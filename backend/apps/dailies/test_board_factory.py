from copy import deepcopy
from importlib import import_module
import random
from django.test import SimpleTestCase
from apps.players.models import Player
from apps.players.career_roles import with_verified_career_roles
from .board_factory import build_catalog, choose_board, is_worlds
from .validators import PlayerFacts, evaluate_condition
from .generator import _has_distinct_roster


class WorldsBoardFactoryTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        source = import_module('apps.players.migrations.0005_worlds_2026_october_19_release')
        cls.players = [Player(pk=index+1, **with_verified_career_roles(deepcopy(row))) for index,row in enumerate(source.load_release())]
        cls.by_id = {p.pk:p for p in cls.players}
        cls.catalog = build_catalog(cls.players)

    def test_boards_have_three_worlds_clues_two_other_clues_and_ten_real_answers(self):
        champion_boards=0
        for seed in range(20):
            board,year = choose_board(self.catalog,random.Random(seed))
            self.assertEqual(sum(option['worlds'] for option in board),3)
            common = set.intersection(*(set(option['anchors']) for option in board))
            self.assertTrue(any(_has_distinct_roster([
                [self.by_id[pk] for pk in option['anchor_players'][anchor]]
                for option in board
            ]) for anchor in common))
            champions=sum(any(c[2]=='worlds_top5_champion' for c in option['conditions']) for option in board)
            self.assertLessEqual(champions,1)
            champion_boards+=bool(champions)
            for role,option in zip(['top','jungle','mid','adc','support'],board):
                self.assertGreaterEqual(len(option['candidate_ids']),10)
                self.assertFalse(any(c[2]=='career_top5_champion' for c in option['conditions']))
                self.assertTrue(any(year in PlayerFacts(self.by_id[pk]).worlds_years for pk in option['candidate_ids']))
                for pk in option['candidate_ids']:
                    player=self.by_id[pk]
                    self.assertIn(role,PlayerFacts(player).roles)
                    self.assertTrue(all(evaluate_condition(player,*c[2:5]) for c in option['conditions']))
        self.assertLess(champion_boards,10)
