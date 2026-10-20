from datetime import date
from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.db import connection
from django.test import TestCase

from apps.players.models import Player
from apps.submissions.models import Submission
from .builder import condition_catalog
from .models import Daily, DailySlot, DailySlotCondition
from .validators import evaluate_condition

wording = import_module('apps.dailies.migrations.0018_clarify_default_clues')


class ClueWordingTests(TestCase):
    def test_translation_migration_preserves_rules_games_custom_labels_and_is_idempotent(self):
        daily = Daily.objects.create(date=date(2026, 1, 1))
        slot = DailySlot.objects.create(daily=daily, role='top', position=1)
        standard = DailySlotCondition.objects.create(slot=slot, condition_type='worlds_top5_champion',
            value='Olaf', label_pl='Olaf w TOP 5 na Worlds', label_en='Olaf in Worlds top 5 played')
        custom = DailySlotCondition.objects.create(slot=slot, condition_type='worlds_count_min',
            operator='gte', value=2, label_pl='Własna wskazówka autora', label_en='2+ Worlds appearances')
        wrong_operator = DailySlotCondition.objects.create(slot=slot, condition_type='worlds_games',
            operator='gte', value=50, label_pl='Ponad 50 gier na Worlds', label_en='Custom English clue')
        game = Submission.objects.create(daily=daily, guest_token='wording-preserves-game', total_points=123.45, errors_used=2)
        fields=('pk','slot_id','condition_type','operator','value','order')
        before=list(DailySlotCondition.objects.order_by('pk').values_list(*fields))
        apply=lambda: wording.clarify_default_labels(apps,SimpleNamespace(connection=connection))
        apply()
        standard.refresh_from_db(); custom.refresh_from_db(); wrong_operator.refresh_from_db(); game.refresh_from_db()
        self.assertEqual(standard.label_pl,'Olaf w jego TOP 5 według liczby gier na Worlds')
        self.assertEqual(custom.label_pl,'Własna wskazówka autora')
        self.assertEqual(custom.label_en,'Played in at least 2 editions of Worlds')
        self.assertEqual(wrong_operator.label_pl,'Ponad 50 gier na Worlds')
        self.assertEqual(list(DailySlotCondition.objects.order_by('pk').values_list(*fields)),before)
        self.assertAlmostEqual(float(game.total_points),123.45)
        self.assertEqual(game.errors_used,2)
        after=list(DailySlotCondition.objects.order_by('pk').values())
        apply()
        self.assertEqual(list(DailySlotCondition.objects.order_by('pk').values()),after)

    def test_historical_year_range_description_keeps_both_inclusive_bounds(self):
        changes=wording.label_changes('birth_year_range','eq',{'min':2000,'max':2010})
        self.assertEqual(changes[0][2],'Urodzony w latach 2000–2010')
        self.assertEqual(wording.label_changes('birth_year_range','eq',{'min':2000,'max':2020}),[])

    def test_editor_group_exit_options_use_the_supported_operator_and_years(self):
        player=Player.objects.create(slug='group-exit',nickname='GroupExit',primary_role='mid',
            attributes={'worlds_eliminations':{'group':[2019]}})
        options=[c for c in condition_catalog().values() if c[2]=='worlds_group_exit_before']
        self.assertTrue(options)
        self.assertTrue(all(c[3]=='eq' and 2012<=c[4]<=2023 for c in options))
        before_2020=next(c for c in options if c[4]==2020)
        self.assertTrue(evaluate_condition(player,*before_2020[2:5]))
        self.assertFalse(evaluate_condition(player,'worlds_group_exit_before','eq',2019))
