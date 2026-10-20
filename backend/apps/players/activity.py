"""Competitive activity, distinct from being an active coach/content creator."""
from datetime import date, datetime
from functools import lru_cache
import gzip
from hashlib import sha256
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo
from django.utils import timezone

SOURCE_FILE = 'competitive_activity_2026_10_21_v1.json.gz'
SOURCE_SHA256 = '25e54c5bcf0d599ddaacfd15d05f954c14d14c1046c25b69c634416647adf22a'
WARSAW = ZoneInfo('Europe/Warsaw')
EXHIBITIONS = re.compile(r'all[ -]?star|showmatch|legend cup|idl kings lendas|caster.*host championship|streamers clash|comedy central winter snowdown',re.I)


def professional_event(row):
    return row['level'] in ('Primary','Secondary') and not EXHIBITIONS.search(row['event'])


def year_before(day):
    try:
        return day.replace(year=day.year-1)
    except ValueError:
        return day.replace(year=day.year-1,day=28)


@lru_cache(maxsize=1)
def activity_evidence():
    raw=(Path(__file__).parent/'fixtures'/'releases'/SOURCE_FILE).read_bytes()
    if sha256(raw).hexdigest()!=SOURCE_SHA256:
        raise ValueError('Competitive activity source checksum mismatch')
    data=json.loads(gzip.decompress(raw))
    if data.get('scope')!='professional_activity' or data.get('source')!='Leaguepedia':
        raise ValueError('Unknown activity evidence scope')
    return {p['slug']:{**p,'covered_since':data['covered_since'],'as_of':data['as_of']} for p in data['players']}


def competitive_active(player, day=None):
    """None means unknown; absence of evidence must not become retirement."""
    attrs=player.attributes or {}
    row=activity_evidence().get(getattr(player,'slug',''))
    if row and row['leaguepedia_page']==attrs.get('leaguepedia_page'):
        role=str(row['current_role'] or '').casefold()
        if role in ('coach','head coach','assistant coach','streamer','content creator') or row.get('retired') is True:
            return False
        day=day or timezone.localdate()
        boundary=year_before(day)
        latest=row.get('last_professional_game')
        if latest:
            played=datetime.fromisoformat(latest).astimezone(WARSAW).date()
            return played>=boundary
        return False if date.fromisoformat(row['covered_since'])<=boundary else None
    if attrs.get('worlds_verified') is True and attrs.get('leaguepedia_page'):
        return None
    return None if attrs.get('activity_verified') is False else bool(player.is_active)
