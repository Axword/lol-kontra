from django.db.models import Count, F, Min, Q, Subquery, Sum
from django.utils import timezone
from rest_framework import serializers, viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import get_user_model
from rest_framework.generics import get_object_or_404
from apps.dailies.models import Daily
from apps.submissions.models import MAX_ERRORS, Submission, SubmissionAnswer
from .serializers import GuestProfileInputSerializer, GuestTokenField, UserSerializer, UserStatsSerializer
from .services import refresh_user_stats
from .models import GuestProfile
from .guest_profiles import guest_display_name, guest_identity_key, guest_stats
from .worlds_teams import WORLDS_2026_SOURCE_URL, WORLDS_2026_TEAMS, supported_team_details

User = get_user_model()

class UserViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return super().get_queryset().filter(pk=self.request.user.pk)

    @action(detail=False, methods=['get'], url_path='me', permission_classes=[IsAuthenticated])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='me/stats', permission_classes=[IsAuthenticated])
    def my_stats(self, request):
        stats = refresh_user_stats(request.user.pk)
        return Response(UserStatsSerializer(stats).data)

# Leaderboard simple
from rest_framework.views import APIView


class GuestProfileView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = GuestProfileInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        token = payload['guest_token']
        key = guest_identity_key(token)
        updates = {}
        if 'nickname' in payload:
            updates['nickname'] = payload['nickname']
            if payload['nickname']:
                updates['has_custom_nickname'] = True
        if 'supported_team' in payload:
            updates['supported_team'] = payload['supported_team'] or ''
        if updates:
            profile, _ = GuestProfile.objects.update_or_create(
                guest_key=key, defaults=updates,
            )
        else:
            profile, _ = GuestProfile.objects.get_or_create(guest_key=key)
        response = Response({
            'nickname': profile.nickname or None,
            'display_name': guest_display_name(token, profile.nickname),
            'has_custom_nickname': profile.has_custom_nickname or bool(profile.nickname),
            'supported_team': supported_team_details(profile.supported_team),
            'stats': guest_stats(token),
        })
        response['Cache-Control'] = 'private, no-store'
        return response


class GuestTeamsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            'season': 2026,
            'source_url': WORLDS_2026_SOURCE_URL,
            'teams': WORLDS_2026_TEAMS,
        })


class GuestProfilePreviewView(APIView):
    """Check a user's imported credential without creating or changing a profile."""
    permission_classes = [AllowAny]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        return response

    def post(self, request):
        class Input(serializers.Serializer):
            guest_token = GuestTokenField(r'\A[A-Za-z0-9_-]{16,64}\Z', trim_whitespace=False, max_length=64)

        serializer = Input(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data['guest_token']
        profile = GuestProfile.objects.filter(guest_key=guest_identity_key(token)).first()
        if profile is None and not Submission.objects.filter(
                user__isnull=True, guest_token=token, is_seed=False).exists():
            return Response({'detail': 'Nie znaleziono profilu. Sprawdź, czy baza danych została już przeniesiona.'}, status=404)
        return Response({
            'nickname': (profile.nickname or None) if profile else None,
            'display_name': guest_display_name(token, profile.nickname if profile else ''),
            'has_custom_nickname': bool(profile and (profile.has_custom_nickname or profile.nickname)),
            'supported_team': supported_team_details(profile.supported_team) if profile else None,
            'stats': guest_stats(token),
        })


class LeaderboardInputSerializer(serializers.Serializer):
    limit = serializers.ChoiceField(choices=[10, 25, 50, 100], default=50)
    daily_id = serializers.IntegerField(required=False, min_value=1)
    guest_token = GuestTokenField(r'\A[A-Za-z0-9_-]{16,64}\Z', required=False,
                                  trim_whitespace=False, max_length=64)


class LeaderboardView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        # Guest credentials are deliberately never read from query strings.
        payload = {key: request.query_params[key] for key in ['limit', 'daily_id']
                   if key in request.query_params}
        return self._response(request, payload)

    def post(self, request):
        return self._response(request, request.data)

    def _response(self, request, payload):
        serializer = LeaderboardInputSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        options = serializer.validated_data
        limit = options['limit']
        token = options.get('guest_token')
        current_identity = ('user', request.user.pk) if request.user.is_authenticated else (
            ('guest', token) if token else None)
        games = Submission.objects.filter(
            is_practice=False, is_seed=False, daily__date__lte=timezone.localdate(),
            daily__status__in=['published', 'closed', 'scored'],
        )
        daily_id = options.get('daily_id')
        if daily_id is not None:
            daily = get_object_or_404(
                Daily, pk=daily_id, date__lte=timezone.localdate(), status__in=['published', 'closed', 'scored']
            )
            games = games.filter(daily=daily)
        finished_ids = games.annotate(
            slot_count=Count('daily__slots', distinct=True),
            correct_count=Count('answers', filter=Q(answers__is_correct=True), distinct=True),
        ).filter(
            Q(is_scored=True) | Q(errors_used__gte=MAX_ERRORS)
            | Q(slot_count__gt=0, correct_count__gte=F('slot_count'))
        ).order_by().values('pk')
        # Keep score aggregation separate from the answer joins: each game
        # contributes its score once, regardless of the number of answers.
        finished = Submission.objects.filter(pk__in=Subquery(finished_ids))
        ranked = []
        current_profile_name = ''
        for guest in [False, True]:
            identity = 'guest_token' if guest else 'user_id'
            group_fields = [identity] if guest else [identity, 'user__username']
            population = finished.filter(user__isnull=guest)
            if guest:
                population = population.exclude(guest_token__isnull=True).exclude(guest_token='')
            totals = population.order_by().values(*group_fields).annotate(
                best_score=Min('total_points'), games_played=Count('pk'), points_sum=Sum('total_points'),
            )
            answer_identity = f'submission__{identity}'
            counts = {
                row[answer_identity]: row for row in SubmissionAnswer.objects.filter(
                    submission_id__in=Subquery(population.order_by().values('pk')), is_correct=True,
                ).order_by().values(answer_identity).annotate(
                    diamond_picks=Count('pk', filter=Q(is_diamond_pick=True)),
                    legendary_answers=Count('pk', filter=Q(rarity_tier='legendary')),
                )
            }
            # Resolve all guest nicknames in one query, while keeping private
            # bearer tokens and identity hashes out of the response.
            rows = list(totals)
            profiles = {}
            if guest:
                keys = {guest_identity_key(row[identity]) for row in rows}
                if current_identity and current_identity[0] == 'guest':
                    keys.add(guest_identity_key(current_identity[1]))
                profiles = dict(GuestProfile.objects.filter(guest_key__in=keys).values_list('guest_key', 'nickname'))
                if current_identity and current_identity[0] == 'guest':
                    current_profile_name = profiles.get(guest_identity_key(current_identity[1]), '')
            for row in rows:
                if guest:
                    username = guest_display_name(row[identity], profiles.get(guest_identity_key(row[identity]), ''))
                else:
                    username = row['user__username']
                picks = counts.get(row[identity], {})
                entry = {
                    'username': username, 'is_guest': guest,
                    'total_points': row['points_sum'], 'games_played': row['games_played'],
                    'avg_points': row['points_sum'] / row['games_played'],
                    'best_score': row['best_score'], 'diamond_picks': picks.get('diamond_picks', 0),
                    'legendary_answers': picks.get('legendary_answers', 0),
                }
                private_identity = ('guest' if guest else 'user', row[identity])
                tie_breaker = guest_identity_key(row[identity]) if guest else str(row[identity]).zfill(20)
                ranked.append((entry, private_identity, tie_breaker))
        ranked.sort(key=lambda row: (row[0]['avg_points'], row[0]['best_score'], -row[0]['games_played'],
                                    row[0]['username'], row[0]['is_guest'], row[2]))
        current_player = None
        data = []
        for rank, (entry, private_identity, _) in enumerate(ranked, 1):
            entry['rank'] = rank
            if private_identity == current_identity:
                current_player = entry
            if rank <= limit:
                data.append(entry)
        if current_identity and current_player is None:
            current_player = {
                'rank': None,
                'username': request.user.username if request.user.is_authenticated else guest_display_name(token, current_profile_name),
                'is_guest': not request.user.is_authenticated,
                'total_points': 0, 'games_played': 0, 'avg_points': None, 'best_score': None,
                'diamond_picks': 0, 'legendary_answers': 0,
            }
        response = Response({'results': data, 'limit': limit, 'total_players': len(ranked),
                             'current_player': current_player})
        if current_identity:
            response['Cache-Control'] = 'private, no-store'
        return response
