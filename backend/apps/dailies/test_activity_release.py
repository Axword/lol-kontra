from importlib import import_module
from io import StringIO
from types import SimpleNamespace
from django.apps import apps
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from apps.players.models import Player
from apps.submissions.models import Submission,SubmissionAnswer,SubmissionAttempt
from .models import Daily,DailySlot,DailySlotCondition
from .generator import count_candidates,validate_daily


class ActivityReleaseTests(TestCase):
    def test_future_refresh_keeps_started_games_guest_boards_and_current_clues(self):
        call_command('seed_players',full=True,stdout=StringIO())
        normal=Daily.objects.create(date='2026-10-23',status='published')
        for position,role in enumerate(['top','jungle','mid','adc','support'],1):
            slot=DailySlot.objects.create(daily=normal,role=role,position=position)
            DailySlotCondition.objects.create(slot=slot,condition_type='country',value='KR')
        protected=[]
        for day,author in [('2026-10-21',''),('2026-10-22','Kaczy'),('2026-10-25','')]:
            daily=Daily.objects.create(date=day,author_name=author,status='published')
            slot=DailySlot.objects.create(daily=daily,position=1,role='mid')
            condition=DailySlotCondition.objects.create(slot=slot,condition_type='country',value='KR')
            protected.append(condition.pk)
            if day=='2026-10-25':
                game=Submission.objects.create(daily=daily,guest_token='activity-started-game')
                player=Player.objects.get(slug='faker')
                SubmissionAnswer.objects.create(submission=game,daily_slot=slot,player=player,is_correct=True)
                SubmissionAttempt.objects.create(submission=game,daily_slot=slot,player=player,is_correct=True)
        before={m:list(m.objects.order_by('pk').values()) for m in [Submission,SubmissionAnswer,SubmissionAttempt]}
        old_conditions=list(DailySlotCondition.objects.filter(pk__in=protected).order_by('pk').values())
        old_slots=list(normal.slots.values_list('pk',flat=True))
        migration=import_module('apps.dailies.migrations.0021_activity_future_boards')
        migration.install(apps,SimpleNamespace(connection=connection))
        validate_daily(normal)
        self.assertTrue(all(len(count_candidates(s))>=10 for s in normal.slots.all()))
        self.assertEqual(old_slots,list(normal.slots.values_list('pk',flat=True)))
        self.assertEqual(old_conditions,list(DailySlotCondition.objects.filter(pk__in=protected).order_by('pk').values()))
        for model,rows in before.items():self.assertEqual(list(model.objects.order_by('pk').values()),rows)
        conditions=list(DailySlotCondition.objects.order_by('pk').values())
        migration.install(apps,SimpleNamespace(connection=connection))
        self.assertEqual(list(DailySlotCondition.objects.order_by('pk').values()),conditions)
