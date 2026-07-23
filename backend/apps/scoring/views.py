from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db.models import Count, Avg, Max, Min, StdDev
from .models import AnswerStatsDaily
from apps.dailies.models import Daily
from apps.submissions.models import Submission

class ScoringViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    @action(detail=False, methods=['get'], url_path=r'dailies/(?P<daily_id>[^/.]+)/answer-stats')
    def answer_stats(self, request, daily_id=None):
        # FIX: select_related prevents N+1 queries on player and daily_slot
        stats = (AnswerStatsDaily.objects
                 .filter(daily_slot__daily_id=daily_id)
                 .select_related('player', 'daily_slot')
                 .order_by('daily_slot__position', '-pick_percent'))
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
        return Response({'daily_id': int(daily_id), 'results': data})

    @action(detail=False, methods=['get'], url_path=r'dailies/(?P<daily_id>[^/.]+)/score-distribution')
    def score_distribution(self, request, daily_id=None):
        """
        Zwraca rozkład punktów (per 1 pkt bucket) + percentyle, statystyki.
        FIX: total_points is now FloatField — no more /10 decoding.
        """
        qs = (Submission.objects
              .filter(daily_id=daily_id, is_scored=True)
              .values('total_points')
              .annotate(count=Count('id'))
              .order_by('total_points'))
        distribution = [{'score': round(row['total_points'], 1), 'count': row['count']} for row in qs]

        # Aggregate statistics
        agg = Submission.objects.filter(daily_id=daily_id, is_scored=True).aggregate(
            total=Count('id'),
            avg=Avg('total_points'),
            max=Max('total_points'),
            min=Min('total_points'),
        )
        try:
            std_agg = Submission.objects.filter(daily_id=daily_id, is_scored=True).aggregate(sd=StdDev('total_points'))
            agg['stddev'] = std_agg.get('sd')
        except Exception:
            agg['stddev'] = None

        # Percentile / rank for a given user score
        user_score = request.query_params.get('user_score')
        percentile = None
        rank = None
        if user_score is not None:
            try:
                us = float(user_score)
                worse = Submission.objects.filter(daily_id=daily_id, is_scored=True, total_points__lt=us).count()
                total = agg.get('total') or 0
                if total > 0:
                    percentile = round(worse / total * 100, 1)
                    greater = Submission.objects.filter(daily_id=daily_id, is_scored=True, total_points__gt=us).count()
                    rank = greater + 1
            except (ValueError, TypeError):
                pass

        return Response({
            'daily_id': int(daily_id),
            'distribution': distribution,
            'total_submissions': agg.get('total', 0),
            'avg_score': round(agg.get('avg') or 0, 1),
            'max_score': round(agg.get('max') or 0, 1),
            'min_score': round(agg.get('min') or 0, 1),
            'stddev': round(agg.get('stddev'), 1) if agg.get('stddev') else None,
            'user_score': float(user_score) if user_score is not None else None,
            'percentile': percentile,
            'rank': rank,
        })
