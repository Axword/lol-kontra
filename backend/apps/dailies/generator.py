"""
Generator codziennych plansz.

Zasady:
  * jeden wymagający warunek lub dwa, z których każdy zawęża odpowiedzi,
  * liczba pasujących zawodników musi mieścić się w widełkach MIN/MAX_CANDIDATES,
  * preferujemy motywy nieużywane w oknie THEME_MEMORY_DAYS dni,
  * plansza ma zaplanowany rozkład trudności: 2 łatwe, 2 średnie, 1 trudny slot.
"""
import random
import json
from collections import Counter, defaultdict
from datetime import timedelta
from itertools import combinations
from types import SimpleNamespace

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.players.models import Player

from .models import Daily, DailySlot, DailySlotCondition, SINGLE_REQUIREMENT_TYPES, valid_requirement_count
from .validators import PlayerFacts, _champion_name, evaluate_condition, player_matches_slot

ROLE_ORDER = ['top', 'jungle', 'mid', 'adc', 'support']

MIN_CANDIDATES = 10
MAX_CANDIDATES = 150
THEME_MEMORY_DAYS = 14

EASY, MEDIUM, HARD = 'easy', 'medium', 'hard'
CHAMPION_RANK_TYPES = {'worlds_top5_champion', 'career_top5_champion'}


def single_candidate_limit(condition_type):
    return 25 if condition_type in CHAMPION_RANK_TYPES else 18

# (theme, difficulty, condition_type, operator, value, label_pl, label_en)
# `theme` grupuje warunki, które mówią o tym samym – dwa warunki z tym samym motywem
# nie trafią do jednego slotu; na kolejnych pozycjach wolimy inne motywy.
CONDITION_POOL = [
    # --- liga / region ---
    ('league', EASY, 'residency', 'eq', 'LCK', 'Grał w LCK', 'Played in LCK'),
    ('league', EASY, 'residency', 'eq', 'LPL', 'Grał w LPL', 'Played in LPL'),
    ('league', EASY, 'residency', 'eq', 'LEC', 'Grał w LEC / EU LCS', 'Played in LEC / EU LCS'),
    ('league', EASY, 'residency', 'eq', 'LCS', 'Grał w LCS / NA LCS', 'Played in LCS / NA LCS'),
    ('league', HARD, 'leagues_min', 'gte', 2, 'Grał w min. 2 z lig: LCK, LPL, LEC, LCS, LTA', 'Played in at least 2 of LCK, LPL, LEC, LCS, LTA'),

    # --- pochodzenie ---
    ('origin', EASY, 'country', 'eq', 'KR', 'Koreańczyk', 'Korean'),
    ('origin', EASY, 'country', 'eq', 'CN', 'Chińczyk', 'Chinese'),
    ('origin', MEDIUM, 'country', 'eq', 'DK', 'Duńczyk', 'Danish'),
    ('origin', MEDIUM, 'country', 'eq', 'PL', 'Polak', 'Polish'),
    ('origin', MEDIUM, 'country', 'eq', 'FR', 'Francuz', 'French'),
    ('origin', MEDIUM, 'country', 'eq', 'VN', 'Wietnamczyk', 'Vietnamese'),
    ('origin', MEDIUM, 'country', 'eq', 'TW', 'Tajwańczyk', 'Taiwanese'),
    ('origin', EASY, 'birth_continent', 'eq', 'Europe', 'Urodzony w Europie', 'Born in Europe'),
    ('origin', MEDIUM, 'birth_continent', 'eq', 'North America', 'Urodzony w Ameryce Północnej', 'Born in North America'),

    # --- drużyny ---
    ('team', EASY, 'team', 'eq', 't1', 'Grał w T1 / SKT T1', 'Played for T1 / SKT T1'),
    ('team', EASY, 'team', 'eq', 'fnatic', 'Grał we Fnatic', 'Played for Fnatic'),
    ('team', EASY, 'team', 'eq', 'g2', 'Grał w G2', 'Played for G2'),
    ('team', MEDIUM, 'team', 'eq', 'geng', 'Grał w Gen.G', 'Played for Gen.G'),
    ('team', MEDIUM, 'team', 'eq', 'rng', 'Grał w RNG', 'Played for RNG'),
    ('team', MEDIUM, 'team', 'eq', 'edg', 'Grał w EDG', 'Played for EDG'),
    ('team', MEDIUM, 'team', 'eq', 'c9', 'Grał w Cloud9', 'Played for Cloud9'),
    ('team', MEDIUM, 'team', 'eq', 'tsm', 'Grał w TSM', 'Played for TSM'),
    ('team', MEDIUM, 'team', 'eq', 'dwg', 'Grał w DAMWON / DWG KIA / Dplus KIA', 'Played for DAMWON / DWG KIA / Dplus KIA'),
    ('team', MEDIUM, 'team', 'eq', 'jdg', 'Grał w JDG', 'Played for JDG'),
    ('team', HARD, 'worlds_teams_min', 'gte', 3, 'Grał na Worlds w barwach min. 3 organizacji', 'Played for at least 3 organizations at Worlds'),
    ('team', HARD, 'worlds_teams_min', 'gte', 2, 'Grał na Worlds w barwach min. 2 organizacji', 'Played for at least 2 organizations at Worlds'),

    # --- występy na Worlds ---
    ('worlds_count', EASY, 'worlds_count_min', 'gte', 2, 'Zagrał w min. 2 edycjach Worlds', 'Played in at least 2 editions of Worlds'),
    ('worlds_count', MEDIUM, 'worlds_count_min', 'gte', 4, 'Zagrał w min. 4 edycjach Worlds', 'Played in at least 4 editions of Worlds'),
    ('worlds_count', HARD, 'worlds_count_min', 'gte', 6, 'Zagrał w min. 6 edycjach Worlds', 'Played in at least 6 editions of Worlds'),
    ('worlds_era', HARD, 'worlds_early_era', 'eq', True, 'Grał na Worlds 2011, 2012 lub 2013', 'Played at Worlds in 2011, 2012 or 2013'),
    ('worlds_debut', MEDIUM, 'worlds_debut_year', 'lte', 2015, 'Debiutował na Worlds w 2015 lub wcześniej', 'First Worlds appearance in 2015 or earlier'),
    ('worlds_last', MEDIUM, 'worlds_last_year', 'gte', 2023, 'Grał na Worlds w 2023 lub później', 'Worlds 2023 or later'),

    # --- osiągnięcia ---
    ('title', EASY, 'worlds_champion', 'eq', True, 'Wygrał Worlds', 'Worlds champion'),
    ('title', HARD, 'worlds_titles_min', 'gte', 2, 'Min. 2 tytuły Worlds', '2+ Worlds titles'),
    ('final', MEDIUM, 'worlds_final', 'eq', True, 'Grał w finale Worlds', 'Played a Worlds final'),
    ('final', HARD, 'worlds_final_lost', 'eq', True, 'Przegrał finał Worlds', 'Lost a Worlds final'),
    ('deep_run', MEDIUM, 'worlds_semifinal', 'eq', True, 'Dotarł co najmniej do półfinału Worlds', 'Reached at least the Worlds semifinals'),
    ('deep_run', EASY, 'worlds_group_escape', 'eq', True, 'Zagrał w fazie pucharowej głównego turnieju Worlds', 'Played in the Worlds main-event knockout stage'),
    ('deep_run', HARD, 'worlds_never_escaped', 'gte', 2, 'Min. 2 edycje Worlds, nigdy w fazie pucharowej głównego turnieju', 'At least 2 Worlds editions, never reached main-event knockouts'),
    ('elimination_stage', HARD, 'worlds_eliminated_stage', 'eq', 'play_in', 'Co najmniej raz odpadł w play-in Worlds', 'Eliminated in Worlds play-in at least once'),
    ('elimination_stage', MEDIUM, 'worlds_eliminated_stage', 'eq', 'group', 'Co najmniej raz odpadł w głównej fazie grupowej / Swiss Worlds', 'Eliminated in Worlds main-event groups or Swiss at least once'),
    ('elimination_stage', MEDIUM, 'worlds_eliminated_stage', 'eq', 'quarterfinal', 'Co najmniej raz odpadł w ćwierćfinale Worlds', 'Eliminated in Worlds quarterfinals at least once'),
    ('elimination_stage', HARD, 'worlds_eliminated_stage', 'eq', 'semifinal', 'Co najmniej raz odpadł w półfinale Worlds', 'Eliminated in Worlds semifinals at least once'),
    ('elimination_stage', HARD, 'worlds_eliminated_stage', 'eq', 'final', 'Przegrał finał Worlds', 'Lost a Worlds final'),
    ('no_title', MEDIUM, 'worlds_never_won', 'gte', 3, 'Min. 3 edycje Worlds, bez ani jednego tytułu', 'Played in at least 3 Worlds editions without winning a title'),
    ('playin', HARD, 'worlds_playin', 'eq', True, 'Awansował z play-in do głównego turnieju Worlds', 'Advanced from play-in to the Worlds main event'),
    ('penta', HARD, 'pentakill_worlds', 'gte', 1, 'Zdobył pentakill na Worlds', 'Pentakill at Worlds'),
    ('title', HARD, 'worlds_titles_exact', 'eq', 1, 'Wygrał Worlds dokładnie raz', 'Won Worlds exactly once'),
    ('title', HARD, 'worlds_title_on_debut', 'eq', True, 'Wygrał Worlds będąc debiutantem turnieju', 'Won Worlds on his first appearance at the tournament'),
    ('final', HARD, 'worlds_final_lost_to_faker', 'eq', True, 'Przegrał finał Worlds przeciwko Fakerowi', 'Lost a Worlds final to Faker'),
    ('masters', HARD, 'european_masters_played', 'eq', True, 'Zagrał w EU Masters / EMEA Masters', 'Played at EU / EMEA Masters'),
    ('masters', HARD, 'european_masters_won', 'eq', True, 'Wygrał EU Masters / EMEA Masters', 'Won EU / EMEA Masters'),
    ('msi', MEDIUM, 'msi_appearance', 'eq', True, 'Grał na MSI', 'Played at MSI'),

    # --- kariera ---
    ('status', EASY, 'active', 'eq', True, 'Wciąż aktywny', 'Still active'),
    ('status', EASY, 'active', 'eq', False, 'Zakończył karierę', 'Retired'),
    ('versatility', HARD, 'worlds_multi_role', 'gte', 2, 'Grał na Worlds na co najmniej 2 różnych pozycjach', 'Played at least 2 different roles at Worlds'),
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

# Existing boards keep their nationality-based validator and origin theme.
LEGACY_ORIGIN_THEMES = {('continent', 'Europe'): 'origin', ('continent', 'North America'): 'origin'}


def build_condition_pool(players=None, minimum=MIN_CANDIDATES):
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
         'Wygrał ponad 50% gier na Worlds (z play-in)', 'Won over 50% of his Worlds games (including play-in)'),
        ('worlds_win_rate', MEDIUM, 'worlds_win_rate', 'lt', 50,
         'Wygrał poniżej 50% gier na Worlds (z play-in)', 'Won under 50% of his Worlds games (including play-in)'),
    ]
    for threshold, greater_difficulty, less_difficulty in [
        (10, EASY, HARD), (25, EASY, MEDIUM), (50, MEDIUM, EASY), (100, HARD, EASY),
    ]:
        statistical.extend([
            ('worlds_games', greater_difficulty, 'worlds_games', 'gt', threshold,
             f'Ponad {threshold} gier na Worlds (z play-in)', f'Over {threshold} games at Worlds (including play-in)'),
            ('worlds_games', less_difficulty, 'worlds_games', 'lt', threshold,
             f'Poniżej {threshold} gier na Worlds (z play-in)', f'Under {threshold} games at Worlds (including play-in)'),
        ])

    champion_counts = {}
    for condition_type, property_name, facts_list, label_pl, label_en in [
        ('worlds_top5_champion', 'worlds_top5_champions', verified, 'na Worlds', 'at Worlds'),
        ('career_top5_champion', 'career_top5_champions', eligible, 'w karierze', 'in his career'),
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
                                f'{champion} w jego TOP 5 według liczby gier {label_pl}', f'{champion} in his top 5 champions by games played {label_en}'))

    for condition in statistical:
        if condition[2] in champion_counts:
            matching = champion_counts[condition[2]][_champion_name(condition[4])]
        else:
            matching = sum(evaluate_condition(player, *condition[2:5]) for player, _facts in verified)
        # A broad statistic can still form a valid intersection with another
        # theme; MAX_CANDIDATES applies to the completed slot, below.
        if matching >= minimum:
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
    champion_ranks = {'worlds_top5_champion', 'career_top5_champion'}
    if first[2] in champion_ranks and second[2] in champion_ranks:
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
    validate_slots(slots, daily.minimum_candidates, bool(daily.author_name.strip()))
    return daily


def validate_slots(slots, minimum_candidates=MIN_CANDIDATES, curated=False):
    """Shared publication and editor validation, including combined answers."""
    if [slot.role for slot in slots] != ROLE_ORDER:
        raise ValueError('Daily must contain five slots in the expected role order')
    themes = {condition[2]: condition[0] for condition in CONDITION_POOL}
    themes['continent'] = 'origin'
    themes.update(STAT_THEMES)
    for slot in slots:
        conditions = list(slot.conditions.all())
        if (not valid_requirement_count(conditions) or any(condition.condition_type == 'role' for condition in conditions)
                or (len(conditions) == 2 and not _independent_conditions(*[(themes.get(c.condition_type, c.condition_type), None,
                                                 c.condition_type, c.operator, c.value) for c in conditions]))):
            raise ValueError('Every slot must contain one demanding or two independent requirements')
    pools = [count_candidates(slot) for slot in slots]
    for slot, pool in zip(slots, pools):
        single = len(slot.conditions.all()) == 1
        minimum = 1 if curated else (max(MIN_CANDIDATES, minimum_candidates)
                    if minimum_candidates is not None else (3 if single else 8))
        maximum = MAX_CANDIDATES if curated or not single else single_candidate_limit(slot.conditions.all()[0].condition_type)
        if not minimum <= len(pool) <= maximum:
            raise ValueError(f'Slot {slot.role} needs {minimum}–{maximum} valid candidates')
        if not curated and minimum_candidates is not None and not single:
            conditions = list(slot.conditions.all())
            role_pool = _role_pool(slot.role)
            individual = [len(_candidates_for_conditions(slot.role,
                [(None, None, c.condition_type, c.operator, c.value)], role_pool)) for c in conditions]
            if len(pool) > 0.8 * min(individual):
                raise ValueError(f'Slot {slot.role}: each requirement must narrow the answers')
    if not _has_distinct_roster(pools):
        raise ValueError('Daily has no solution using five different players')
    return pools


def recent_themes(before_date, days=THEME_MEMORY_DAYS):
    """Motywy warunków użyte w ostatnich `days` dniach – żeby ich nie powtarzać."""
    since = before_date - timedelta(days=days)
    used = Counter()
    conditions = DailySlotCondition.objects.filter(
        slot__daily__date__gte=since, slot__daily__date__lt=before_date
    ).values_list('condition_type', 'value')
    by_type = dict(LEGACY_ORIGIN_THEMES)
    for theme, _diff, ctype, _op, value, _pl, _en in CONDITION_POOL:
        by_type.setdefault((ctype, str(value)), theme)
    for ctype, value in conditions:
        theme = STAT_THEMES.get(ctype) or by_type.get((ctype, str(value)))
        if theme:
            used[theme] += 1
    return used


def requirement_key(condition_type, operator, value):
    return condition_type, operator, json.dumps(value, sort_keys=True)


def recent_requirements(before_date, days=4):
    return Counter(requirement_key(*row) for row in DailySlotCondition.objects.filter(
        slot__daily__date__gte=before_date - timedelta(days=days), slot__daily__date__lt=before_date
    ).values_list('condition_type', 'operator', 'value'))


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


def generate_slot(daily, role, position, difficulty, rnd, used_themes, pool=None, condition_pool=None, board_themes=None, used_requirements=None):
    """Select a narrow standalone achievement or two materially useful clues."""
    pool = pool if pool is not None else _role_pool(role)
    if not pool:
        raise ValueError(f'No players available for role {role}')
    conditions = list(condition_pool if condition_pool is not None else build_condition_pool(pool))
    conditions = [c for c in conditions if c[2] != 'role']
    rnd.shuffle(conditions)
    # Champion clues share the same verified ranking. Parse that ranking once
    # per player, rather than once for every champion in the condition pool.
    champion_matches = {}
    for kind, property_name in [('worlds_top5_champion', 'worlds_top5_champions'),
                                 ('career_top5_champion', 'career_top5_champions')]:
        if not any(c[2] == kind and c[3] == 'eq' for c in conditions):
            continue
        index = defaultdict(set)
        for player in pool:
            facts = PlayerFacts(player)
            if facts.attr.get('worlds_verified') is False or role not in facts.roles:
                continue
            for champion in getattr(facts, property_name):
                index[_champion_name(champion)].add(player.pk)
        champion_matches[kind] = index
    matches = [champion_matches[c[2]].get(_champion_name(c[4]), set())
               if c[2] in champion_matches and c[3] == 'eq'
               else {p.pk for p in _candidates_for_conditions(role, [c], pool)} for c in conditions]
    quantitative = {'birth', 'worlds_games', 'worlds_win_rate', 'worlds_count'}
    options = []

    def remember(chosen, matching):
        n = len(matching)
        score = abs(n - 18) * 0.25
        # Count prior uses, so a saturated history still favours variety. Use
        # the average to avoid rewarding singles merely for having fewer clues.
        score += 2 * sum(used_themes.get(c[0], 0) if isinstance(used_themes, dict)
                         else int(c[0] in used_themes) for c in chosen) / len(chosen)
        score += sum(100 for c in chosen if c[0] in (board_themes or set()))
        score += 45 * sum((used_requirements or {}).get(requirement_key(*c[2:5]), 0) for c in chosen) / len(chosen)
        score += 3 if not any(c[1] == difficulty for c in chosen) else 0
        if len(chosen) == 1:
            score += 1
        options.append((score, chosen, matching))

    for i, c in enumerate(conditions):
        n = len(matches[i])
        if c[2] in SINGLE_REQUIREMENT_TYPES and MIN_CANDIDATES <= n <= min(single_candidate_limit(c[2]), len(pool) * 0.25):
            remember([c], matches[i])
    for first, second in combinations(range(len(conditions)), 2):
        chosen = [conditions[first], conditions[second]]
        if not _independent_conditions(*chosen):
            continue
        # An already specific champion clue needs no statistical filler. Keep
        # this editorial rule here so historical boards remain readable.
        kinds = {c[2] for c in chosen}
        if kinds & CHAMPION_RANK_TYPES and kinds & {'worlds_games', 'worlds_win_rate', 'birth_year_range'}:
            continue
        if all(c[0] in quantitative for c in chosen):
            continue
        matching = matches[first] & matches[second]
        n = len(matching)
        if not MIN_CANDIDATES <= n <= min(MAX_CANDIDATES, 50):
            continue
        # Neither clue may be merely implied by the other one.
        if n > 0.8 * min(len(matches[first]), len(matches[second])):
            continue
        remember(chosen, matching)
    if not options:
        raise ValueError(f'Cannot find independent requirements for {role}')
    best_score = min(row[0] for row in options)
    _score, chosen, matching = rnd.choice([row for row in options if row[0] <= best_score + 2])
    slot = DailySlot.objects.create(daily=daily, role=role, position=position,
                                   label_pl=role.capitalize(), label_en=role.capitalize())
    _write_conditions(slot, chosen)
    return slot, [p for p in pool if p.pk in matching]

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

    daily.minimum_candidates = MIN_CANDIDATES
    daily.save(update_fields=['minimum_candidates'])

    rnd = random.Random(f'{date}-{seed}')
    used_themes = recent_themes(date)
    used_requirements = recent_requirements(date)
    plan = list(DIFFICULTY_PLAN)
    rnd.shuffle(plan)

    theme_by_condition = {
        (ctype, str(value)): theme
        for theme, _d, ctype, _o, value, _pl, _en in CONDITION_POOL
    }

    candidate_pools = []
    board_themes = set()
    for position, (role, difficulty) in enumerate(zip(ROLE_ORDER, plan), start=1):
        pool = _role_pool(role)
        slot, candidates = generate_slot(daily, role, position, difficulty, rnd, used_themes, pool,
                                         board_themes=board_themes, used_requirements=used_requirements)
        candidate_pools.append(candidates)
        for cond in slot.conditions.all():
            theme = STAT_THEMES.get(cond.condition_type) or theme_by_condition.get((cond.condition_type, str(cond.value)))
            if theme:
                used_themes[theme] += 1
                board_themes.add(theme)

    if not _has_distinct_roster(candidate_pools):
        raise ValueError('No solution using five different players')
    return daily
