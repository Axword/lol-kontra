"""Synthetic guest history check, used only by the disposable CI Compose stack."""
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.dailies.models import Daily
from apps.dailies.validators import player_matches_slot
from apps.players.models import Player
from apps.submissions.models import Submission

assert os.environ.get('PROFILE_MIGRATION_SMOKE') in {'create', 'check'}
assert settings.DATABASES['default']['NAME'] in {'words_v', 'restore_ci'}
token = 'synthetic-ci-migration-identity-2026'
client = APIClient(HTTP_HOST='game.example.com', HTTP_X_FORWARDED_PROTO='https')
daily = Daily.objects.order_by('date').first()
if os.environ['PROFILE_MIGRATION_SMOKE'] == 'create':
    assert not Submission.objects.filter(guest_token=token).exists()
    get_user_model().objects.create_user(username='ciMigrationAccount', password='Synthetic-login-only-2026!')
    response = client.post('/api/v1/guest/profile/', {
        'guest_token': token, 'nickname': 'TransferTester', 'supported_team': 't1',
    }, format='json')
    assert response.status_code == 200
    selected = set()
    choices = []
    for slot in daily.slots.order_by('position'):
        player = next(player for player in Player.objects.all()
                      if player.pk not in selected and player_matches_slot(player, slot))
        selected.add(player.pk)
        choices.append({'slot_id': slot.pk, 'player_slug': player.slug})
    response = client.post('/api/v1/submissions/', {
        'daily_id': daily.pk, 'guest_token': token, 'answers': choices,
    }, format='json')
    assert response.status_code == 201 and response.data['is_over'] and response.data['total_points'] == 0

account = APIClient(HTTP_HOST='game.example.com', HTTP_X_FORWARDED_PROTO='https')
assert account.login(username='ciMigrationAccount', password='Synthetic-login-only-2026!')
account.logout()

profile = client.post('/api/v1/guest/profile/preview/', {'guest_token': token}, format='json')
assert profile.status_code == 200
assert profile.data['nickname'] == 'TransferTester' and profile.data['has_custom_nickname']
assert profile.data['supported_team']['id'] == 't1'
assert profile.data['stats']['games_played'] == 1 and profile.data['stats']['total_points'] == 0
assert profile.data['stats']['diamond_picks'] == 5
game = client.get('/api/v1/submissions/me/', {'daily_id': daily.pk, 'guest_token': token})
assert game.status_code == 200 and game.data['is_over'] and game.data['total_points'] == 0
assert len(game.data['answers']) == 5
assert all(answer['rarity_percent'] == 0 and answer['is_diamond_pick'] for answer in game.data['answers'])
print('PASS: same private identity resolves nickname, badge and complete historical roster with frozen percentages')
