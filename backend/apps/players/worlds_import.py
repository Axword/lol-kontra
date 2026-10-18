"""Validate an offline Leaguepedia snapshot and build identity-preserving fixtures.

No network, model imports, database writes, or clock-dependent defaults belong
here. ``complete`` requires the supplied snapshot to match independent physical
game counts up to ``as_of``; the fetcher must obtain that coverage separately.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import ast
import html
import re
import unicodedata

from django.utils.text import slugify
from unidecode import unidecode


ROLES = ('top', 'jungle', 'mid', 'adc', 'support')
ROLE_ALIASES = {'jng': 'jungle', 'jgl': 'jungle', 'jg': 'jungle', 'middle': 'mid',
                'bot': 'adc', 'ad carry': 'adc', 'adcarry': 'adc', 'sup': 'support', 'supp': 'support'}
SOURCE_PAGE_KEYS = ('leaguepedia_page', 'source_page', 'leaguepedia_source_page')

# Explicit country names/codes only. Unrecognized input stays unknown.
COUNTRIES = {}
for _continent, _countries in {
    'Asia': 'KR:South Korea|CN:China|TW:Taiwan|HK:Hong Kong|MO:Macau|JP:Japan|VN:Vietnam|TH:Thailand|SG:Singapore|MY:Malaysia|PH:Philippines|ID:Indonesia|IN:India|PK:Pakistan|BD:Bangladesh|MN:Mongolia|KZ:Kazakhstan|UZ:Uzbekistan|SA:Saudi Arabia|AE:United Arab Emirates|QA:Qatar|IL:Israel|IR:Iran|IQ:Iraq|JO:Jordan|LB:Lebanon|GE:Georgia|AM:Armenia|AZ:Azerbaijan',
    'Europe': 'DK:Denmark|SE:Sweden|NO:Norway|FI:Finland|IS:Iceland|GB:United Kingdom|IE:Ireland|FR:France|DE:Germany|PL:Poland|ES:Spain|PT:Portugal|IT:Italy|NL:Netherlands|BE:Belgium|LU:Luxembourg|CH:Switzerland|AT:Austria|CZ:Czech Republic|SK:Slovakia|HU:Hungary|RO:Romania|BG:Bulgaria|GR:Greece|HR:Croatia|SI:Slovenia|RS:Serbia|BA:Bosnia and Herzegovina|ME:Montenegro|MK:North Macedonia|AL:Albania|XK:Kosovo|EE:Estonia|LV:Latvia|LT:Lithuania|UA:Ukraine|BY:Belarus|MD:Moldova|RU:Russia|TR:Turkey|CY:Cyprus|MT:Malta',
    'North America': 'US:United States|CA:Canada|MX:Mexico|CR:Costa Rica|PA:Panama|GT:Guatemala|HN:Honduras|SV:El Salvador|NI:Nicaragua|BZ:Belize|CU:Cuba|DO:Dominican Republic|PR:Puerto Rico|JM:Jamaica',
    'South America': 'BR:Brazil|AR:Argentina|CL:Chile|PE:Peru|CO:Colombia|EC:Ecuador|UY:Uruguay|PY:Paraguay|BO:Bolivia|VE:Venezuela',
    'Oceania': 'AU:Australia|NZ:New Zealand|FJ:Fiji',
    'Africa': 'ZA:South Africa|EG:Egypt|MA:Morocco|DZ:Algeria|TN:Tunisia|NG:Nigeria|KE:Kenya|GH:Ghana',
}.items():
    for _country in _countries.split('|'):
        _code, _name = _country.split(':', 1)
        COUNTRIES[_code.casefold()] = (_code, _continent)
        COUNTRIES[_name.casefold()] = (_code, _continent)
for _alias, _code in {'korea': 'KR', 'republic of korea': 'KR', 'korea, republic of': 'KR',
                      'south korea': 'KR', 'vietnam': 'VN', 'viet nam': 'VN',
                      'czechia': 'CZ', 'usa': 'US', 'united states of america': 'US',
                      'uk': 'GB', 'great britain': 'GB', 'england': 'GB',
                      'turkiye': 'TR', 'türkiye': 'TR', 'macao': 'MO',
                      'russian federation': 'RU', 'chinese taipei': 'TW'}.items():
    COUNTRIES[_alias] = COUNTRIES[_code.casefold()]

RESIDENCIES = {value.casefold(): value for value in (
    'LCK', 'LPL', 'LEC', 'LCS', 'LMS', 'PCS', 'LCP', 'LTA', 'VCS', 'LJL', 'TCL',
    'CBLOL', 'LLA', 'LCL', 'LCO', 'OPL', 'GPL', 'EU LCS', 'NA LCS',
)}
# Riot's official residency regions (Americas, EMEA, SEA, etc.) are not proof of
# participation in one particular league. Preserve existing historical league
# codes and store the source region separately instead of inferring a league.


def _text(value):
    if value is None:
        return ''
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return ''
    value = str(value)
    for _ in range(3):
        decoded = html.unescape(value)
        if decoded == value:
            break
        value = decoded
    return ' '.join(unicodedata.normalize('NFKC', value).split())


def _key(value):
    # MediaWiki treats spaces and underscores in titles equivalently. Do not
    # discard disambiguation, punctuation or accents and thereby merge people.
    return _text(value).replace('_', ' ').casefold()


def _timestamp(value, label):
    text = _text(value)
    try:
        result = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError as error:
        raise ValueError(f'{label}: invalid ISO timestamp {text!r}') from error
    # Cargo's DateTime_UTC sometimes omits the explicit timezone suffix.
    return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)


def _boolean(value):
    if isinstance(value, bool):
        return value
    text = _text(value).casefold()
    if text in ('yes', 'true', '1'):
        return True
    if text in ('no', 'false', '0'):
        return False
    return None


def _role(value):
    text = _text(value).casefold()
    text = ROLE_ALIASES.get(text, text)
    return text if text in ROLES else ''


def _list(value):
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value] if value not in (None, '') else []


def _favorite_champions(value):
    if isinstance(value, str):
        text = _text(value)
        if text.startswith(('[', '(')):
            try:
                value = ast.literal_eval(text)
            except (ValueError, SyntaxError) as error:
                raise ValueError('Malformed favorite_champions list') from error
            if not isinstance(value, (list, tuple)):
                raise ValueError('favorite_champions must contain a list')
        else:
            value = re.split(r'[,;]', text)
    names = [_text(item.get('champion') if isinstance(item, dict) else item) for item in _list(value)]
    return sorted({name for name in names if name}, key=str.casefold)


def _year(value, label):
    text = _text(value)
    if not re.fullmatch(r'\d{4}', text):
        raise ValueError(f'{label}: invalid year {value!r}')
    return int(text)


def _worlds_year(page):
    early = re.fullmatch(r'Season ([123]) World Championship', page)
    if early:
        return 2010 + int(early[1])
    main = re.fullmatch(r'(\d{4}) Season World Championship(?:/(Main Event|Play-In))?', page)
    if not main:
        raise ValueError(f'Not an official Worlds main event or play-in: {page!r}')
    year = int(main[1])
    if not (2014 <= year <= 2016 and main[2] is None or year >= 2017 and main[2]):
        raise ValueError(f'Unexpected Worlds stage: {page!r}')
    return year


def _base_slug(page):
    return slugify(unidecode(page), allow_unicode=False)[:80]


def _unique_slug(page, used):
    base = _base_slug(page)
    if base and base.casefold() not in used:
        return base
    digest = sha256(page.encode('utf-8')).hexdigest()
    for length in range(10, 65, 4):
        suffix = digest[:length]
        candidate = f'{(base or "player")[:79 - len(suffix)]}-{suffix}'
        if candidate.casefold() not in used:
            return candidate
    raise ValueError(f'Cannot assign a unique slug for {page!r}')


def build_worlds_players(snapshot, existing_records):
    """Return ``(flat_fixture_rows, coverage_report)`` or raise on unsafe data.

    Input rows use the fetcher's normalized schema, not raw Cargo field names.
    Identical repeated rows are harmless pagination overlap. Every conflicting
    duplicate or incomplete game rejects the whole import before any mutation.
    """
    if not isinstance(snapshot, dict) or not isinstance(existing_records, (list, tuple)):
        raise ValueError('Expected a snapshot object and existing fixture list')
    as_of = _text(snapshot.get('as_of'))
    cutoff = _timestamp(as_of, 'as_of')
    for name in ('tournaments', 'rows', 'aliases', 'players'):
        if not isinstance(snapshot.get(name), list) or not all(isinstance(row, dict) for row in snapshot[name]):
            raise ValueError(f'{name}: expected a list of objects')
    if not snapshot['rows']:
        raise ValueError('An empty snapshot cannot prove Worlds completeness')

    tournaments = {}
    for row in snapshot['tournaments']:
        page = _text(row.get('OverviewPage'))
        year = _year(row.get('Year'), page)
        if _worlds_year(page) != year:
            raise ValueError(f'{page}: inconsistent tournament year')
        if page in tournaments and tournaments[page] != year:
            raise ValueError(f'{page}: conflicting tournament metadata')
        tournaments[page] = year

    expected = snapshot.get('expected_game_counts')
    if not isinstance(expected, dict):
        raise ValueError('expected_game_counts: an independent coverage map is required')
    for page, count in expected.items():
        if page not in tournaments or type(count) is not int or count < 0:
            raise ValueError(f'expected_game_counts: invalid tournament or game count for {page!r}')

    metadata = {}
    for row in snapshot['players']:
        page = _text(row.get('page'))
        if not page:
            raise ValueError('Player metadata has no canonical page')
        key = _key(page)
        if key in metadata and metadata[key] != row:
            raise ValueError(f'{page}: conflicting player metadata')
        metadata[key] = deepcopy(row)

    aliases = {}
    canonical_pages = {key: _text(row['page']) for key, row in metadata.items()}
    for row in snapshot['aliases']:
        alias, page = _key(row.get('alias')), _text(row.get('page'))
        if not alias or not page:
            raise ValueError('Alias requires both alias and canonical page')
        canonical = canonical_pages.get(_key(page), page)
        if alias in aliases and _key(aliases[alias]) != _key(canonical):
            raise ValueError(f'{row["alias"]}: ambiguous alias')
        if alias in canonical_pages and alias != _key(canonical):
            raise ValueError(f'{row["alias"]}: alias conflicts with a canonical player page')
        aliases[alias] = canonical
        canonical_pages.setdefault(_key(canonical), canonical)

    def resolve(value):
        key = _key(value)
        if key in aliases:
            return aliases[key]
        if key in canonical_pages:
            return canonical_pages[key]
        raise ValueError(f'Unknown Leaguepedia player alias: {_text(value)!r}')

    unique = {}
    duplicates = 0
    for index, raw in enumerate(snapshot['rows']):
        page = resolve(raw.get('player'))
        game_id = _text(raw.get('game_id'))
        champion, team = _text(raw.get('champion')), _text(raw.get('team'))
        tournament = _text(raw.get('tournament'))
        date = _timestamp(raw.get('date'), f'row {index} date')
        win = _boolean(raw.get('win'))
        if not game_id or not champion or not team or win is None:
            raise ValueError(f'row {index}: missing game, champion, team or unrecognized result')
        if tournament not in tournaments:
            raise ValueError(f'row {index}: tournament outside the supplied Worlds whitelist')
        if date >= cutoff or date.year != tournaments[tournament]:
            raise ValueError(f'row {index}: date outside the tournament year/as_of cutoff')
        pentakills = raw.get('pentakills')
        if pentakills is not None and pentakills != '':
            text = _text(pentakills)
            if not re.fullmatch(r'\d+', text):
                raise ValueError(f'row {index}: invalid pentakills')
            pentakills = int(text)
        else:
            pentakills = None
        row = {'page': page, 'game_id': game_id, 'champion': champion, 'team': team,
               'tournament': tournament, 'date': date, 'win': win,
               'role': _role(raw.get('role')), 'ingame_role': _role(raw.get('ingame_role')),
               'pentakills': pentakills}
        identity = (game_id, _key(page))
        if identity in unique:
            if unique[identity] != row:
                raise ValueError(f'{game_id}/{page}: conflicting duplicate player row')
            duplicates += 1
        else:
            unique[identity] = row

    games = defaultdict(list)
    player_rows = defaultdict(list)
    for row in unique.values():
        games[row['game_id']].append(row)
        player_rows[_key(row['page'])].append(row)
    for game_id, rows in games.items():
        teams = defaultdict(list)
        for row in rows:
            teams[row['team']].append(row['win'])
        if (len(rows) != 10 or len(teams) != 2 or sum(row['win'] for row in rows) != 5
                or any(len(results) != 5 or len(set(results)) != 1 for results in teams.values())
                or len({(row['date'], row['tournament']) for row in rows}) != 1):
            raise ValueError(f'{game_id}: expected 10 players, two coherent five-player teams and five wins')

    actual = Counter(rows[0]['tournament'] for rows in games.values())
    missing_coverage = set(actual) - set(expected)
    if missing_coverage:
        raise ValueError(f'expected_game_counts: missing coverage for {sorted(missing_coverage)!r}')
    for page, count in expected.items():
        if actual[page] != count:
            raise ValueError(f'{page}: coverage mismatch, expected {count} unique games, got {actual[page]}')

    existing = deepcopy(list(existing_records))
    by_slug, by_page = {}, {}
    for index, record in enumerate(existing):
        if not isinstance(record, dict) or not _text(record.get('slug')):
            raise ValueError('Existing fixtures require a nonempty slug')
        slug_key = _text(record['slug']).casefold()
        if slug_key in by_slug:
            raise ValueError(f'{record["slug"]}: duplicate existing slug')
        by_slug[slug_key] = index
        attrs = record.get('attributes')
        attrs = {} if attrs is None else attrs
        career = record.get('career_stats')
        if not isinstance(attrs, dict) or career is not None and not isinstance(career, dict):
            raise ValueError(f'{record["slug"]}: malformed existing attributes/statistics')
        pages = {_key(record.get(key) or attrs.get(key)) for key in SOURCE_PAGE_KEYS if record.get(key) or attrs.get(key)}
        pages = {_key(aliases.get(page, canonical_pages.get(page, page))) for page in pages}
        if len(pages) > 1:
            raise ValueError(f'{record["slug"]}: conflicting existing source pages')
        for page in pages:
            if page in by_page:
                raise ValueError(f'{page}: multiple existing player identities')
            by_page[page] = index

    def migrate_favorites(record):
        attrs = record.setdefault('attributes', {})
        old = attrs.pop('top_champions_career', None)
        if old and 'favorite_champions' not in attrs:
            attrs['favorite_champions'] = _favorite_champions(old)

    for record in existing:
        if record.get('attributes') is None:
            record['attributes'] = {}
        if record.get('career_stats') is None:
            record['career_stats'] = {}
        migrate_favorites(record)

    used_slugs = set(by_slug)
    base_counts = Counter(_base_slug(page).casefold() for page in canonical_pages.values())
    matched = set()
    unknown = defaultdict(list)
    missing_pages = []
    new_records = []
    for page_key in sorted(player_rows):
        rows = player_rows[page_key]
        page = canonical_pages[page_key]
        meta = metadata.get(page_key, {})
        if not meta:
            missing_pages.append(page)
        index = by_page.get(page_key)
        base = _base_slug(page).casefold()
        if index is None and base_counts[base] == 1 and base in by_slug:
            candidate = by_slug[base]
            # A source page is stronger evidence than a coincidentally equal slug.
            if candidate not in by_page.values():
                index = candidate
        if index is not None:
            if index in matched:
                raise ValueError(f'{page}: existing identity would be assigned twice')
            matched.add(index)
            record = existing[index]
        else:
            slug = _unique_slug(page, used_slugs)
            used_slugs.add(slug.casefold())
            record = {'slug': slug, 'attributes': {}, 'career_stats': {}, 'worlds_titles_count': 0}
            new_records.append(record)
        attrs = record.setdefault('attributes', {})
        career = record.setdefault('career_stats', {})
        attrs['leaguepedia_page'] = page
        attrs['worlds_verified'] = True
        years = sorted({tournaments[row['tournament']] for row in rows})
        attrs['worlds_appearances'] = years
        record['worlds_count'] = len(years)
        teams = sorted({row['team'] for row in rows}, key=str.casefold)
        attrs['worlds_teams'] = teams
        team_years = {team: sorted({tournaments[row['tournament']] for row in rows if row['team'] == team}) for team in teams}
        attrs['worlds_team_years'] = team_years
        attrs['teams'] = list(attrs.get('teams') or []) + [team for team in teams if team not in (attrs.get('teams') or [])]
        history = deepcopy(attrs.get('team_years') or {})
        if not isinstance(history, dict):
            raise ValueError(f'{page}: malformed existing team_years')
        for team, values in team_years.items():
            old_years = {_year(year, f'{page}/{team} history') for year in _list(history.get(team))}
            history[team] = sorted(old_years | set(values))
        attrs['team_years'] = history
        roles = Counter(row['ingame_role'] or row['role'] for row in rows if row['ingame_role'] or row['role'])
        attrs['worlds_roles'] = sorted(roles, key=ROLES.index)
        playin = {(tournaments[row['tournament']], row['team']) for row in rows if row['tournament'].endswith('/Play-In')}
        main = {(tournaments[row['tournament']], row['team']) for row in rows if row['tournament'].endswith('/Main Event')}
        attrs['worlds_playin_appearances'] = sorted({year for year, _team in playin})
        attrs['worlds_playin'] = sorted({year for year, _team in playin & main})

        country_of_birth = _text(meta.get('country'))
        nationality = _text(meta.get('nationality_primary') or meta.get('NationalityPrimary'))
        attrs['leaguepedia_country_of_birth'] = country_of_birth
        if nationality:
            attrs['leaguepedia_nationality_primary'] = nationality
        else:
            attrs.pop('leaguepedia_nationality_primary', None)
        country, continent = COUNTRIES.get((nationality or country_of_birth).casefold(), ('', ''))
        source_residency = _text(meta.get('residency'))
        residency = _text(record.get('residency')) or RESIDENCIES.get(source_residency.casefold(), '')
        attrs['leaguepedia_residency'] = source_residency
        retired = _boolean(meta.get('retired'))
        birth_year = None
        birth = _text(meta.get('birthdate'))
        if re.fullmatch(r'\d{4}(?:-\d{2}-\d{2})?', birth):
            try:
                born = datetime.fromisoformat(birth if len(birth) > 4 else birth + '-01-01')
                if 1900 <= born.year <= cutoff.year:
                    birth_year = born.year
            except ValueError:
                pass
        nickname, real_name = _text(meta.get('id')), _text(meta.get('name'))
        metadata_role = _role(meta.get('role'))
        primary = metadata_role or (sorted(roles, key=lambda role: (-roles[role], ROLES.index(role)))[0] if roles else '')
        historical_roles = {_role(role) for role in _list(record.get('secondary_roles')) + [record.get('primary_role')]}
        record.update(nickname=nickname or page, real_name=real_name, country_code=country,
                      continent=continent, residency=residency, birth_year=birth_year,
                      is_active=not retired if retired is not None else False,
                      primary_role=primary, secondary_roles=sorted((set(roles) | historical_roles) - {primary, ''}, key=ROLES.index))
        attrs['country'] = country
        attrs['activity_verified'] = retired is not None
        if 'favorite_champions' in meta:
            attrs['favorite_champions'] = _favorite_champions(meta.get('favorite_champions'))
        for field, known in {'country': country, 'residency': source_residency, 'birthdate': birth_year,
                             'activity': retired is not None, 'nickname': nickname,
                             'real_name': real_name, 'role': metadata_role}.items():
            if not known:
                unknown[field].append(page)

        champions = defaultdict(lambda: {'games': 0, 'wins': 0})
        for row in rows:
            champions[row['champion']]['games'] += 1
            champions[row['champion']]['wins'] += int(row['win'])
        wins = sum(row['win'] for row in rows)
        career['worlds'] = {'games': len(rows), 'wins': wins, 'losses': len(rows) - wins,
                            'champions': sorted(({'champion': champion, **counts} for champion, counts in champions.items()),
                                                key=lambda row: (-row['games'], row['champion'].casefold())),
                            'complete': True, 'scope': 'worlds_including_play_in', 'source': 'Leaguepedia', 'as_of': as_of}
        if all(row['pentakills'] is not None for row in rows):
            attrs['pentakills_worlds'] = sum(row['pentakills'] for row in rows)
            attrs['pentakills_worlds_verified'] = True
        else:
            attrs.pop('pentakills_worlds', None)
            attrs['pentakills_worlds_verified'] = False

    for index, record in enumerate(existing):
        if index not in matched:
            record['attributes'].update(worlds_verified=False, worlds_appearances=[])
            record['worlds_count'] = 0
            career = record.get('career_stats') or {}
            if isinstance(career.get('worlds'), dict):
                career['worlds']['complete'] = False
    fixtures = sorted(existing + new_records, key=lambda row: (_text(row.get('nickname')).casefold(), row['slug']))
    report = {'source': 'Leaguepedia', 'scope': 'worlds_including_play_in', 'as_of': as_of,
              'coverage_verified': True, 'expected_games': sum(expected.values()),
              'input_rows': len(snapshot['rows']), 'unique_rows': len(unique), 'duplicate_rows': duplicates,
              'games': len(games), 'confirmed_players': len(player_rows), 'complete_players': len(player_rows),
              'existing_records': len(existing), 'new_players': len(new_records),
              'preserved_unverified_players': len(existing) - len(matched),
              'metadata_missing_pages': sorted(missing_pages),
              'unknown_metadata': {field: sorted(values) for field, values in sorted(unknown.items())},
              'tournaments': [{'page': page, 'year': year,
                               'games': sum(rows[0]['tournament'] == page for rows in games.values()),
                               'player_rows': sum(row['tournament'] == page for row in unique.values())}
                              for page, year in sorted(tournaments.items(), key=lambda item: (item[1], item[0]))]}
    return fixtures, report
