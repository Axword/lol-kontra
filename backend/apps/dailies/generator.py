import random
from django.utils import timezone
from .models import Daily, DailySlot, DailySlotCondition
from apps.players.models import Player
from .validators import player_matches_slot

CONDITION_POOL = [
    # (type, operator, value, label_pl, label_en)
    ('residency', 'eq', 'LCK', 'Grał w LCK', 'Played in LCK'),
    ('residency', 'eq', 'LPL', 'Grał w LPL', 'Played in LPL'),
    ('residency', 'eq', 'LEC', 'Grał w LEC', 'Played in LEC'),
    ('residency', 'eq', 'LCS', 'Grał w LCS', 'Played in LCS'),
    ('worlds_champion', 'eq', True, 'Wygrał Worlds', 'Worlds Champion'),
    ('worlds_appearance', 'any', True, 'Grał na Worlds', 'Worlds appearance'),
    ('worlds_titles_min', 'eq', 2, 'Min. 2 tytuły Worlds', '2+ Worlds titles'),
    ('active', 'eq', True, 'Aktywny zawodnik', 'Active player'),
    ('active', 'eq', False, 'Emerytowany', 'Retired'),
    ('country', 'eq', 'KR', 'Koreańczyk', 'Korean'),
    ('country', 'eq', 'CN', 'Chińczyk', 'Chinese'),
    ('continent', 'eq', 'Europe', 'Europejczyk', 'European'),
    ('team', 'eq', 't1', 'Grał w T1', 'Played for T1'),
    ('team', 'eq', 'fnatic', 'Grał w Fnatic', 'Played for Fnatic'),
    ('team', 'eq', 'g2', 'Grał w G2', 'Played for G2'),
    ('coach', 'eq', 'kkoma', 'Trenowany przez kkOmę', 'Coached by kkOma'),
]

ROLE_ORDER = ['top', 'jungle', 'mid', 'adc', 'support']

def count_candidates(slot):
    # naiwne – iteruje po graczach roli (dla MVP, później SQL JSONB)
    candidates = []
    qs = Player.objects.filter(primary_role=slot.role, is_active=True) | Player.objects.filter(secondary_roles__contains=[slot.role])
    qs = qs.distinct()[:500]
    for p in qs:
        if player_matches_slot(p, slot):
            candidates.append(p)
            if len(candidates) > 200:
                break
    return candidates

def generate_slot(daily, role, position, seed=None):
    rnd = random.Random(f"{daily.date}-{role}-{seed}")
    slot = DailySlot.objects.create(daily=daily, role=role, position=position, label_pl=role.capitalize(), label_en=role.capitalize())
    # pick 2-3 conditions
    attempts = 0
    while attempts < 30:
        attempts += 1
        # clear previous conditions if retry
        slot.conditions.all().delete()
        chosen = rnd.sample(CONDITION_POOL, k=rnd.choice([2,2,3]))
        for i, (ctype, op, val, pl, en) in enumerate(chosen):
            DailySlotCondition.objects.create(
                slot=slot,
                condition_type=ctype,
                operator=op,
                value=val,
                label_pl=pl,
                label_en=en,
                order=i
            )
        candidates = count_candidates(slot)
        cc = len(candidates)
        if 20 <= cc <= 65:
            # idealnie 30-50
            if 30 <= cc <= 50:
                return slot, candidates
            # akceptuj 20-65, ale szukaj dalej lepszego – max prób i tak ogranicza
            # pozwól z 40% szansą żeby nie utknąć
            import random as _r
            if _r.random() < 0.4:
                return slot, candidates
    # fallback – loosest
    return slot, count_candidates(slot)

def generate_daily(date=None, seed=None):
    if date is None:
        date = timezone.localdate() + timezone.timedelta(days=1)
    daily, created = Daily.objects.get_or_create(date=date, defaults={
        'status': 'draft',
        'locale_seed': str(seed or date),
        'reveal_mode': 'instant'
    })
    if daily.slots.exists():
        return daily
    for pos, role in enumerate(ROLE_ORDER, start=1):
        generate_slot(daily, role, pos, seed=seed)
    return daily
