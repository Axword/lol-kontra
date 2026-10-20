"""Independent, server-authoritative ten-error runs; never writes Daily submissions."""
import copy
import random
import uuid

from django.db import transaction
from django.db.models import F, Max
from types import SimpleNamespace
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.dailies.board_factory import choose_board, question_catalog
from apps.dailies.generator import ROLE_ORDER
from apps.dailies.validators import player_matches_slot
from apps.players.models import Player
from apps.players.serializers import VerifiedPlayerSerializer
from apps.users.guest_profiles import guest_display_name, guest_identity_key
from apps.users.models import GuestProfile
from apps.users.serializers import GuestTokenField
from .models import InfinityAttempt, InfinityRun, MAX_ERRORS
from . import infinity_rankings as rankings


class Identity(serializers.Serializer):
    guest_token = GuestTokenField(r'\A[A-Za-z0-9_-]{16,64}\Z', max_length=64, trim_whitespace=False)


class Answer(Identity):
    run_id = serializers.UUIDField()
    board_id = serializers.UUIDField()
    position = serializers.IntegerField(min_value=1, max_value=5)
    player_slug = serializers.SlugField(max_length=80)


def validated(serializer, data):
    instance = serializer(data=data)
    instance.is_valid(raise_exception=True)
    return instance.validated_data


def make_board(previous=None):
    previous = previous or {}
    chosen, year = choose_board(question_catalog(), random.SystemRandom(), previous=previous.get('signature'))
    slots = []
    for position, (role, option) in enumerate(zip(ROLE_ORDER, chosen), 1):
        conditions = [{'id': position * 10 + index, 'condition_type': c[2], 'operator': c[3],
            'value': c[4], 'label_pl': c[5], 'label_en': c[6]} for index, c in enumerate(option['conditions'])]
        slots.append({'id': position, 'position': position, 'role': role, 'label_pl': role.capitalize(),
            'label_en': role.capitalize(), 'conditions': conditions, 'candidate_ids': option['candidate_ids']})
    return {'slots': slots, 'theme_year': year, 'signature': [o['conditions'] for o in chosen]}


def run_state(run):
    slots = [{key: value for key, value in slot.items() if key != 'candidate_ids'} for slot in run.board['slots']]
    return {'id': str(run.id), 'board_id': str(run.board_id), 'slots': slots, 'answers': run.answers,
        'correct_count': run.correct_count, 'completed_boards': run.correct_count // 5,
        'errors_used': run.errors_used, 'errors_left': MAX_ERRORS - run.errors_used,
        'max_errors': MAX_ERRORS, 'is_over': run.finished_at is not None,
        'ranking_result': (run.ranking_result or rankings.finished_result(run)) if run.finished_at else None}


def private_response(data, status=200):
    response = Response(data, status=status)
    response['Cache-Control'] = 'private, no-store'
    return response


def matches_current_clues(run, position, player):
    slot=next(s for s in run.board['slots'] if s['position']==position)
    conditions=[SimpleNamespace(**c) for c in slot['conditions']]
    return player_matches_slot(player,SimpleNamespace(role=slot['role'],
        conditions=SimpleNamespace(all=lambda:conditions)))


@api_view(['POST'])
@permission_classes([AllowAny])
def state(request):
    token = validated(Identity, request.data)['guest_token']
    runs = InfinityRun.objects.filter(guest_profile__guest_key=guest_identity_key(token))
    run = runs.order_by(F('finished_at').desc(nulls_first=True), '-started_at').first()
    best = runs.aggregate(best=Max('correct_count'))['best'] or 0
    return private_response({'run': run_state(run) if run else None, 'personal_best': best})


@api_view(['POST'])
@permission_classes([AllowAny])
def start(request):
    token = validated(Identity, request.data)['guest_token']
    profile, _ = GuestProfile.objects.get_or_create(guest_key=guest_identity_key(token))
    with transaction.atomic():
        GuestProfile.objects.select_for_update().get(pk=profile.pk)
        run = InfinityRun.objects.filter(guest_profile=profile, finished_at__isnull=True).first()
        if run is None:
            before={'completed_runs':InfinityRun.objects.filter(guest_profile=profile,finished_at__isnull=False).count(),
                    'ranks':rankings.snapshot(profile.pk)}
            run = InfinityRun.objects.create(guest_profile=profile,ranking_before=before,
                display_suffix=guest_display_name(token).removeprefix('Gość-'), board=make_board())
        best = InfinityRun.objects.filter(guest_profile=profile).aggregate(best=Max('correct_count'))['best'] or 0
    return private_response({'run': run_state(run), 'personal_best': best})


@api_view(['POST'])
@permission_classes([AllowAny])
def answer(request):
    payload = validated(Answer, request.data)
    with transaction.atomic():
        run = get_object_or_404(InfinityRun.objects.select_for_update(), pk=payload['run_id'],
            guest_profile__guest_key=guest_identity_key(payload['guest_token']))
        player = get_object_or_404(Player, slug=payload['player_slug'])
        attempt = InfinityAttempt.objects.filter(run=run, board_id=payload['board_id'],
            position=payload['position'], player=player).order_by('-is_correct').first()
        corrected_retry=False
        if (attempt and not attempt.is_correct and not run.finished_at and run.board_id==payload['board_id']
            and not any(a['daily_slot']==payload['position'] or a['player']==player.pk for a in run.answers)):
            corrected_retry=matches_current_clues(run,payload['position'],player)
        unchanged = attempt is not None and not corrected_retry
        if attempt and not corrected_retry:
            correct = attempt.is_correct
        elif run.finished_at or run.board_id != payload['board_id']:
            return private_response({'code': 'board_changed', 'run': run_state(run)}, status=409)
        elif any(a['daily_slot'] == payload['position'] for a in run.answers):
            return private_response({'code': 'position_closed', 'run': run_state(run)}, status=409)
        elif any(a['player'] == player.pk for a in run.answers):
            return private_response({'code': 'player_used', 'run': run_state(run)}, status=400)
        else:
            slot = next(s for s in run.board['slots'] if s['position'] == payload['position'])
            # Existing boards keep their visible clues; new policy/data can
            # qualify a player absent from the original cached candidate list.
            correct = corrected_retry or matches_current_clues(run,payload['position'],player)
            InfinityAttempt.objects.create(run=run, board_id=run.board_id,
                position=payload['position'], player=player, is_correct=correct)
            if correct:
                run.correct_count += 1
                run.answers = copy.deepcopy(run.answers) + [{
                    'id': payload['position'], 'daily_slot': payload['position'], 'slot_role': slot['role'],
                    'player': player.pk, 'player_slug': player.slug, 'player_nickname': player.nickname,
                    'player_portrait_url': VerifiedPlayerSerializer().get_portrait_url(player),
                    'is_correct': True, 'rarity_tier': None, 'rarity_percent': None,
                    'points_awarded': 0, 'is_diamond_pick': False}]
                if len(run.answers) == 5:
                    run.board = make_board(run.board)
                    run.board_id = uuid.uuid4()
                    run.answers = []
            else:
                run.errors_used += 1
                if run.errors_used == MAX_ERRORS:
                    run.finished_at = timezone.now()
            run.save()
            if run.finished_at:
                run.ranking_result=rankings.finished_result(run)
                run.save(update_fields=['ranking_result'])
        best = InfinityRun.objects.filter(guest_profile=run.guest_profile).aggregate(best=Max('correct_count'))['best'] or 0
    return private_response({'run': run_state(run), 'personal_best': best,
        'correct': correct, 'unchanged': unchanged, 'player_nickname': player.nickname})


class RankingInput(serializers.Serializer):
    period = serializers.ChoiceField(choices=rankings.PERIODS,default='all_time')
    page = serializers.IntegerField(min_value=1, max_value=1000000, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=25)


@api_view(['GET'])
@permission_classes([AllowAny])
def leaderboard(request):
    params = validated(RankingInput, request.query_params)
    leaders = rankings.leaders(params['period']).select_related('guest_profile')
    total = leaders.count()
    pages = max(1, (total + params['page_size'] - 1) // params['page_size'])
    page = min(params['page'], pages)
    offset = (page - 1) * params['page_size']
    rows = [{'rank': offset + index + 1, 'nickname': 'Gość-' + (run.guest_profile.nickname or run.display_suffix),
        'correct_count': run.correct_count, 'completed_boards': run.correct_count // 5,
        'is_active': run.finished_at is None} for index, run in enumerate(leaders[offset:offset + params['page_size']])]
    return private_response({'results': rows, 'page': page, 'total_pages': pages, 'total_players': total,'period':params['period']})
