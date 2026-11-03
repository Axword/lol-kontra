"""Reviewed daily clues for confirmed matches; never guess a future matchup."""
from datetime import date
import json
from pathlib import Path
from types import SimpleNamespace

from django.db import transaction

PLAN_FILE = Path(__file__).resolve().parent / 'fixtures' / 'editorial' / 'worlds_2026_playoffs.json'
# A daily roster should offer room for personal, uncommon choices. Small
# curated intersections turn it into a trivia question with only a few answers.
MIN_MATCH_CANDIDATES = 18


def load_plan():
    plan = json.loads(PLAN_FILE.read_text(encoding='utf-8'))
    if plan.get('schema_version') != 1:
        raise ValueError('Unsupported match board plan')
    days = [entry['date'] for entry in plan['matches']]
    if len(days) != len(set(days)):
        raise ValueError('A day may have only one reviewed match board')
    for entry in plan['matches']:
        date.fromisoformat(entry['date'])
        if entry.get('review_status') not in {'draft', 'approved', 'pending_matchup'}:
            raise ValueError('Unknown match board review status')
        if entry['review_status'] != 'pending_matchup' and len(entry.get('teams', [])) != 2:
            raise ValueError('A confirmed match needs two teams')
    return plan


def match_for_day(day):
    day = day.isoformat() if isinstance(day, date) else str(day)
    return next((entry for entry in load_plan()['matches'] if entry['date'] == day), None)


def audit_match_board(entry, players):
    """Read-only checks shared by editorial preview and the eventual writer."""
    from .generator import ROLE_ORDER, _has_distinct_roster, validate_board_diversity
    from .models import valid_requirement_count
    from .validators import PlayerFacts, evaluate_condition

    if entry['review_status'] == 'pending_matchup' or len(entry.get('teams', [])) != 2:
        raise ValueError('The actual opponents have not been confirmed')
    slots = entry.get('slots', [])
    if [slot['role'] for slot in slots] != ROLE_ORDER:
        raise ValueError('Match board needs five ordered positions')
    validate_board_diversity([slot['conditions'] for slot in slots])
    kinds = [c['condition_type'] for slot in slots for c in slot['conditions']]
    if sum(kind in {'league', 'residency', 'region'} for kind in kinds) > 1:
        raise ValueError('Match board may use only one league clue')
    if sum(kind in {'worlds_top5_champion', 'career_top5_champion', 'champion_played'} for kind in kinds) > 1:
        raise ValueError('Match board may use only one champion clue')
    if sum(bool(slot.get('match_context')) for slot in slots) < 2:
        raise ValueError('At least two positions must relate to the scheduled match')
    players = list(players)
    pools = []
    for slot in slots:
        conditions = [SimpleNamespace(**condition) for condition in slot['conditions']]
        if not valid_requirement_count(conditions):
            raise ValueError('Invalid number of match requirements')
        pool = [p for p in players if slot['role'] in PlayerFacts(p).roles and all(
            evaluate_condition(p, c.condition_type, c.operator, c.value) for c in conditions)]
        if not MIN_MATCH_CANDIDATES <= len(pool) <= 150:
            raise ValueError(f"Match position {slot['role']} needs {MIN_MATCH_CANDIDATES}–150 valid answers")
        if not set(slot.get('audited_candidates', [])).issubset({p.slug for p in pool}):
            raise ValueError(f"Verified answers no longer match {slot['role']}")
        pools.append(pool)
    if not _has_distinct_roster(pools):
        raise ValueError('Match board needs five different players')
    return pools


def store_match_board(daily):
    """Use approved entries; unpublished editorial work never blocks daily play."""
    from apps.players.models import Player
    from .models import DailySlot, DailySlotCondition

    entry = match_for_day(daily.date)
    if entry is None or entry['review_status'] != 'approved':
        return None
    if daily.slots.exists():
        raise ValueError('Existing match boards must retain their slots and saved games')
    with transaction.atomic():
        audit_match_board(entry, Player.objects.all().order_by('slug'))
        daily.author_name = entry.get('author_name', 'Axword')
        daily.author_url = entry.get('author_url', 'https://x.com/AxwordLol')
        daily.author_description = entry['description_pl']
        daily.minimum_candidates = None
        daily.locale_seed = f"worlds-match-{entry['date']}-v1"
        daily.save(update_fields=['author_name', 'author_url', 'author_description', 'minimum_candidates', 'locale_seed'])
        for position, slot in enumerate(entry['slots'], 1):
            row = DailySlot.objects.create(daily=daily, position=position, role=slot['role'],
                label_pl=slot['role'].capitalize(), label_en=slot['role'].capitalize())
            DailySlotCondition.objects.bulk_create([DailySlotCondition(slot=row, order=order, **condition)
                for order, condition in enumerate(slot['conditions'])])
    return daily
