"""Daily comments and rankings; solutions are revealed only after own play."""
import unicodedata
from collections import defaultdict
from urllib.parse import urlsplit

from django.db import transaction
from django.db.models import Count, F, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET
from rest_framework import serializers
from rest_framework.response import Response

from apps.submissions.models import MAX_ERRORS, Submission
from apps.users.guest_profiles import (
    _BLOCKED_FORMS, _SEVERE_ROOT, _moderation_forms, guest_display_name, guest_identity_key,
)
from apps.users.models import GuestProfile
from apps.users.serializers import GuestTokenField
from apps.users.worlds_teams import supported_team_details
from .models import CommunityComment
from .roster_images import localize_roster_png, render_roster_png


def validate_comment(value):
    if not isinstance(value, str):
        raise serializers.ValidationError('Komentarz musi być tekstem.')
    value = unicodedata.normalize('NFKC', value).strip()
    if len(value) > 500:
        raise serializers.ValidationError('Komentarz może mieć maksymalnie 500 znaków.')
    if any(unicodedata.category(char).startswith('C') and char != '\n' for char in value):
        raise serializers.ValidationError('Komentarz zawiera niedozwolone znaki.')
    forms = _moderation_forms(value)
    if forms & _BLOCKED_FORMS or any(_SEVERE_ROOT.search(form) for form in forms):
        raise serializers.ValidationError('Napisz komentarz bez obraźliwych słów.')
    return value


class CommentField(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail('invalid')
        return super().to_internal_value(data)


class CommunityInput(serializers.Serializer):
    guest_token = GuestTokenField(r'\A[A-Za-z0-9_-]{16,64}\Z', trim_whitespace=False, max_length=64)
    comment = CommentField(required=False, allow_blank=True, trim_whitespace=False, max_length=500)

    def validate_comment(self, value):
        return validate_comment(value)


def finished_games(daily):
    return Submission.objects.filter(daily=daily, is_practice=False, is_seed=False).annotate(
        slot_count=Count('daily__slots', distinct=True),
        correct_count=Count('answers', filter=Q(answers__is_correct=True), distinct=True),
    ).filter(Q(is_scored=True) | Q(errors_used__gte=MAX_ERRORS)
             | Q(slot_count__gt=0, correct_count__gte=F('slot_count')))


def _author(daily):
    url = daily.author_url or 'https://x.com/AxwordLol'
    try:
        parsed = urlsplit(url)
        valid = parsed.scheme in ('https', 'http') and parsed.hostname and not parsed.username and not parsed.password
    except ValueError:
        valid = False
    if not valid:
        url = 'https://x.com/AxwordLol'
    return {
        'name': daily.author_name or 'Axword', 'url': url,
        'description': daily.author_description or 'Autor wyzwania',
        **({'avatar_url': '/authors/kaczy.png'} if url == 'https://x.com/kaczy102' else {}),
    }


def daily_community(request, daily):
    token = None
    payload = {}
    if request.method == 'POST':
        serializer = CommunityInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        token = payload['guest_token']
    eligible = finished_games(daily)
    own = eligible.filter(user__isnull=True, guest_token=token).first() if token else None
    if own and not (own.errors_used >= MAX_ERRORS or own.slot_count > 0 and own.correct_count >= own.slot_count):
        own = None
    can_view = own is not None
    if 'comment' in payload:
        if not can_view:
            return Response({'detail': 'Komentarz ze składem dodasz po zakończeniu własnej gry.'}, status=403)
        existing = CommunityComment.objects.filter(submission=own).first()
        snapshot = None if existing else render_roster_png(own)
        # A single game lock serializes simultaneous first posts. Text edits
        # preserve the immutable snapshot and its random public share key.
        with transaction.atomic():
            Submission.objects.select_for_update().get(pk=own.pk)
            comment = CommunityComment.objects.filter(submission=own).first()
            if comment:
                if comment.text != payload['comment']:
                    comment.text = payload['comment']
                    comment.save(update_fields=['text', 'updated_at'])
            else:
                CommunityComment.objects.create(submission=own, text=payload['comment'], roster_png=snapshot)

    games = list(eligible.select_related('user').order_by('total_points', 'submitted_at', 'pk'))
    profiles = {profile.guest_key: profile for profile in GuestProfile.objects.filter(
        guest_key__in=[guest_identity_key(game.guest_token) for game in games if game.guest_token],
    )}

    def identity(game):
        if game.user_id:
            return game.user.username, None
        profile = profiles.get(guest_identity_key(game.guest_token))
        return guest_display_name(game.guest_token, profile.nickname if profile else ''), (
            supported_team_details(profile.supported_team) if profile else None)

    player_ranking = []
    teams = defaultdict(list)
    for game in games:
        nickname, team = identity(game)
        if len(player_ranking) < 10:
            player_ranking.append({'nickname': nickname, 'team': team, 'score': game.total_points})
        if team:
            teams[team['id']].append(game.total_points)
    team_ranking = [{
        'team': supported_team_details(team_id), 'players': len(scores),
        'average_score': sum(scores) / len(scores),
    } for team_id, scores in teams.items()]
    team_ranking.sort(key=lambda row: (row['average_score'], -row['players'], row['team']['code']))
    comments = []
    eligible_by_id = {game.pk: game for game in games}
    rows = CommunityComment.objects.filter(submission_id__in=eligible_by_id).defer('roster_png')[:100]
    for comment in rows:
        game = eligible_by_id[comment.submission_id]
        nickname, team = identity(game)
        comments.append({
            'id': comment.pk, 'nickname': nickname, 'team': team, 'score': game.total_points,
            'created_at': comment.created_at.isoformat(),
            'text': (comment.text or None) if can_view else None,
            'roster_image_url': request.build_absolute_uri(
                f'/api/v1/roster-shares/{comment.share_key}.png') if can_view else None,
        })
    own_comment_id = CommunityComment.objects.filter(submission=own).values_list('pk', flat=True).first() if own else None
    response = Response({
        'author': _author(daily), 'can_view_solutions': can_view,
        'can_comment': can_view and own_comment_id is None, 'own_comment_id': own_comment_id,
        'comments': comments, 'player_ranking': player_ranking, 'team_ranking': team_ranking,
    })
    response['Cache-Control'] = 'private, no-store'
    return response


@require_GET
def roster_share(request, share_key):
    comment = get_object_or_404(CommunityComment.objects.filter(
        share_key=share_key, submission__is_practice=False, submission__is_seed=False,
        submission__daily__date__lte=timezone.localdate(),
        submission__daily__status__in=['published', 'closed', 'scored'],
    ).only('roster_png'))
    value = bytes(comment.roster_png)
    if request.GET.get('v') == '2':
        value = localize_roster_png(value, request.GET.get('lang', 'pl'))
    response = HttpResponse(value, content_type='image/png')
    response['Cache-Control'] = 'public, max-age=31536000, immutable'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
