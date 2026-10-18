import hashlib
import hmac

from django.conf import settings
from django.db.models import Count, F, Max, Q, Subquery, Sum
from django.utils import timezone
from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from apps.dailies.models import Daily
from apps.submissions.models import MAX_ERRORS, Submission, SubmissionAnswer
from .serializers import UserSerializer, UserStatsSerializer
from .services import refresh_user_stats

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

class LeaderboardView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        games = Submission.objects.filter(
            is_practice=False, is_seed=False, daily__date__lte=timezone.localdate(),
            daily__status__in=['published', 'closed', 'scored'],
        )
        daily_id = request.query_params.get('daily_id')
        if daily_id is not None:
            try:
                daily_id = int(daily_id)
            except (TypeError, ValueError):
                raise ValidationError({'daily_id': 'daily_id musi być liczbą całkowitą'})
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
        data = []
        for guest in [False, True]:
            identity = 'guest_token' if guest else 'user_id'
            group_fields = [identity] if guest else [identity, 'user__username']
            population = finished.filter(user__isnull=guest)
            if guest:
                population = population.exclude(guest_token__isnull=True).exclude(guest_token='')
            totals = population.order_by().values(*group_fields).annotate(
                best_score=Max('total_points'), games_played=Count('pk'), points_sum=Sum('total_points'),
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
            for row in totals:
                if guest:
                    digest = hmac.new(settings.SECRET_KEY.encode(), row[identity].encode(), hashlib.sha256).hexdigest()[:8]
                    username = f'#{digest.upper()}'
                else:
                    username = row['user__username']
                picks = counts.get(row[identity], {})
                data.append({
                    'username': username, 'is_guest': guest,
                    'total_points': row['points_sum'], 'games_played': row['games_played'],
                    'best_score': row['best_score'], 'diamond_picks': picks.get('diamond_picks', 0),
                    'legendary_answers': picks.get('legendary_answers', 0),
                })
        data.sort(key=lambda entry: (-entry['total_points'], -entry['best_score'], entry['username'], entry['is_guest']))
        return Response({'results': data[:100]})
