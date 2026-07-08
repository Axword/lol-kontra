import pytest
from apps.players.models import Player
from apps.dailies.models import Daily, DailySlot, DailySlotCondition
from apps.dailies.validators import player_matches_slot

@pytest.mark.django_db
def test_player_matches_condition():
    p = Player.objects.create(
        slug='faker',
        nickname='Faker',
        country_code='KR',
        residency='LCK',
        continent='Asia',
        primary_role='mid',
        attributes={
            'worlds_appearances': [2013,2015,2016],
            'worlds_titles': [2013,2015,2016],
            'teams': ['t1'],
            'leagues': ['LCK'],
            'coaches': ['kkoma']
        },
        worlds_count=7,
        worlds_titles_count=3
    )
    daily = Daily.objects.create(date='2025-01-01', locale_seed='test')
    slot = DailySlot.objects.create(daily=daily, position=1, role='mid')
    DailySlotCondition.objects.create(slot=slot, condition_type='residency', operator='eq', value='LCK', label_pl='LCK', label_en='LCK')
    DailySlotCondition.objects.create(slot=slot, condition_type='worlds_champion', operator='eq', value=True, label_pl='Worlds Champ', label_en='Worlds Champ')
    assert player_matches_slot(p, slot) is True
