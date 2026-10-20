"""Worlds-focused boards: three Worlds positions, two career positions, ten answers each."""
from collections import Counter
from datetime import date
from itertools import combinations
import random
from types import SimpleNamespace

from django.core.cache import cache
from django.db.models import Max

from apps.players.models import Player
from apps.players.majority_roles import SOURCE_SHA256
from apps.players.activity import SOURCE_SHA256 as ACTIVITY_SHA256
from django.utils import timezone
from .models import SINGLE_REQUIREMENT_TYPES
from .validators import PlayerFacts, _champion_name, evaluate_condition

EDITORIAL_FROM = date(2026, 10, 21)
MINIMUM = 10


def is_worlds(kind):
    return kind.startswith('worlds_') or kind == 'pentakill_worlds'


def build_catalog(players):
    from .generator import CONDITION_POOL, _independent_conditions, single_candidate_limit
    players = [p for p in players if p.attributes.get('worlds_verified') is not False]
    facts = {p.pk: PlayerFacts(p) for p in players}
    conditions = [c for c in CONDITION_POOL if c[2] not in ('birth_continent', 'worlds_multi_role', 'active')]
    # Retirement remains available as a second, independent career clue.
    conditions += [c for c in CONDITION_POOL if c[2] == 'active']
    champion_players = {}
    for player in players:
        for champion in facts[player.pk].worlds_top5_champions:
            champion_players.setdefault(_champion_name(champion), {'name': champion, 'players': set()})['players'].add(player.pk)
    for entry in champion_players.values():
        if len(entry['players']) >= MINIMUM:
            champion = entry['name']
            conditions.append(('worlds_top5_champion', 'medium', 'worlds_top5_champion', 'eq', champion,
                f'{champion} w jego TOP 5 według liczby gier na Worlds',
                f'{champion} in his top 5 champions by games played at Worlds'))
    matches = {}
    for index, condition in enumerate(conditions):
        if condition[2] == 'worlds_top5_champion':
            matches[index] = champion_players[_champion_name(condition[4])]['players']
        else:
            matches[index] = {p.pk for p in players if evaluate_condition(p, *condition[2:5])}
    result = {}
    for role in ('top', 'jungle', 'mid', 'adc', 'support'):
        role_ids = {p.pk for p in players if role in facts[p.pk].roles}
        by_condition = {i: ids & role_ids for i, ids in matches.items()}
        useful = [i for i, ids in by_condition.items() if len(ids) >= MINIMUM]
        options = []

        def add(indices, candidates):
            if not MINIMUM <= len(candidates) <= 150:
                return
            selected = [conditions[i] for i in indices]
            if len(selected) == 1 and len(candidates) > single_candidate_limit(selected[0][2]):
                return
            if sum(c[2] == 'worlds_top5_champion' for c in selected) > 1:
                return
            # The shared year is a curation preference, never a hidden answer rule.
            years = Counter(year for pk in candidates for year in facts[pk].worlds_years)
            anchor_players = {}
            for pk in candidates:
                for team, played_years in facts[pk].attr.get('worlds_team_years', {}).items():
                    for year in played_years:
                        anchor_players.setdefault(f'{year}:{team}', []).append(pk)
            options.append({'conditions': [list(c) for c in selected],
                'candidate_ids': sorted(candidates), 'years': dict(years),
                'anchors': sorted(anchor_players), 'anchor_players': anchor_players,
                'worlds': any(is_worlds(c[2]) for c in selected)})

        for i in useful:
            if conditions[i][2] in SINGLE_REQUIREMENT_TYPES:
                add([i], by_condition[i])
        for first, second in combinations(useful, 2):
            a, b = conditions[first], conditions[second]
            if not _independent_conditions(a, b):
                continue
            if a[0] in ('worlds_count', 'worlds_debut', 'worlds_last') and b[0] in ('worlds_count', 'worlds_debut', 'worlds_last'):
                continue
            # A broad nationality/league plus one clear Worlds fact is easier to
            # reason about than two champion or numerical requirements.
            candidates = by_condition[first] & by_condition[second]
            if len(candidates) > .8 * min(len(by_condition[first]), len(by_condition[second])):
                continue
            add([first, second], candidates)
        if not all(any(o['worlds'] == category for o in options) for category in (True, False)):
            raise ValueError(f'Not enough independent ten-answer clues for {role}')
        result[role] = options
    return result


def question_catalog():
    version = Player.objects.aggregate(updated=Max('updated_at'))['updated']
    key = f'worlds-board-catalog-v4:{SOURCE_SHA256}:{ACTIVITY_SHA256}:{timezone.localdate()}:{version.isoformat() if version else "empty"}:{Player.objects.count()}'
    catalog = cache.get(key)
    if catalog is None:
        catalog = build_catalog(list(Player.objects.order_by('slug')))
        cache.set(key, catalog, 600)
    return catalog


def choose_board(catalog, rnd=None, recent=None, previous=None):
    from .generator import ROLE_ORDER, requirement_key, _has_distinct_roster
    rnd = rnd or random.SystemRandom()
    recent = recent or Counter()
    previous = previous or []
    roles = list(ROLE_ORDER)
    years = sorted({int(year) for options in catalog.values() for option in options for year in option['years']})
    include_champion = rnd.random() < .25
    rnd.shuffle(years)
    anchors = sorted(set.intersection(*[{anchor for option in catalog[role] for anchor in option.get('anchors', [])} for role in roles]))
    rnd.shuffle(anchors)
    # Try an actual Worlds team first. The hints stay open to other valid
    # players, but one recognizable lineup can solve the entire board.
    contexts = [(int(anchor.split(':',1)[0]),anchor) for anchor in anchors] + [(year,None) for year in years]
    for year,anchor in contexts:
        categories = [True, True, True, False, False]
        rnd.shuffle(categories)
        chosen, used = [], set()
        for role, category in zip(roles, categories):
            options = [o for o in catalog[role] if o['worlds'] == category
                and (anchor in o.get('anchors', []) if anchor else o['years'].get(year, o['years'].get(str(year), 0)) >= 1)]
            if not options:
                break
            def cost(option):
                kinds = {c[2] for c in option['conditions']}
                repeated = len(kinds & used)
                history = sum(recent[requirement_key(*c[2:5])] for c in option['conditions'])
                # Prefer achievements; at most one champion clue on a board.
                return repeated * 20 + history * 3
            available = [o for o in options if not ((not include_champion or 'worlds_top5_champion' in used)
                and any(c[2] == 'worlds_top5_champion' for c in o['conditions']))]
            if not available:
                break
            minimum = min(map(cost, available))
            selected = rnd.choice([o for o in available if cost(o) <= minimum + 1])
            chosen.append(selected)
            used.update(c[2] for c in selected['conditions'])
        if len(chosen) == 5:
            if anchor and not _has_distinct_roster([
                [SimpleNamespace(pk=pk) for pk in option['anchor_players'][anchor]]
                for option in chosen
            ]):
                continue
            signature = [option['conditions'] for option in chosen]
            if signature == previous:
                continue
            return chosen, year
    raise ValueError('Cannot build a coherent five-position board with ten candidates each')


def store_daily(daily, rnd, recent):
    from .generator import ROLE_ORDER, _has_distinct_roster, _write_conditions
    from .models import DailySlot
    selected, year = choose_board(question_catalog(), rnd, recent)
    pools = [list(Player.objects.filter(pk__in=entry['candidate_ids'])) for entry in selected]
    if not _has_distinct_roster(pools):
        raise ValueError('Board needs five different players')
    for position, (role, entry) in enumerate(zip(ROLE_ORDER, selected), 1):
        slot = DailySlot.objects.create(daily=daily, role=role, position=position,
            label_pl=role.capitalize(), label_en=role.capitalize())
        _write_conditions(slot, entry['conditions'])
    return daily
