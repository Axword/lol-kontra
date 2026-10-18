"""Immutable October release importer. Keep this contract with migration 0009."""
from collections import Counter
from datetime import date, datetime
import gzip
import hashlib
import json
from pathlib import Path

from django.db import transaction

RELEASE_SHA256 = 'ea1e06459a88ce28cf190f99c53a04141830a2cf7d00e45d8eb36082b88aaf4e'
ROLES = ('top', 'jungle', 'mid', 'adc', 'support')


def validate_calendar(document):
    def require(ok, message):
        if not ok:
            raise ValueError('Calendar release rejected: ' + message)

    require(isinstance(document, dict) and set(document) == {'release', 'boards'}
            and document['release'] == 'october-2026-v1', 'unknown release')
    boards = document['boards']
    require(isinstance(boards, list) and len(boards) == 31, 'expected 31 boards')
    for day, board in enumerate(boards, 1):
        require(set(board) == {'date', 'status', 'locale_seed', 'published_at', 'closed_at', 'slots', 'test_rosters'}, 'unexpected board fields')
        require(board['date'] == date(2026, 10, day).isoformat(), 'missing or duplicate date')
        require(board['status'] in {'published', 'closed', 'scored'}, 'invalid status')
        require(isinstance(board['locale_seed'], str) and len(board['locale_seed']) <= 64, 'invalid seed')
        for field in ('published_at', 'closed_at'):
            stamp = board[field]
            require(stamp is None or datetime.fromisoformat(stamp).tzinfo is not None, 'naive timestamp')
        slots = board['slots']
        require(isinstance(slots, list) and len(slots) == 5, 'expected five slots')
        for position, (role, slot) in enumerate(zip(ROLES, slots), 1):
            require(set(slot) == {'position', 'role', 'label_pl', 'label_en', 'conditions'}
                    and slot['role'] == role and slot['position'] == position, 'invalid slot role/order')
            require(all(isinstance(slot[key], str) and len(slot[key]) <= 128 for key in ('label_pl', 'label_en')), 'invalid slot label')
            conditions = slot['conditions']
            require(isinstance(conditions, list) and len(conditions) == 2, 'every slot needs two requirements')
            for condition in conditions:
                require(set(condition) == {'condition_type', 'operator', 'value', 'label_pl', 'label_en', 'order'}, 'unexpected condition fields')
                require(isinstance(condition['condition_type'], str) and 0 < len(condition['condition_type']) <= 32
                        and condition['operator'] in {'eq', 'in', 'any', 'gt', 'lt', 'gte', 'lte'}
                        and type(condition['order']) is int and condition['order'] >= 0, 'invalid condition')
                require(all(isinstance(condition[key], str) and 0 < len(condition[key]) <= 256 for key in ('label_pl', 'label_en')), 'invalid requirement label')
        rosters = board['test_rosters']
        require(isinstance(rosters, list) and len(rosters) == 10, 'expected ten test rosters')
        for roster in rosters:
            require(isinstance(roster, dict) and set(roster) == set(ROLES)
                    and all(isinstance(slug, str) and slug.strip() for slug in roster.values())
                    and len(set(roster.values())) == 5, 'test roster requires five different players')
    return boards


def load_calendar():
    path = Path(__file__).resolve().parents[1] / 'fixtures/releases/october_2026_v1.json.gz'
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != RELEASE_SHA256:
        raise ValueError('Calendar release rejected: SHA-256 mismatch')
    return validate_calendar(json.loads(gzip.decompress(payload)))


def install_calendar(apps, schema_editor):
    boards = load_calendar()
    alias = schema_editor.connection.alias
    Player = apps.get_model('players', 'Player')
    Daily = apps.get_model('dailies', 'Daily')
    Slot = apps.get_model('dailies', 'DailySlot')
    Condition = apps.get_model('dailies', 'DailySlotCondition')
    Submission = apps.get_model('submissions', 'Submission')
    Answer = apps.get_model('submissions', 'SubmissionAnswer')
    Attempt = apps.get_model('submissions', 'SubmissionAttempt')
    Stats = apps.get_model('scoring', 'AnswerStatsDaily')
    Config = apps.get_model('scoring', 'ScoringConfig')
    slugs = {slug for board in boards for roster in board['test_rosters'] for slug in roster.values()}
    players = Player.objects.using(alias).in_bulk(slugs, field_name='slug')
    if set(players) != slugs or any(player.attributes.get('worlds_verified') is not True for player in players.values()):
        raise ValueError('Calendar release rejected: missing verified player identities')
    with transaction.atomic(using=alias):
        if not Config.objects.using(alias).filter(is_active=True).exists():
            Config.objects.using(alias).create(is_active=True)
        for board in boards:
            # Existing boards and all real answers belong to their users. The
            # release only initializes dates absent from this installation.
            if Daily.objects.using(alias).filter(date=board['date']).exists():
                continue
            daily = Daily.objects.using(alias).create(date=board['date'], status=board['status'],
                locale_seed=board['locale_seed'], reveal_mode='instant',
                published_at=datetime.fromisoformat(board['published_at']) if board['published_at'] else None,
                closed_at=datetime.fromisoformat(board['closed_at']) if board['closed_at'] else None)
            slots = {}
            for source in board['slots']:
                slot = Slot.objects.using(alias).create(daily_id=daily.pk,
                    **{key: source[key] for key in ('position', 'role', 'label_pl', 'label_en')})
                slots[slot.role] = slot
                Condition.objects.using(alias).bulk_create([
                    Condition(slot_id=slot.pk, **condition) for condition in source['conditions']])
            counts = {role: Counter(roster[role] for roster in board['test_rosters']) for role in ROLES}
            for voter, roster in enumerate(board['test_rosters'], 1):
                penalties = {role: counts[role][roster[role]] / 10 * 100.0 for role in ROLES}
                game = Submission.objects.using(alias).create(daily_id=daily.pk,
                    guest_token=f"seed-{board['date']}-{voter:02d}", is_seed=True,
                    total_points=round(500.0 - sum(penalties.values()), 6))
                answers, attempts = [], []
                for role in ROLES:
                    percent = penalties[role]
                    tier = 'common' if percent > 20 else 'rare' if percent > 10 else 'epic' if percent > 1 else 'legendary'
                    answers.append(Answer(submission_id=game.pk, daily_slot_id=slots[role].pk,
                        player_id=players[roster[role]].pk, is_correct=True, rarity_tier=tier,
                        rarity_percent=percent, points_awarded=-percent,
                        scoring_pick_count=counts[role][roster[role]], scoring_sample_size=10))
                    attempts.append(Attempt(submission_id=game.pk, daily_slot_id=slots[role].pk,
                        player_id=players[roster[role]].pk, is_correct=True))
                Answer.objects.using(alias).bulk_create(answers)
                Attempt.objects.using(alias).bulk_create(attempts)
            for role in ROLES:
                stats = []
                for slug, count in counts[role].items():
                    percent = count / 10 * 100.0
                    tier = 'common' if percent > 20 else 'rare' if percent > 10 else 'epic' if percent > 1 else 'legendary'
                    stats.append(Stats(daily_slot_id=slots[role].pk, player_id=players[slug].pk,
                        pick_count=count, pick_percent=percent, rarity_tier=tier))
                Stats.objects.using(alias).bulk_create(stats)
