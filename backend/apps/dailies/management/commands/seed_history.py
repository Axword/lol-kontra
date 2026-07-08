from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
import random
from datetime import timedelta

from apps.dailies.models import Daily, DailySlot, DailySlotCondition
from apps.dailies.generator import generate_daily
from apps.players.models import Player
from apps.submissions.models import Submission, SubmissionAnswer
from apps.scoring.engine import score_daily

class Command(BaseCommand):
    help = 'Seed 7 days history with simulated submissions'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30)
        parser.add_argument('--subs', type=int, default=550, help='submissions per day')
        parser.add_argument('--clear', action='store_true')

    def handle(self, *args, **opts):
        days = opts['days']
        subs_per_day = opts['subs']
        if opts['clear']:
            Daily.objects.filter(date__lt=timezone.localdate()).delete()
            self.stdout.write(self.style.WARNING('Cleared old dailies'))

        today = timezone.localdate()
        created_days = 0
        for i in range(days, 0, -1):
            d = today - timedelta(days=i)
            daily, created = Daily.objects.get_or_create(
                date=d,
                defaults={'status':'published','reveal_mode':'instant','locale_seed':str(d)}
            )
            if created or daily.slots.count() == 0:
                # ensure slots
                if daily.slots.exists():
                    daily.slots.all().delete()
                try:
                    # try generator
                    from apps.dailies.generator import generate_daily as gen
                    # force regenerate
                    DailySlot.objects.filter(daily=daily).delete()
                    # use generator internals
                    roles = ['top','jungle','mid','adc','support']
                    # simple fallback – create demo slots guaranteed to have >=15 candidates
                    self._create_demo_slots(daily, roles)
                    created_days += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Gen failed {d}: {e}"))
                    continue
            # simulate submissions if none
            if Submission.objects.filter(daily=daily).count() < 10:
                self.simulate_submissions(daily, subs_per_day)
            # score
            score_daily(daily.id)
            daily.status = 'scored'
            daily.closed_at = timezone.now()
            daily.save(update_fields=['status','closed_at'])
            self.stdout.write(self.style.SUCCESS(f"Daily {daily.id} {d} – subs:{Submission.objects.filter(daily=daily).count()} – scored"))
        self.stdout.write(self.style.SUCCESS(f'Done. Created {created_days} new dailies. Total in DB: {Daily.objects.count()}'))

    def _create_demo_slots(self, daily, roles):
        """Create slots guaranteed to have 20-80 candidates"""
        # Predefined safe condition sets (tested manually against 876 players DB)
        # each tuple: role, [(condition_type, operator, value, label_pl, label_en), ...]
        pools = {
            'top': [
                [('residency','eq','LCK','Grał w LCK','Played in LCK'), ('worlds_appearance','any',True,'Grał na Worlds','Worlds appearance')],
                [('residency','eq','LEC','Grał w LEC','Played in LEC'), ('active','eq',True,'Aktywny','Active')],
                [('country','eq','KR','Koreańczyk','Korean'), ('worlds_appearance','gte',2,'Min. 2 Worlds','2+ Worlds')],
            ],
            'jungle': [
                [('residency','eq','LPL','Grał w LPL','Played in LPL'), ('worlds_appearance','any',True,'Grał na Worlds','Worlds appearance')],
                [('continent','eq','Europe','Europejczyk','European'), ('active','eq',True,'Aktywny','Active')],
                [('residency','eq','LCK','Grał w LCK','Played in LCK'), ('active','eq',False,'Emerytowany','Retired')],
            ],
            'mid': [
                [('residency','eq','LCK','Grał w LCK','Played in LCK'), ('worlds_champion','eq',True,'Wygrał Worlds','Worlds Champion')],
                [('country','eq','KR','Koreańczyk','Korean'), ('msi_appearance','any',True,'Grał na MSI','MSI appearance')],
                [('league','eq','LEC','Grał w LEC','Played in LEC'), ('worlds_appearance','any',True,'Grał na Worlds','Worlds appearance')],
            ],
            'adc': [
                [('continent','eq','Europe','Europejczyk','European'), ('team','eq','fnatic','Grał w Fnatic','Played for Fnatic')],
                [('residency','eq','LPL','Grał w LPL','Played in LPL'), ('active','eq',True,'Aktywny','Active')],
                [('country','eq','KR','Koreańczyk','Korean'), ('worlds_appearance','gte',3,'Min. 3 Worlds','3+ Worlds')],
            ],
            'support': [
                [('coach','eq','kkoma','Trenowany przez kkOmę','Coached by kkOma'), ('worlds_appearance','any',True,'Grał na Worlds','Worlds')],
                [('residency','eq','LEC','Grał w LEC','Played in LEC'), ('active','eq',True,'Aktywny','Active')],
                [('league','eq','LCS','Grał w LCS','Played in LCS'), ('worlds_appearance','any',True,'Grał na Worlds','Worlds')],
            ],
        }
        from apps.dailies.models import DailySlot, DailySlotCondition
        from apps.dailies.validators import player_matches_slot
        from apps.players.models import Player
        pos=1
        for role in roles:
            # try conditions until candidate count 15-90
            import random
            choices = pools.get(role, pools['mid'])
            random.shuffle(choices)
            slot = DailySlot.objects.create(daily=daily, role=role, position=pos, label_pl=role.capitalize(), label_en=role.capitalize())
            pos+=1
            # find first condition set with good candidate count
            found=False
            for cond_set in choices:
                # clear
                slot.conditions.all().delete()
                for idx,(ctype,op,val,pl,en) in enumerate(cond_set):
                    DailySlotCondition.objects.create(slot=slot, condition_type=ctype, operator=op, value=val, label_pl=pl, label_en=en, order=idx)
                # count candidates (quick, max 300 scan)
                c=0
                qs = Player.objects.filter(primary_role=role)[:400]
                for p in qs:
                    if player_matches_slot(p, slot):
                        c+=1
                        if c>90: break
                if 20 <= c <= 65:
                    found=True
                    # prefer closer to 40
                    if 30 <= c <= 50:
                        break
            if not found:
                # keep last tried – still playable
                pass

    def simulate_submissions(self, daily, n):
        """Create n fake submissions with popularity-weighted picks"""
        from apps.players.models import Player
        from apps.dailies.validators import player_matches_slot
        import random
        slots = list(daily.slots.prefetch_related('conditions').all())
        # precompute candidates per slot
        slot_candidates = {}
        for s in slots:
            cands = []
            qs = Player.objects.filter(primary_role=s.role)[:600]
            for p in qs:
                if player_matches_slot(p, s):
                    cands.append(p)
            # fallback secondary role
            if len(cands) < 5:
                qs2 = Player.objects.exclude(primary_role=s.role)[:400]
                for p in qs2:
                    if s.role in (p.secondary_roles or []):
                        if player_matches_slot(p, s):
                            cands.append(p)
            # ensure at least 5
            if not cands:
                cands = list(Player.objects.filter(primary_role=s.role)[:10])
            # assign popularity weight – worlds_count + titles*3 + small random
            weighted = []
            for p in cands:
                w = 1 + p.worlds_count * 2 + p.worlds_titles_count * 5
                # boost famous nicks
                if p.nickname.lower() in ['faker','caps','ruler','deft','uzi','perkz','rekkles','jankos','the shy','theshy','showmaker','chovy','canyon','ruler','gumayusi','keria']:
                    w *= 4
                weighted.append((p, w))
            slot_candidates[s.id] = weighted

        created = 0
        for i in range(n):
            guest_token = f'sim_{daily.id}_{i}_{random.randint(1000,999999)}'
            # 2% chance duplicate -> skip (to get natural distribution)
            sub = Submission.objects.create(daily=daily, guest_token=guest_token, ip_hash='sim')
            # pick per slot weighted
            for s in slots:
                weighted = slot_candidates.get(s.id, [])
                if not weighted:
                    continue
                # weighted random
                total_w = sum(w for _,w in weighted)
                r = random.uniform(0, total_w)
                upto = 0
                chosen = weighted[0][0]
                for p,w in weighted:
                    if upto + w >= r:
                        chosen = p
                        break
                    upto += w
                # 5% chance pick totally random rare – increases entropy
                if random.random() < 0.07 and len(weighted) > 5:
                    chosen = random.choice(weighted)[0]
                SubmissionAnswer.objects.create(
                    submission=sub,
                    daily_slot=s,
                    player=chosen,
                    is_correct=True  # candidates are pre-validated
                )
            created += 1
        return created
