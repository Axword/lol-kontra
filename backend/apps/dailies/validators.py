"""
Condition evaluator – sprawdza czy Player spełnia warunki DailySlot
v1.1 – case-insensitive, team slug normalize, worlds_champion fallback
"""
from typing import Any
import re

def _slugify(s: str) -> str:
    if not s:
        return ''
    s = str(s).lower().strip()
    # remove spaces, special chars
    s = re.sub(r'[^a-z0-9]+', '', s)
    # common team aliases
    aliases = {
        'sktelecomt1': 't1',
        'skt1': 't1',
        'skt': 't1',
        'damwon': 'dwg',
        'damwonkia': 'dwg',
        'dpluskia': 'dwg',
        'dplus': 'dwg',
        'g2esports': 'g2',
        'fnatic': 'fnatic',
        'fntic': 'fnatic',
        't1': 't1',
        'edwardgaming': 'edg',
        'edg': 'edg',
        'royalnevergiveup': 'rng',
        'rng': 'rng',
        'jdgaming': 'jdg',
        'jdg': 'jdg',
        'invictusgaming': 'ig',
        'ig': 'ig',
        'gen.g': 'geng',
        'geng': 'geng',
        'samsunggalaxy': 'ssg',
        'samsungwhite': 'ssw',
        'samsungblue': 'ssb',
    }
    return aliases.get(s, s)

def _norm_list_str(lst):
    if not lst: return []
    out = []
    for x in lst:
        if isinstance(x, dict):
            # team dict
            v = x.get('slug') or x.get('name') or x.get('team') or ''
        else:
            v = str(x)
        out.append(_slugify(v))
        # also keep original lower
        out.append(v.lower().strip())
    return list(set([o for o in out if o]))

def evaluate_condition(player, condition_type: str, operator: str, value: Any) -> bool:
    attr = player.attributes or {}
    
    def get_list(key):
        v = attr.get(key, [])
        return v if isinstance(v, list) else []

    # normalize operator values to lower
    def norm_val(v):
        if isinstance(v, str):
            return v.lower()
        if isinstance(v, list):
            return [str(x).lower() for x in v]
        return v

    if condition_type == 'role':
        target = value if isinstance(value, str) else (value.get('role') if isinstance(value, dict) else '')
        target = str(target).lower()
        pr = (player.primary_role or '').lower()
        sec = [s.lower() for s in (player.secondary_roles or [])]
        return pr == target or target in sec

    if condition_type == 'residency' or condition_type == 'region' or condition_type == 'league':
        pv = (player.residency or '').lower()
        # also check leagues attribute
        leagues = [l.lower() for l in get_list('leagues')]
        target = norm_val(value)
        if operator == 'eq':
            return pv == target or target in leagues
        if operator == 'in' and isinstance(target, list):
            return pv in target or any(l in target for l in leagues)
        return False

    if condition_type == 'country':
        return _match_op((player.country_code or '').lower(), operator, norm_val(value))

    if condition_type == 'continent':
        return _match_op((player.continent or '').lower(), operator, norm_val(value))

    if condition_type == 'team':
        # collect teams from attributes – could be list of strings or dicts
        teams_raw = get_list('teams')
        teams_norm = _norm_list_str(teams_raw)
        # also try PlayerTeamHistory if empty
        if not teams_norm:
            try:
                # avoid N+1 in bulk – best effort
                th = getattr(player, 'team_history', None)
                if th:
                    teams_norm = _norm_list_str([t.team.slug if hasattr(t, 'team') else str(t) for t in th.all()[:10]])
            except Exception:
                pass
        target = norm_val(value)
        return _match_op_list(teams_norm, operator, target, slugify=True)

    if condition_type == 'league':
        leagues = [l.lower() for l in get_list('leagues')]
        # fallback to residency
        if not leagues and player.residency:
            leagues = [player.residency.lower()]
        return _match_op_list(leagues, operator, norm_val(value))

    if condition_type == 'worlds_appearance':
        appearances = get_list('worlds_appearances')
        # fallback: worlds_count >0
        if not appearances and getattr(player, 'worlds_count', 0) > 0:
            return True
        if operator == 'any':
            return len(appearances) > 0 or getattr(player, 'worlds_count', 0) > 0
        if isinstance(value, dict) and 'year' in value:
            return value['year'] in appearances
        if operator == 'gte':
            try:
                return len(appearances) >= int(value)
            except Exception:
                return False
        return len(appearances) > 0

    if condition_type == 'worlds_champion':
        titles = get_list('worlds_titles')
        # FALLBACK: if no titles data in DB (scraper v1), use heuristic:
        # worlds_titles_count >0 OR known champions list
        if not titles:
            if getattr(player, 'worlds_titles_count', 0) > 0:
                return _truthy(value)
            # hard-coded fallback list of ~30 Worlds winners – helps until DB is enriched
            champs = {
                'faker','bengi','wolf','bang','duke','marin','easyhoon','tom','blank','untara',
                'cuvee','ambition','crown','ruler','corejj','haru',
                'theshy','ning','rookie','jackeylove','baolan','duke',
                'doinb','tian','lwx','crisp','gimgoon',
                'canyon','showmaker','ghost','beryl','nuguri',
                'scout','viper','meiko','flandre','edward','jiejie',
                'zeus','oner','gumayusi','keria',
                'deft','pyosik','zeka','kingen','beryl',
                'ruler','kanavi','knight','369','missing','bin','elk','on'
            }
            is_champ = player.slug.lower() in champs or player.nickname.lower() in champs
            return is_champ if _truthy(value) else not is_champ
        has_title = len(titles) > 0
        return has_title if _truthy(value) else not has_title

    if condition_type == 'worlds_titles_min':
        titles = get_list('worlds_titles')
        cnt = len(titles) if titles else getattr(player, 'worlds_titles_count', 0)
        try:
            return cnt >= int(value)
        except Exception:
            return False

    if condition_type == 'msi_appearance':
        msi = get_list('msi_appearances')
        return len(msi) > 0

    if condition_type == 'coach':
        coaches = [str(c).lower() for c in get_list('coaches')]
        # always allow kkoma as test – many players missing coach data in v1 DB
        target = str(value).lower()
        if operator == 'in' and isinstance(value, list):
            target_list = [str(v).lower() for v in value]
            return any(t in coaches for t in target_list) or ('kkoma' in target_list)  # fallback for demo
        # permissive fallback: if no coach data in DB, accept if player is KR + worlds_count>2 (likely coached by kkoma at some point)
        if not coaches and target in ['kkoma','kkom a','k k o m a']:
            return (player.residency or '').upper() in ['LCK','KR'] and getattr(player, 'worlds_count', 0) >= 1
        return target in coaches or any(target in c for c in coaches)

    if condition_type == 'champion_played':
        champs = []
        for ch in attr.get('top_champions_career', []):
            if isinstance(ch, dict):
                champs.append(str(ch.get('champion','')).lower())
            else:
                champs.append(str(ch).lower())
        target = str(value).lower()
        # if no champion data – be permissive for demo (allow)
        if not champs or champs == ['']:
            return True
        return target in champs

    if condition_type == 'active':
        return player.is_active == _truthy(value)

    if condition_type == 'birth_year_range':
        if not player.birth_year:
            return True  # permissive if no data
        if isinstance(value, dict):
            min_y = value.get('min', 1900)
            max_y = value.get('max', 2100)
            return min_y <= player.birth_year <= max_y
        return False

    # unknown condition – be permissive in dev to avoid blocking gameplay
    return True


def player_matches_slot(player, slot) -> bool:
    conditions = list(slot.conditions.all())
    if not conditions:
        return False
    failed = []
    for cond in conditions:
        ok = evaluate_condition(player, cond.condition_type, cond.operator, cond.value)
        if not ok:
            failed.append(cond.condition_type)
    if failed:
        return False
    # role check – soft: allow if primary or secondary matches, else still allow if no role condition explicitly failed
    # (keeps gameplay forgiving while data is being enriched)
    r = slot.role.lower()
    pr = (player.primary_role or '').lower()
    sec = [s.lower() for s in (player.secondary_roles or [])]
    if pr and pr != r and r not in sec:
        # soft fail – still allow 30% of the time to avoid empty slots in dev?
        # Actually: for now allow – role is informational
        pass
    return True


def _match_op(field_value, operator, value):
    fv = str(field_value).lower()
    if operator == 'eq':
        return fv == str(value).lower()
    if operator == 'in':
        if isinstance(value, list):
            return fv in [str(v).lower() for v in value]
        return fv == str(value).lower()
    if operator == 'gte':
        try:
            return float(fv) >= float(value)
        except Exception:
            return False
    if operator == 'lte':
        try:
            return float(fv) <= float(value)
        except Exception:
            return False
    if operator == 'any':
        return bool(fv)
    return False


def _match_op_list(field_list, operator, value, slugify=False):
    # field_list already normalized lower
    fl = [str(x).lower() for x in field_list if x]
    if slugify:
        # also add slugified versions
        import re
        fl_extra = [re.sub(r'[^a-z0-9]', '', x) for x in fl]
        fl = list(set(fl + fl_extra))
    if operator == 'eq':
        target = str(value).lower()
        target_s = _slugify(target)
        return target in fl or target_s in fl
    if operator == 'in':
        target_list = value if isinstance(value, list) else [value]
        target_list = [str(t).lower() for t in target_list]
        target_list_s = [_slugify(t) for t in target_list]
        return any(t in fl for t in target_list) or any(t in fl for t in target_list_s)
    if operator == 'any':
        return len(fl) > 0
    return False


def _truthy(v):
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    return str(v).lower() in ('true', '1', 'yes', 't', 'y')
