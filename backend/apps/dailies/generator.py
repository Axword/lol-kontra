"""
Generator codziennych plansz.

Zasady:
  * każdy slot dostaje dokładnie dwa warunki z różnych motywów,
  * liczba pasujących zawodników musi mieścić się w widełkach MIN/MAX_CANDIDATES,
  * motyw warunku nie może powtórzyć się w oknie THEME_MEMORY_DAYS dni,
  * plansza ma zaplanowany rozkład trudności: 2 łatwe, 2 średnie, 1 trudny slot.
"""
import random
from collections import Counter
from datetime import timedelta
from itertools import combinations
from types import SimpleNamespace

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.players.models import Player

from .models import Daily, DailySlot, DailySlotCondition
from .validators import PlayerFacts, _champion_name, evaluate_condition, player_matches_slot

ROLE_ORDER = ['top', 'jungle', 'mid', 'adc', 'support']

MIN_CANDIDATES = 8
MAX_CANDIDATES = 150
IDEAL_RANGE = (15, 80)
THEME_MEMORY_DAYS = 14

EASY, MEDIUM, HARD = 'easy', 'medium', 'hard'

# (theme, difficulty, condition_type, operator, value, label_pl, label_en)
# `theme` grupuje warunki, które mówią o tym samym – dwa warunki z tym samym motywem
# nie trafią do jednego slotu ani do dwóch slotów tej samej planszy.
CONDITION_POOL = [
    # --- liga / region ---
    ('league', EASY, 'residency', 'eq', 'LCK', 'Grał w LCK', 'Played in LCK'),
    ('league', EASY, 'residency', 'eq', 'LPL', 'Grał w LPL', 'Played in LPL'),
    ('league', EASY, 'residency', 'eq', 'LEC', 'Grał w LEC', 'Played in LEC'),
    ('league', EASY, 'residency', 'eq', 'LCS', 'Grał w LCS', 'Played in LCS'),
    ('league', HARD, 'wildcard_region', 'eq', True, 'Reprezentował region wildcard', 'Wildcard region'),
    ('league', HARD, 'leagues_min', 'gte', 2, 'Grał w dwóch różnych ligach głównych', 'Played in two major leagues'),
    ('league', MEDIUM, 'import_player', 'eq', True, 'Import – grał poza swoim regionem', 'Import player'),

    # --- pochodzenie ---
    ('origin', EASY, 'country', 'eq', 'KR', 'Koreańczyk', 'Korean'),
    ('origin', EASY, 'country', 'eq', 'CN', 'Chińczyk', 'Chinese'),
    ('origin', MEDIUM, 'country', 'eq', 'DK', 'Duńczyk', 'Danish'),
    ('origin', MEDIUM, 'country', 'eq', 'PL', 'Polak', 'Polish'),
    ('origin', MEDIUM, 'country', 'eq', 'FR', 'Francuz', 'French'),
    ('origin', MEDIUM, 'country', 'eq', 'VN', 'Wietnamczyk', 'Vietnamese'),
    ('origin', EASY, 'continent', 'eq', 'Europe', 'Europejczyk', 'European'),
    ('origin', MEDIUM, 'continent', 'eq', 'North America', 'Z Ameryki Północnej', 'North American'),

    # --- drużyny ---
    ('team', EASY, 'team', 'eq', 't1', 'Grał w T1', 'Played for T1'),
    ('team', EASY, 'team', 'eq', 'fnatic', 'Grał we Fnatic', 'Played for Fnatic'),
    ('team', EASY, 'team', 'eq', 'g2', 'Grał w G2', 'Played for G2'),
    ('team', MEDIUM, 'team', 'eq', 'geng', 'Grał w Gen.G', 'Played for Gen.G'),
    ('team', MEDIUM, 'team', 'eq', 'rng', 'Grał w RNG', 'Played for RNG'),
    ('team', MEDIUM, 'team', 'eq', 'edg', 'Grał w EDG', 'Played for EDG'),
    ('team', MEDIUM, 'team', 'eq', 'c9', 'Grał w Cloud9', 'Played for Cloud9'),
    ('team', MEDIUM, 'team', 'eq', 'tsm', 'Grał w TSM', 'Played for TSM'),
    ('team', MEDIUM, 'team', 'eq', 'dwg', 'Grał w DWG KIA', 'Played for DWG KIA'),
    ('team', MEDIUM, 'team', 'eq', 'jdg', 'Grał w JDG', 'Played for JDG'),
    ('team', HARD, 'worlds_teams_min', 'gte', 3, 'Na Worlds w barwach 3 różnych organizacji', '3+ orgs at Worlds'),
    ('team', HARD, 'worlds_teams_min', 'gte', 2, 'Na Worlds w barwach 2 różnych organizacji', '2+ orgs at Worlds'),

    # --- występy na Worlds ---
    ('worlds_count', EASY, 'worlds_count_min', 'gte', 2, 'Min. 2 występy na Worlds', '2+ Worlds appearances'),
    ('worlds_count', MEDIUM, 'worlds_count_min', 'gte', 4, 'Min. 4 występy na Worlds', '4+ Worlds appearances'),
    ('worlds_count', HARD, 'worlds_count_min', 'gte', 6, 'Weteran – min. 6 występów na Worlds', '6+ Worlds appearances'),
    ('worlds_era', HARD, 'worlds_early_era', 'eq', True, 'Grał na Worlds w erze S1-S3', 'Played Worlds in S1-S3'),
    ('worlds_debut', MEDIUM, 'worlds_debut_year', 'lte', 2015, 'Debiut na Worlds do 2015 roku', 'Worlds debut by 2015'),
    ('worlds_last', MEDIUM, 'worlds_last_year', 'gte', 2023, 'Grał na Worlds w 2023 lub później', 'Worlds 2023 or later'),

    # --- osiągnięcia ---
    ('title', EASY, 'worlds_champion', 'eq', True, 'Wygrał Worlds', 'Worlds champion'),
    ('title', HARD, 'worlds_titles_min', 'gte', 2, 'Min. 2 tytuły Worlds', '2+ Worlds titles'),
    ('final', MEDIUM, 'worlds_final', 'eq', True, 'Grał w finale Worlds', 'Played a Worlds final'),
    ('final', HARD, 'worlds_final_lost', 'eq', True, 'Przegrał finał Worlds', 'Lost a Worlds final'),
    ('deep_run', MEDIUM, 'worlds_semifinal', 'eq', True, 'Dotarł do półfinału Worlds', 'Reached a Worlds semifinal'),
    ('deep_run', EASY, 'worlds_group_escape', 'eq', True, 'Wyszedł z fazy grupowej', 'Escaped groups'),
    ('deep_run', HARD, 'worlds_never_escaped', 'gte', 2, 'Mimo 2+ startów nigdy nie wyszedł z grupy', 'Never escaped groups'),
    ('elimination_stage', HARD, 'worlds_eliminated_stage', 'eq', 'play_in', 'Odpadł w play-in Worlds', 'Eliminated in Worlds play-in'),
    ('elimination_stage', MEDIUM, 'worlds_eliminated_stage', 'eq', 'group', 'Odpadł w grupie lub Swiss Worlds', 'Eliminated in Worlds groups or Swiss'),
    ('elimination_stage', MEDIUM, 'worlds_eliminated_stage', 'eq', 'quarterfinal', 'Odpadł w 1/4 finału Worlds', 'Eliminated in Worlds quarterfinals'),
    ('elimination_stage', HARD, 'worlds_eliminated_stage', 'eq', 'semifinal', 'Odpadł w 1/2 finału Worlds', 'Eliminated in Worlds semifinals'),
    ('elimination_stage', HARD, 'worlds_eliminated_stage', 'eq', 'final', 'Przegrał finał Worlds', 'Lost a Worlds final'),
    ('no_title', MEDIUM, 'worlds_never_won', 'gte', 3, 'Mimo 3+ startów nigdy nie wygrał Worlds', 'Never won Worlds'),
    ('playin', HARD, 'worlds_playin', 'eq', True, 'Przeszedł przez play-in', 'Came through play-in'),
    ('penta', HARD, 'pentakill_worlds', 'gte', 1, 'Pentakill na Worlds', 'Pentakill at Worlds'),
    ('msi', MEDIUM, 'msi_appearance', 'eq', True, 'Grał na MSI', 'Played at MSI'),

    # --- kariera ---
    ('status', EASY, 'active', 'eq', True, 'Wciąż aktywny', 'Still active'),
    ('status', EASY, 'active', 'eq', False, 'Zakończył karierę', 'Retired'),
    ('versatility', HARD, 'worlds_multi_role', 'gte', 2, 'Grał na Worlds na dwóch rolach', 'Two roles at Worlds'),
    ('birth', MEDIUM, 'birth_year_range', 'eq', {'min': 1990, 'max': 1999}, 'Urodzony w latach 90.', 'Born in the 1990s'),
    ('birth', MEDIUM, 'birth_year_range', 'eq', {'min': 2000, 'max': 2010}, 'Urodzony w 2000 roku lub później', 'Born in 2000 or later'),
]

# Planowany rozkład trudności slotów na jednej planszy.
DIFFICULTY_PLAN = [EASY, EASY, MEDIUM, MEDIUM, HARD]

# Themes are independent of the current champion list. Historical challenges
# must retain their theme even after a data refresh removes a champion.
STAT_THEMES = {
    'worlds_win_rate': 'worlds_win_rate',
    'worlds_games': 'worlds_games',
    'worlds_top5_champion': 'worlds_top5_champion',
    'career_top5_champion': 'career_top5_champion',
}


def build_condition_pool(players=None):
    """Extend the static pool with statistics currently backed by enough players.

    Build this for each role at generation time; importing the module must not
    capture an empty database or leave champion choices stale after an update.
    The shared validator supplies the definition of complete, trustworthy data.
    """
    players = list(players if players is not None else Player.objects.all().order_by('slug'))
    eligible = [(player, PlayerFacts(player)) for player in players
                if player.attributes.get('worlds_verified') is not False]
    verified = [(player, facts) for player, facts in eligible if facts.worlds_stats is not None]
    pool = list(CONDITION_POOL)

    statistical = [
        ('worlds_win_rate', MEDIUM, 'worlds_win_rate', 'gt', 50,
         'Ponad 50% wygranych na Worlds', 'Over 50% wins at Worlds'),
        ('worlds_win_rate', MEDIUM, 'worlds_win_rate', 'lt', 50,
         'Poniżej 50% wygranych na Worlds', 'Under 50% wins at Worlds'),
    ]
    for threshold, greater_difficulty, less_difficulty in [
        (10, EASY, HARD), (25, EASY, MEDIUM), (50, MEDIUM, EASY), (100, HARD, EASY),
    ]:
        statistical.extend([
            ('worlds_games', greater_difficulty, 'worlds_games', 'gt', threshold,
             f'Ponad {threshold} gier na Worlds', f'Over {threshold} games at Worlds'),
            ('worlds_games', less_difficulty, 'worlds_games', 'lt', threshold,
             f'Poniżej {threshold} gier na Worlds', f'Under {threshold} games at Worlds'),
        ])

    champion_counts = {}
    for condition_type, property_name, facts_list, label_pl, label_en in [
        ('worlds_top5_champion', 'worlds_top5_champions', verified, 'na Worlds', 'Worlds'),
        ('career_top5_champion', 'career_top5_champions', eligible, 'kariery', 'career'),
    ]:
        champions = {}
        counts = Counter()
        for _player, facts in facts_list:
            top_five = getattr(facts, property_name)
            counts.update({_champion_name(champion) for champion in top_five})
            for champion in top_five:
                champions.setdefault(champion.casefold(), champion)
        champion_counts[condition_type] = counts
        for key in sorted(champions):
            champion = champions[key]
            statistical.append((condition_type, MEDIUM, condition_type, 'eq', champion,
                                f'{champion} w TOP 5 {label_pl}', f'{champion} in {label_en} top 5 played'))

    for condition in statistical:
        if condition[2] in champion_counts:
            matching = champion_counts[condition[2]][_champion_name(condition[4])]
        else:
            matching = sum(evaluate_condition(player, *condition[2:5]) for player, _facts in verified)
        # A broad statistic can still form a valid intersection with another
        # theme; MAX_CANDIDATES applies to the completed slot, below.
        if matching >= MIN_CANDIDATES:
            pool.append(condition)
    return pool


def _role_pool(role):
    """Zawodnicy grający na danej roli – bez filtra aktywności (to osobny warunek)."""
    players = (
        Player.objects.filter(Q(primary_role=role) | Q(secondary_roles__contains=[role])).order_by('slug')
    )
    return [player for player in players if player.attributes.get('worlds_verified') is not False]


def count_candidates(slot, pool=None):
    """Lista zawodników spełniających wszystkie warunki slotu."""
    pool = pool if pool is not None else _role_pool(slot.role)
    conditions = list(slot.conditions.all())
    probe = SimpleNamespace(role=slot.role, conditions=SimpleNamespace(all=lambda: conditions))
    return [p for p in pool if player_matches_slot(p, probe)]


def _candidates_for_conditions(role, chosen, pool):
    conditions = [SimpleNamespace(condition_type=c[2], operator=c[3], value=c[4]) for c in chosen]
    probe = SimpleNamespace(role=role, conditions=SimpleNamespace(all=lambda: conditions))
    return [p for p in pool if player_matches_slot(p, probe)]


def _has_distinct_roster(candidate_pools):
    """A player may fill only one slot, even when several roles are recorded."""
    assigned = {}

    def assign(index, visited):
        for player in candidate_pools[index]:
            if player.pk in visited:
                continue
            visited.add(player.pk)
            if player.pk not in assigned or assign(assigned[player.pk], visited):
                assigned[player.pk] = index
                return True
        return False

    return all(assign(index, set()) for index in range(len(candidate_pools)))


def _independent_conditions(first, second):
    if first[0] == second[0]:
        return False
    if second[2] == 'worlds_eliminated_stage':
        first, second = second, first
    if first[2] != 'worlds_eliminated_stage' or second[4] is not True:
        return True
    implied = {
        'quarterfinal': {'worlds_group_escape'},
        'semifinal': {'worlds_group_escape', 'worlds_semifinal'},
        'final': {'worlds_group_escape', 'worlds_semifinal', 'worlds_final', 'worlds_final_lost'},
    }
    return not isinstance(first[4], str) or second[2] not in implied.get(first[4], set())


def validate_daily(daily):
    """Return a playable daily or raise without changing any stored answers."""
    slots = list(daily.slots.order_by('position').prefetch_related('conditions'))
    if [slot.role for slot in slots] != ROLE_ORDER:
        raise ValueError('Daily must contain five slots in the expected role order')
    themes = {condition[2]: condition[0] for condition in CONDITION_POOL}
    themes.update(STAT_THEMES)
    for slot in slots:
        conditions = list(slot.conditions.all())
        if (len(conditions) != 2 or any(condition.condition_type == 'role' for condition in conditions)
                or not _independent_conditions(*[(themes.get(c.condition_type, c.condition_type), None,
                                                 c.condition_type, c.operator, c.value) for c in conditions])):
            raise ValueError('Every slot must contain exactly two independent requirements')
    pools = [count_candidates(slot) for slot in slots]
    if any(not MIN_CANDIDATES <= len(pool) <= MAX_CANDIDATES for pool in pools):
        raise ValueError(f'Every slot must have {MIN_CANDIDATES}–{MAX_CANDIDATES} valid candidates')
    if not _has_distinct_roster(pools):
        raise ValueError('Daily has no solution using five different players')
    return daily


def recent_themes(before_date, days=THEME_MEMORY_DAYS):
    """Motywy warunków użyte w ostatnich `days` dniach – żeby ich nie powtarzać."""
    since = before_date - timedelta(days=days)
    used = set()
    conditions = DailySlotCondition.objects.filter(
        slot__daily__date__gte=since, slot__daily__date__lt=before_date
    ).values_list('condition_type', 'value')
    by_type = {}
    for theme, _diff, ctype, _op, value, _pl, _en in CONDITION_POOL:
        by_type.setdefault((ctype, str(value)), theme)
    for ctype, value in conditions:
        theme = STAT_THEMES.get(ctype) or by_type.get((ctype, str(value)))
        if theme:
            used.add(theme)
    return used


def _write_conditions(slot, chosen):
    slot.conditions.all().delete()
    for order, (_theme, _diff, ctype, operator, value, label_pl, label_en) in enumerate(chosen):
        DailySlotCondition.objects.create(
            slot=slot,
            condition_type=ctype,
            operator=operator,
            value=value,
            label_pl=label_pl,
            label_en=label_en,
            order=order,
        )


def generate_slot(daily, role, position, difficulty, rnd, used_themes, pool=None, condition_pool=None):
    """
    Buduje jeden slot. Zwraca (slot, candidates).

    Szuka dwóch warunków dających sensowną liczbę kandydatów. Jeśli po
    wyczerpaniu prób nie znajdzie nic w idealnym zakresie, bierze najlepszy
    napotkany wariant zamiast zostawiać slot niegrywalny.
    """
    slot = DailySlot.objects.create(
        daily=daily, role=role, position=position,
        label_pl=role.capitalize(), label_en=role.capitalize(),
    )
    pool = pool if pool is not None else _role_pool(role)
    if not pool:
        raise ValueError(f'No players available for role {role}')
    condition_pool = condition_pool if condition_pool is not None else build_condition_pool(pool)
    condition_pool = [condition for condition in condition_pool if condition[2] != 'role']

    primary = [c for c in condition_pool if c[1] == difficulty and c[0] not in used_themes]
    if not primary:
        primary = [c for c in condition_pool if c[1] == difficulty]
    secondary = [c for c in condition_pool if c[0] not in used_themes] or list(condition_pool)

    best = None  # (odległość od ideału, warunki, kandydaci)

    for _ in range(40 if primary else 0):
        anchor = rnd.choice(primary)
        others = [c for c in secondary if _independent_conditions(anchor, c)]
        if not others:
            continue
        chosen = [anchor, rnd.choice(others)]
        candidates = _candidates_for_conditions(role, chosen, pool)
        count = len(candidates)

        if IDEAL_RANGE[0] <= count <= IDEAL_RANGE[1]:
            _write_conditions(slot, chosen)
            return slot, candidates

        if MIN_CANDIDATES <= count <= MAX_CANDIDATES:
            distance = min(abs(count - IDEAL_RANGE[0]), abs(count - IDEAL_RANGE[1]))
            if best is None or distance < best[0]:
                best = (distance, chosen, candidates)

    if best:
        _write_conditions(slot, best[1])
        return slot, best[2]

    # Exhaust the remaining pairs without ever reducing the requirement count.
    # Each single-condition candidate set is evaluated once in this fallback.
    fallbacks = list(condition_pool)
    rnd.shuffle(fallbacks)
    matches = {}
    for first, second in combinations(range(len(fallbacks)), 2):
        chosen = [fallbacks[first], fallbacks[second]]
        if not _independent_conditions(*chosen):
            continue
        for index in (first, second):
            if index not in matches:
                matches[index] = {player.pk for player in _candidates_for_conditions(role, [fallbacks[index]], pool)}
        matching = matches[first] & matches[second]
        count = len(matching)
        if not MIN_CANDIDATES <= count <= MAX_CANDIDATES:
            continue
        candidates = [player for player in pool if player.pk in matching]
        if IDEAL_RANGE[0] <= count <= IDEAL_RANGE[1]:
            _write_conditions(slot, chosen)
            return slot, candidates
        distance = min(abs(count - IDEAL_RANGE[0]), abs(count - IDEAL_RANGE[1]))
        if best is None or distance < best[0]:
            best = (distance, chosen, candidates)
    if best:
        _write_conditions(slot, best[1])
        return slot, best[2]
    raise ValueError(f'Cannot find two independent requirements for {role} with {MIN_CANDIDATES}–{MAX_CANDIDATES} candidates')


@transaction.atomic
def generate_daily(date=None, seed=None, force=False):
    """Tworzy planszę na wskazany dzień (domyślnie jutro)."""
    if date is None:
        date = timezone.localdate() + timedelta(days=1)

    daily, _created = Daily.objects.select_for_update().get_or_create(
        date=date,
        defaults={'status': 'draft', 'locale_seed': str(seed or date), 'reveal_mode': 'instant'},
    )
    if daily.slots.exists():
        if not force:
            return validate_daily(daily)
        if daily.submissions.exists():
            raise ValueError('Cannot regenerate a daily with existing submissions')
        daily.slots.all().delete()

    rnd = random.Random(f'{date}-{seed}')
    used_themes = recent_themes(date)
    plan = list(DIFFICULTY_PLAN)
    rnd.shuffle(plan)

    theme_by_condition = {
        (ctype, str(value)): theme
        for theme, _d, ctype, _o, value, _pl, _en in CONDITION_POOL
    }

    candidate_pools = []
    for position, (role, difficulty) in enumerate(zip(ROLE_ORDER, plan), start=1):
        pool = _role_pool(role)
        slot, candidates = generate_slot(daily, role, position, difficulty, rnd, used_themes, pool)
        candidate_pools.append(candidates)
        for cond in slot.conditions.all():
            theme = STAT_THEMES.get(cond.condition_type) or theme_by_condition.get((cond.condition_type, str(cond.value)))
            if theme:
                used_themes.add(theme)

    if not _has_distinct_roster(candidate_pools):
        raise ValueError('No solution using five different players')
    return daily
