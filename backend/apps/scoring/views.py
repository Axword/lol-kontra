from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db.models import Count
from .models import AnswerStatsDaily
from apps.dailies.models import Daily
from apps.submissions.models import Submission

class ScoringViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    @action(detail=False, methods=['get'], url_path=r'dailies/(?P<daily_id>[^/.]+)/answer-stats')
    def answer_stats(self, request, daily_id=None):
        stats = AnswerStatsDaily.objects.filter(daily_slot__daily_id=daily_id).select_related('player', 'daily_slot')
        data = [
            {
                'slot_id': s.daily_slot_id,
                'slot_role': s.daily_slot.role,
                'player': s.player.nickname,
                'player_slug': s.player.slug,
                'pick_count': s.pick_count,
                'pick_percent': round(s.pick_percent, 2),
                'rarity_tier': s.rarity_tier,
            } for s in stats
        ]
        return Response({'daily_id': daily_id, 'results': data})

    @action(detail=False, methods=['get'], url_path=r'dailies/(?P<daily_id>[^/.]+)/score-distribution')
    def score_distribution(self, request, daily_id=None):
        """
        Zwraca dokładny rozkład punktów – per 1 pkt.
        [
          {"score": 0, "count": 3},
          {"score": 10, "count": 12},
          ...
        ]
        + percentyle, statystyki
        """
        qs = (Submission.objects
              .filter(daily_id=daily_id, is_scored=True)
              .values('total_points')
              .annotate(count=Count('id'))
              .order_by('total_points'))
        distribution = [{'score': row['total_points'], 'count': row['count']} for row in qs]

        # statystyki agregujące
        from django.db.models import Avg, Max, Min, StdDev, Count
        agg = Submission.objects.filter(daily_id=daily_id, is_scored=True).aggregate(
            total=Count('id'),
            avg=Avg('total_points'),
            max=Max('total_points'),
            min=Min('total_points'),
        )
        # spróbuj StdDev – może nie być dostępne na sqlite
        try:
            std_agg = Submission.objects.filter(daily_id=daily_id, is_scored=True).aggregate(sd=StdDev('total_points'))
            agg['stddev'] = std_agg.get('sd')
        except Exception:
            agg['stddev'] = None

        # percentyle – policz rank użytkownika jeśli podano ?user_score=
        user_score = request.query_params.get('user_score')
        percentile = None
        rank = None
        if user_score is not None:
            try:
                us = int(user_score)
                worse = Submission.objects.filter(daily_id=daily_id, is_scored=True, total_points__lt=us).count()
                total = agg.get('total') or 0
                if total > 0:
                    percentile = round(worse / total * 100, 1)
                    # rank: 1 = najlepszy
                    better_or_equal = Submission.objects.filter(daily_id=daily_id, is_scored=True, total_points__gte=us).count()
                    # approximate rank = number with strictly greater +1
                    greater = Submission.objects.filter(daily_id=daily_id, is_scored=True, total_points__gt=us).count()
                    rank = greater + 1
            except Exception:
                pass

        return Response({
            'daily_id': int(daily_id),
            'distribution': distribution,  # per exact score
            'total_submissions': agg.get('total', 0),
            'avg_score': round(agg.get('avg') or 0, 1),
            'max_score': agg.get('max') or 0,
            'min_score': agg.get('min') or 0,
            'stddev': round(agg.get('stddev') or 0, 1) if agg.get('stddev') else None,
            'user_score': int(user_score) if user_score is not None else None,
            'percentile': percentile,
            'rank': rank,
        })
