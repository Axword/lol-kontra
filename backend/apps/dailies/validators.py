"""
Condition evaluator – sprawdza, czy zawodnik spełnia warunki slotu.

v2.0 (2026-08-16)
  * rola slotu jest EGZEKWOWANA (wcześniej była tylko informacyjna),
  * nieznany typ warunku NIE przepuszcza gracza (wcześniej zwracał True),
  * brak danych = warunek niespełniony (wcześniej część warunków była "pobłażliwa"
    i po cichu przepuszczała wszystkich),
  * usunięte zaszyte listy mistrzów Worlds i reguła awaryjna dla trenerów,
  * ~30 typów warunków zamiast 15.

Źródłem prawdy są `Player.attributes` (JSONB) uzupełniane przez scraper. Oczekiwane klucze:

    worlds_appearances   [2015, 2016, 2017]   lata występów na Worlds
    worlds_titles        [2016]               lata wygranych Worlds
    worlds_finals        [2016, 2017]         lata gry w finale
    worlds_semifinals    [2015, 2016, 2017]   lata awansu do top 4
    worlds_group_escapes [2016, 2017]         lata wyjścia z fazy grupowej
    worlds_playin        [2019]               lata przejścia przez play-in
    worlds_teams         ["t1", "fnatic"]     organizacje reprezentowane na Worlds
    worlds_roles         ["mid", "adc"]       role, na których grał na Worlds
    teams                ["t1", ...]          pełna historia drużyn
    team_years           {"t1": [2013, 2014]} drużyna -> lata
    leagues              ["LCK", "LEC"]       ligi, w których występował
    coaches              ["kkoma"]            trenerzy
    msi_appearances      [2016, 2017]
    msi_titles           [2016]
    pentakills_worlds    2                    liczba pentakilli na Worlds

Warunki statystyk meczowych korzystają wyłącznie z Player.career_stats['worlds']:
games/wins/losses, complete=True, scope='worlds_including_play_in' oraz kompletna
lista champions z licznikami games/wins dla warunku top 5. Dane kariery ogólnej
nie zastępują brakujących statystyk Worlds.
"""
import logging
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.players.worlds_import import COUNTRIES

logger = logging.getLogger(__name__)

MAJOR_LEAGUES = {'lck', 'lpl', 'lec', 'lcs', 'eulcs', 'nalcs', 'lta', 'ltan', 'ltas'}
WILDCARD_LEAGUES = {'vcs', 'pcs', 'lms', 'lla', 'cblol', 'ljl', 'tcl', 'lco', 'opl', 'lcl', 'gpl'}

# Region ligi -> kraje uznawane za "miejscowe". Służy warunkowi "import".
LEAGUE_HOME_COUNTRIES = {
    'lck': {'kr'},
    'lpl': {'cn'},
    'lms': {'tw', 'hk', 'mo'},
    'pcs': {'tw', 'hk', 'mo', 'sg', 'my', 'ph', 'th', 'vn'},
    'vcs': {'vn'},
    'ljl': {'jp'},
    'tcl': {'tr'},
    'cblol': {'br'},
    'lla': {'mx', 'ar', 'cl', 'pe', 'co', 'ec'},
    'lco': {'au', 'nz'},
    'opl': {'au', 'nz'},
}
# Ligi regionalne, dla których "miejscowość" określa kontynent, a nie kraj.
LEAGUE_HOME_CONTINENTS = {
    'lec': 'europe',
    'eulcs': 'europe',
    'lcs': 'north america',
    'nalcs': 'north america',
}

TEAM_ALIASES = {
    'sktelecomt1': 't1', 'skt1': 't1', 'skt': 't1',
    'sktelecomt1k': 't1', 'sktelecomt12': 't1',
    'damwon': 'dwg', 'damwongaming': 'dwg', 'damwonkia': 'dwg',
    'dpluskia': 'dwg', 'dplus': 'dwg',
    'g2esports': 'g2',
    'edwardgaming': 'edg',
    'royalnevergiveup': 'rng',
    'jdgaming': 'jdg',
    'invictusgaming': 'ig',
    'geng': 'geng', 'gen.g': 'geng', 'genggaming': 'geng',
    'samsunggalaxy': 'ssg', 'samsungwhite': 'ssw', 'samsungblue': 'ssb',
    'topesports': 'tes',
    'billibilligaming': 'blg', 'bilibiligaming': 'blg',
    'weibogaming': 'wbg',
    'hanwhalifeesports': 'hle',
    'kt rolster': 'kt', 'ktrolster': 'kt',
    'cloud9': 'c9',
    'teamliquid': 'tl',
    'teamsololmid': 'tsm', 'tsmftx': 'tsm',
    'madlions': 'mad',
    'rogue': 'rge',
    'misfitsgaming': 'misfits',
    'splyce': 'splyce',
}

ROLE_ALIASES = {
    'toplane': 'top', 'toplaner': 'top',
    'jgl': 'jungle', 'jng': 'jungle', 'jg': 'jungle',
    'middle': 'mid', 'midlane': 'mid', 'midlaner': 'mid',
    'bot': 'adc', 'botlane': 'adc', 'ad carry': 'adc', 'adcarry': 'adc', 'marksman': 'adc',
    'sup': 'support', 'supp': 'support',
}


# --------------------------------------------------------------------------- #
#  Normalizacja
# --------------------------------------------------------------------------- #

def _slug(value: Any) -> str:
    if value is None:
        return ''
    text = str(value).lower().strip()
    text = re.sub(r'[^a-z0-9]+', '', text)
    return TEAM_ALIASES.get(text, text)


def _norm_role(value: Any) -> str:
    text = str(value or '').lower().strip()
    return ROLE_ALIASES.get(text, text)


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _team_tokens(raw_list) -> set:
    """Zamienia listę drużyn (stringi albo słowniki) na zbiór znormalizowanych slugów."""
    tokens = set()
    for item in _as_list(raw_list):
        if isinstance(item, dict):
            value = item.get('slug') or item.get('name') or item.get('team') or ''
        else:
            value = item
        slug = _slug(value)
        if slug:
            tokens.add(slug)
    return tokens


def _years(value) -> set:
    out = set()
    for item in _as_list(value):
        try:
            out.add(int(item))
        except (TypeError, ValueError):
            continue
    return out


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).lower() in ('true', '1', 'yes', 't', 'y')


def _as_int(value, default=None):
    if isinstance(value, dict):
        value = value.get('min', value.get('value', value.get('count')))
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _worlds_threshold(value, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        return None
    try:
        threshold = Decimal(str(value))
    except InvalidOperation:
        return None
    if not threshold.is_finite() or threshold < 0 or (maximum is not None and threshold > maximum):
        return None
    return threshold


def _compare_worlds(left, right, operator):
    return {
        'eq': left == right, 'gt': left > right, 'lt': left < right,
        'gte': left >= right, 'lte': left <= right,
    }.get(operator, False)


def _champion_name(value):
    """Normalize champion spelling without team aliases or substring matching."""
    if not isinstance(value, str):
        return ''
    text = unicodedata.normalize('NFKC', value).strip().casefold().replace('’', "'").replace('‘', "'")
    if not re.fullmatch(r"[a-z](?:[a-z .'&-]*[a-z])?", text):
        return ''
    return re.sub(r"[ .'\-]", '', text.replace('&', 'and'))


def _match_number(number, operator, value, minimum=False):
    if operator == 'any':
        return number > 0
    if operator == 'in':
        return number in _years(value)
    if isinstance(value, bool):
        return False
    target = _as_int(value)
    if target is None:
        return False
    if operator == 'gte' or (minimum and operator == 'eq'):
        return number >= target
    if operator == 'lte':
        return number <= target
    if operator == 'eq':
        return number == target
    return False


def _match_boolean(actual, operator, value, known=True):
    if operator == 'any':
        return bool(actual)
    if operator != 'eq' or not known or value not in (True, False, 0, 1, 'true', 'false', '1', '0'):
        return False
    return bool(actual) == _truthy(value)


def _match_event(years, operator, value, known=False, count=None):
    if operator == 'any':
        return bool(years) or bool(count)
    if isinstance(value, dict) and 'year' in value:
        value = value['year']
    if isinstance(value, bool) or str(value).lower() in ('true', 'false'):
        return _match_boolean(bool(years) or bool(count), operator, value, known or bool(years) or bool(count))
    if operator == 'in':
        return bool(years & _years(value))
    target = _as_int(value)
    if target is None:
        return False
    if operator == 'eq':
        return target in years
    if operator == 'lte':
        return any(year <= target for year in years)
    if operator == 'gte':
        return any(year >= target for year in years)
    return False


# --------------------------------------------------------------------------- #
#  Dostęp do danych zawodnika
# --------------------------------------------------------------------------- #

class PlayerFacts:
    """
    Cienka warstwa nad `Player.attributes`, żeby każdy warunek czytał dane tak samo
    i żeby brak danych był jawny (pusty zbiór), a nie przypadkowym `True`.
    """

    def __init__(self, player):
        self.player = player
        self.attr = player.attributes or {}

    # --- proste pola ---
    @property
    def country(self) -> str:
        return (self.player.country_code or '').lower()

    @property
    def continent(self) -> str:
        return (self.player.continent or '').lower()

    @property
    def birth_continent(self) -> str:
        country = self.attr.get('leaguepedia_country_of_birth')
        if not isinstance(country, str):
            return ''
        return COUNTRIES.get(country.strip().casefold(), ('', ''))[1].lower()

    @property
    def residency(self) -> str:
        return (self.player.residency or '').lower()

    @property
    def primary_role(self) -> str:
        return _norm_role(self.player.primary_role)

    @property
    def roles(self) -> set:
        roles = {self.primary_role} if self.primary_role else set()
        roles |= {_norm_role(r) for r in (self.player.secondary_roles or []) if r}
        return {r for r in roles if r}

    # --- listy z attributes ---
    @property
    def leagues(self) -> set:
        sourced = 'leagues_meta' in self.attr
        raw = self.attr.get('leagues')
        if sourced:
            meta = self.attr['leagues_meta']
            if (not isinstance(meta, dict) or meta.get('source') != 'Leaguepedia'
                    or meta.get('complete') is not True
                    or meta.get('scope') != 'leaguepedia_dated_league_appearances'
                    or not isinstance(raw, list) or any(not isinstance(value, str) or not value.strip() for value in raw)):
                return set()
        found = {_slug(l) for l in _as_list(raw) if l}
        # An explicit source-backed empty list must never resurrect stale seed
        # residency. Keep the old fallback only for fixtures without metadata.
        if not sourced and not found and self.residency:
            found = {_slug(self.residency)}
        aliases = {'eulcs': 'lec', 'nalcs': 'lcs'}
        return {aliases.get(l, l) for l in found if l}

    @property
    def teams(self) -> set:
        found = _team_tokens(self.attr.get('teams'))
        if not found:
            found = _team_tokens(self.attr.get('worlds_teams'))
        return found

    @property
    def team_years(self) -> dict:
        raw = self.attr.get('team_years') or {}
        if not isinstance(raw, dict):
            return {}
        return {_slug(k): _years(v) for k, v in raw.items()}

    @property
    def worlds_years(self) -> set:
        return _years(self.attr.get('worlds_appearances'))

    @property
    def worlds_count(self) -> int:
        years = self.worlds_years
        return len(years) if 'worlds_appearances' in self.attr else int(getattr(self.player, 'worlds_count', 0) or 0)

    @property
    def title_years(self) -> set:
        return _years(self.attr.get('worlds_titles'))

    @property
    def titles_count(self) -> int:
        years = self.title_years
        return len(years) if 'worlds_titles' in self.attr else int(getattr(self.player, 'worlds_titles_count', 0) or 0)

    @property
    def final_years(self) -> set:
        if 'worlds_finals' in self.attr:
            return _years(self.attr.get('worlds_finals'))
        # Legacy data did not distinguish an actual finals appearance from
        # belonging to the title-winning roster.
        return self.title_years

    @property
    def semifinal_years(self) -> set:
        return _years(self.attr.get('worlds_semifinals')) | self.final_years

    @property
    def group_escape_years(self) -> set:
        if 'worlds_group_escapes' in self.attr:
            return _years(self.attr.get('worlds_group_escapes'))
        return self.semifinal_years

    @property
    def playin_years(self) -> set:
        return _years(self.attr.get('worlds_playin'))

    @property
    def worlds_teams(self) -> set:
        return _team_tokens(self.attr.get('worlds_teams'))

    @property
    def worlds_roles(self) -> set:
        found = {_norm_role(r) for r in _as_list(self.attr.get('worlds_roles')) if r}
        return {r for r in found if r}

    @property
    def coaches(self) -> set:
        return {_slug(c) for c in _as_list(self.attr.get('coaches')) if c}

    @property
    def msi_years(self) -> set:
        return _years(self.attr.get('msi_appearances'))

    @property
    def pentakills_worlds(self) -> int:
        raw = self.attr.get('pentakills_worlds')
        if isinstance(raw, list):
            return len(raw)
        return _as_int(raw, 0) or 0

    def _stats_for(self, key, scope):
        career = getattr(self.player, 'career_stats', None)
        stats = career.get(key) if isinstance(career, dict) else None
        if not isinstance(stats, dict) or stats.get('complete') is not True:
            return None
        if stats.get('scope') != scope:
            return None
        if any(type(stats.get(field)) is not int or stats[field] < 0 for field in ('games', 'wins', 'losses')):
            return None
        if stats['games'] <= 0 or stats['wins'] + stats['losses'] != stats['games']:
            return None
        return stats

    @property
    def worlds_stats(self):
        """Verified game totals for the whole Worlds, including play-ins."""
        return self._stats_for('worlds', 'worlds_including_play_in')

    @property
    def career_stats(self):
        """Recorded Leaguepedia career games, independently checked at import."""
        stats = self._stats_for('career', 'leaguepedia_career')
        return stats if stats is not None and stats.get('source') == 'Leaguepedia' else None

    @staticmethod
    def _champions_for(stats):
        """All champions actually played in a complete, consistent breakdown."""
        if stats is None or not isinstance(stats.get('champions'), list):
            return []
        rows = []
        seen = set()
        games_sum = wins_sum = 0
        for champion in stats['champions']:
            if not isinstance(champion, dict):
                return []
            name = _champion_name(champion.get('champion'))
            games, wins = champion.get('games'), champion.get('wins')
            if (not name or name in seen or type(games) is not int or type(wins) is not int
                    or games < 0 or wins < 0 or wins > games):
                return []
            seen.add(name)
            games_sum += games
            wins_sum += wins
            if games:
                rows.append(champion)
        if games_sum != stats['games'] or wins_sum != stats['wins'] or not rows:
            return []
        return rows

    @property
    def worlds_champions(self):
        return self._champions_for(self.worlds_stats)

    @property
    def career_champions(self):
        return self._champions_for(self.career_stats)

    @staticmethod
    def _top_five(rows):
        """All ties at the fifth position count; zero-game rows never do."""
        rows = sorted(rows, key=lambda row: (-row['games'], _champion_name(row['champion'])))
        if not rows:
            return []
        cutoff = rows[min(4, len(rows) - 1)]['games']
        return [row['champion'] for row in rows if row['games'] >= cutoff]

    @property
    def worlds_top5_champions(self):
        return self._top_five(self.worlds_champions)

    @property
    def career_top5_champions(self):
        return self._top_five(self.career_champions)


# --------------------------------------------------------------------------- #
#  Warunki
# --------------------------------------------------------------------------- #

CONDITIONS = {}


def condition(name):
    def wrap(fn):
        CONDITIONS[name] = fn
        return fn
    return wrap


def _match_scalar(field: str, operator: str, value) -> bool:
    field = str(field or '').lower()
    if not field:
        return False
    if operator == 'in':
        return field in {str(v).lower() for v in _as_list(value)}
    if operator == 'any':
        return True
    return field == str(value).lower()


def _match_set(values: set, operator: str, value) -> bool:
    if not values:
        return False
    if operator == 'any':
        return True
    targets = {_slug(v) for v in _as_list(value)}
    targets = {t for t in targets if t}
    if not targets:
        return False
    if operator == 'in':
        return bool(values & targets)
    return bool(values & targets)


# --- podstawowe ---

@condition('role')
def _c_role(f, operator, value):
    if operator == 'any':
        return bool(f.roles)
    return bool(f.roles & {_norm_role(v) for v in _as_list(value)})


@condition('country')
def _c_country(f, operator, value):
    return _match_scalar(f.country, operator, value)


@condition('continent')
def _c_continent(f, operator, value):
    return _match_scalar(f.continent, operator, value)


@condition('birth_continent')
def _c_birth_continent(f, operator, value):
    return _match_scalar(f.birth_continent, operator, value)


@condition('active')
def _c_active(f, operator, value):
    return _match_boolean(f.player.is_active, operator, value,
                          known=f.attr.get('activity_verified') is not False)


@condition('residency')
@condition('region')
@condition('league')
def _c_league(f, operator, value):
    aliases = {'eulcs': 'lec', 'nalcs': 'lcs'}
    targets = [aliases.get(_slug(v), _slug(v)) for v in _as_list(value)]
    return _match_set(f.leagues, operator, targets)


@condition('team')
def _c_team(f, operator, value):
    return _match_set(f.teams, operator, value)


@condition('coach')
def _c_coach(f, operator, value):
    return _match_set(f.coaches, operator, value)


# --- Worlds: występy ---

@condition('worlds_win_rate')
def _c_worlds_win_rate(f, operator, value):
    stats = f.worlds_stats
    threshold = _worlds_threshold(value, maximum=100)
    if stats is None or threshold is None:
        return False
    # Integer cross multiplication keeps arbitrary decimal thresholds exact;
    # even a very close result cannot round to 50% or depend on Decimal context.
    numerator, denominator = threshold.as_integer_ratio()
    return _compare_worlds(stats['wins'] * 100 * denominator, stats['games'] * numerator, operator)


@condition('worlds_games')
def _c_worlds_games(f, operator, value):
    stats = f.worlds_stats
    threshold = _worlds_threshold(value)
    if stats is None or threshold is None:
        return False
    numerator, denominator = threshold.as_integer_ratio()
    return _compare_worlds(stats['games'] * denominator, numerator, operator)


@condition('worlds_top5_champion')
def _c_worlds_top5_champion(f, operator, value):
    name = _champion_name(value)
    return bool(operator == 'eq' and name and name in {_champion_name(champion) for champion in f.worlds_top5_champions})


@condition('career_top5_champion')
def _c_career_top5_champion(f, operator, value):
    name = _champion_name(value)
    return bool(operator == 'eq' and name and name in {_champion_name(champion) for champion in f.career_top5_champions})


@condition('worlds_eliminated_stage')
def _c_worlds_eliminated_stage(f, operator, value):
    # A recorded positive result remains useful when other seasons are missing.
    # Empty/unknown histories never prove a negative elimination claim.
    stages = {'play_in', 'group', 'quarterfinal', 'semifinal', 'final'}
    if operator != 'eq' or not isinstance(value, str) or value not in stages:
        return False
    history = f.attr.get('worlds_eliminations')
    years = history.get(value) if isinstance(history, dict) else None
    return isinstance(years, list) and any(type(year) is int and year >= 2011 for year in years)

@condition('worlds_appearance')
def _c_worlds_appearance(f, operator, value):
    if operator in ('gte', 'lte') and _as_int(value, 9999) < 1900:
        return _match_number(f.worlds_count, operator, value)
    return _match_event(f.worlds_years, operator, value,
                        known='worlds_appearances' in f.attr, count=f.worlds_count)


@condition('worlds_count_min')
def _c_worlds_count_min(f, operator, value):
    return _match_number(f.worlds_count, operator, value, minimum=True)


@condition('worlds_debut_year')
def _c_worlds_debut(f, operator, value):
    if not f.worlds_years:
        return False
    return _match_number(min(f.worlds_years), operator, value)


@condition('worlds_last_year')
def _c_worlds_last(f, operator, value):
    if not f.worlds_years:
        return False
    return _match_number(max(f.worlds_years), operator, value)


@condition('worlds_early_era')
def _c_worlds_early_era(f, operator, value):
    """Grał na Worlds w erze S1-S3 (2011-2013)."""
    return _match_boolean(bool(f.worlds_years & {2011, 2012, 2013}), operator, value,
                          known='worlds_appearances' in f.attr)


@condition('worlds_teams_min')
def _c_worlds_teams_min(f, operator, value):
    return bool(f.worlds_teams) and _match_number(len(f.worlds_teams), operator, value, minimum=True)


@condition('worlds_multi_role')
def _c_worlds_multi_role(f, operator, value):
    return bool(f.worlds_roles) and _match_number(len(f.worlds_roles), operator, value, minimum=True)


# --- Worlds: osiągnięcia ---

@condition('worlds_champion')
def _c_worlds_champion(f, operator, value):
    return _match_boolean(f.titles_count > 0, operator, value,
                          known='worlds_titles' in f.attr or f.titles_count > 0)


@condition('worlds_titles_min')
def _c_worlds_titles_min(f, operator, value):
    return ('worlds_titles' in f.attr or f.titles_count > 0) and _match_number(
        f.titles_count, operator, value, minimum=True)


@condition('worlds_final')
def _c_worlds_final(f, operator, value):
    return _match_event(f.final_years, operator, value, known='worlds_finals' in f.attr)


@condition('worlds_final_lost')
def _c_worlds_final_lost(f, operator, value):
    """Grał w finale, którego nie wygrał."""
    if 'worlds_titles' not in f.attr:
        return False
    return _match_event(f.final_years - f.title_years, operator, value, known='worlds_finals' in f.attr)


@condition('worlds_semifinal')
def _c_worlds_semifinal(f, operator, value):
    return _match_event(f.semifinal_years, operator, value, known='worlds_semifinals' in f.attr)


@condition('worlds_group_escape')
def _c_worlds_group_escape(f, operator, value):
    return _match_event(f.group_escape_years, operator, value, known='worlds_group_escapes' in f.attr)


@condition('worlds_never_escaped')
def _c_worlds_never_escaped(f, operator, value):
    """Nigdy nie wyszedł z fazy grupowej mimo co najmniej N występów."""
    return ('worlds_group_escapes' in f.attr and
            _match_number(f.worlds_count, operator, value, minimum=True) and not f.group_escape_years)


@condition('worlds_never_won')
def _c_worlds_never_won(f, operator, value):
    return ('worlds_titles' in f.attr and
            _match_number(f.worlds_count, operator, value, minimum=True) and f.titles_count == 0)


@condition('worlds_playin')
def _c_worlds_playin(f, operator, value):
    return _match_event(f.playin_years, operator, value, known='worlds_playin' in f.attr)


@condition('worlds_playin_appearance')
def _c_playin_appearance(f, operator, value):
    return _match_event(_years(f.attr.get('worlds_playin_appearances')), operator, value,
                        known='worlds_playin_appearances' in f.attr)


@condition('country_excluded')
def _c_country_excluded(f, operator, value):
    return operator == 'eq' and isinstance(value, str) and bool(f.country) and f.country != value.lower()


@condition('worlds_group_exit_before')
def _c_group_exit_before(f, operator, value):
    if operator != 'eq' or type(value) is not int or not 2012 <= value <= 2023:
        return False
    history = f.attr.get('worlds_eliminations')
    years = history.get('group') if isinstance(history, dict) else None
    return isinstance(years, list) and any(type(y) is int and 2011 <= y < value for y in years)


@condition('career_regions_min')
def _c_career_regions(f, operator, value):
    from .career_regions import career_regions
    known = career_regions(f.attr)
    return bool(known) and _match_number(len(known), operator, value, minimum=True)


@condition('worlds_titles_exact')
def _c_titles_exact(f, operator, value):
    return (operator == 'eq' and type(value) is int and value >= 0
            and f.attr.get('worlds_titles_verified') is True and f.titles_count == value)


@condition('worlds_title_on_debut')
def _c_title_on_debut(f, operator, value):
    won = bool(f.worlds_years and min(f.worlds_years) in f.title_years)
    return _match_boolean(won, operator, value, known=bool(f.worlds_years) and 'worlds_titles' in f.attr)


@condition('worlds_final_lost_to_faker')
def _c_final_lost_to_faker(f, operator, value):
    # Pinned from the verified Faker record in the October 2026 release.
    titles = {2013, 2015, 2016, 2023, 2024, 2025}
    lost = bool((f.final_years - f.title_years) & titles)
    return _match_boolean(lost, operator, value,
                          known='worlds_finals' in f.attr and 'worlds_titles' in f.attr)


def _masters_fact(f, key):
    data = f.attr.get('european_masters')
    return data.get(key) if isinstance(data, dict) and data.get('source') == 'Leaguepedia' else None


@condition('european_masters_played')
def _c_masters_played(f, operator, value):
    events = _masters_fact(f, 'played')
    return _match_boolean(bool(events), operator, value, known=isinstance(events, list))


@condition('european_masters_won')
def _c_masters_won(f, operator, value):
    events = _masters_fact(f, 'titles')
    return _match_boolean(bool(events), operator, value, known=isinstance(events, list))


@condition('pentakill_worlds')
def _c_pentakill(f, operator, value):
    extra = f.attr.get('additional_worlds_facts') or {}
    positive = extra.get('pentakills', 0) if isinstance(extra, dict) and extra.get('source') == 'Leaguepedia' else 0
    count = max(f.pentakills_worlds, positive) if type(positive) is int else f.pentakills_worlds
    return ('pentakills_worlds' in f.attr or count > 0) and _match_number(count, operator, value, minimum=True)


# --- MSI ---

@condition('msi_appearance')
def _c_msi(f, operator, value):
    return _match_event(f.msi_years, operator, value, known='msi_appearances' in f.attr)


# --- kariera i konteksty ---

@condition('team_year')
def _c_team_year(f, operator, value):
    """
    Grał w konkretnej drużynie w konkretnym roku.
    value: {"team": "fnatic", "year": 2018}
    """
    if not isinstance(value, dict):
        return False
    team = _slug(value.get('team'))
    year = _as_int(value.get('year'))
    if not team or year is None:
        return False
    return year in f.team_years.get(team, set())


@condition('leagues_min')
def _c_leagues_min(f, operator, value):
    """Występował w co najmniej N różnych ligach głównych."""
    return _match_number(len(f.leagues & MAJOR_LEAGUES), operator, value, minimum=True)


@condition('wildcard_region')
def _c_wildcard(f, operator, value):
    return _match_boolean(bool(f.leagues & WILDCARD_LEAGUES), operator, value, known=bool(f.leagues))


@condition('import_player')
def _c_import(f, operator, value):
    """
    Zawodnik grający poza swoim macierzystym regionem – np. Koreańczyk w Europie.
    Wymaga zarówno kraju, jak i ligi; brak danych = warunek niespełniony.
    """
    country = f.country
    if not f.leagues or not country:
        return False
    known = []
    for league in f.leagues:
        if league in LEAGUE_HOME_COUNTRIES:
            known.append(country not in LEAGUE_HOME_COUNTRIES[league])
        elif league in LEAGUE_HOME_CONTINENTS and f.continent:
            known.append(f.continent != LEAGUE_HOME_CONTINENTS[league])
    return _match_boolean(any(known), operator, value, known=bool(known))


@condition('birth_year_range')
def _c_birth_range(f, operator, value):
    year = f.player.birth_year
    if not year:
        return False
    if isinstance(value, dict):
        if operator != 'eq':
            return False
        minimum = _as_int(value.get('min', 1900))
        maximum = _as_int(value.get('max', 2100))
        return minimum is not None and maximum is not None and minimum <= year <= maximum
    return _match_number(year, operator, value)


@condition('champion_played')
def _c_champion(f, operator, value):
    career = getattr(f.player, 'career_stats', None)
    if isinstance(career, dict) and 'worlds' in career:
        # Playing at Worlds proves the positive career claim. These data cannot
        # prove that a player never played a champion elsewhere.
        if operator not in {'eq', 'in'}:
            return False
        played = {_champion_name(row['champion']) for row in f.worlds_champions}
        targets = _as_list(value) if operator == 'in' else [value]
        return bool(played & {_champion_name(champion) for champion in targets if _champion_name(champion)})
    # Deprecated compatibility for old fixtures without the Worlds schema;
    # production import removes the old favourite-champion field.
    champs = set()
    for item in _as_list(f.attr.get('top_champions_career')):
        name = item.get('champion') if isinstance(item, dict) else item
        slug = _slug(name)
        if slug:
            champs.add(slug)
    return _match_set(champs, operator, value)


# --------------------------------------------------------------------------- #
#  API modułu
# --------------------------------------------------------------------------- #

def evaluate_condition(player, condition_type: str, operator: str, value: Any) -> bool:
    attributes = getattr(player, 'attributes', None)
    if isinstance(attributes, dict) and attributes.get('worlds_verified') is False:
        return False
    handler = CONDITIONS.get(condition_type)
    if handler is None:
        # Świadomie restrykcyjnie: nieznany warunek nie może przepuszczać wszystkich,
        # bo wtedy slot przyjmuje dowolnego zawodnika.
        logger.warning('Nieznany typ warunku: %s', condition_type)
        return False
    operator = operator or 'eq'
    scalar_types = {'role', 'country', 'continent', 'birth_continent', 'residency', 'region', 'league', 'team', 'coach', 'champion_played'}
    boolean_types = {'active', 'worlds_champion', 'worlds_early_era', 'wildcard_region', 'import_player'}
    if condition_type in {'worlds_win_rate', 'worlds_games'}:
        allowed = {'eq', 'gt', 'lt', 'gte', 'lte'}
    elif condition_type in ('worlds_top5_champion', 'career_top5_champion', 'worlds_eliminated_stage'):
        allowed = {'eq'}
    else:
        allowed = {'eq', 'in', 'any'} if condition_type in scalar_types else (
            {'eq', 'any'} if condition_type in boolean_types else {'eq', 'in', 'gte', 'lte', 'any'})
    if operator not in allowed:
        return False
    if condition_type == 'team_year' and operator != 'eq':
        return False
    try:
        return bool(handler(PlayerFacts(player), operator, value))
    except Exception:
        logger.exception('Błąd oceny warunku %s (value=%r)', condition_type, value)
        return False


def player_matches_slot(player, slot) -> bool:
    """
    Zawodnik pasuje do slotu, gdy gra na roli slotu ORAZ spełnia wszystkie warunki.
    Rola jest twardym wymogiem – bez tego support przechodziłby na slocie topa.
    """
    facts = PlayerFacts(player)
    if isinstance(facts.attr, dict) and facts.attr.get('worlds_verified') is False:
        return False
    slot_role = _norm_role(slot.role)
    if not slot_role or slot_role not in facts.roles:
        return False

    conditions = list(slot.conditions.all())
    if not conditions:
        return False

    return all(
        evaluate_condition(player, c.condition_type, c.operator, c.value)
        for c in conditions
    )


def explain_slot_match(player, slot) -> dict:
    """Diagnostyka dla admina: który warunek odrzucił zawodnika."""
    facts = PlayerFacts(player)
    slot_role = _norm_role(slot.role)
    checks = [{
        'condition': 'worlds_verified',
        'value': True,
        'passed': not (isinstance(facts.attr, dict) and facts.attr.get('worlds_verified') is False),
    }, {
        'condition': 'role',
        'value': slot.role,
        'passed': bool(slot_role and slot_role in facts.roles),
    }]
    for c in slot.conditions.all():
        checks.append({
            'condition': c.condition_type,
            'value': c.value,
            'passed': evaluate_condition(player, c.condition_type, c.operator, c.value),
        })
    return {
        'player': player.nickname,
        'slot': slot.role,
        'matched': all(c['passed'] for c in checks),
        'checks': checks,
    }
