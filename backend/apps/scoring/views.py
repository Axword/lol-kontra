import math

from django.db.models import Avg, Count, F, Max, Min, Q, StdDev
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.submissions.models import MAX_ERRORS, STARTING_POINTS, Submission, SubmissionAnswer
from apps.dailies.models import Daily

from .engine import tier_for_percent
from .models import ScoringConfig


class ScoringViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def get_daily(self, daily_id):
        return get_object_or_404(
            Daily, pk=daily_id, status__in=['published', 'closed', 'scored'], date__lte=timezone.localdate()
        )

    @action(detail=False, methods=['get'], url_path=r'dailies/(?P<daily_id>[^/.]+)/answer-stats')
    def answer_stats(self, request, daily_id=None):
        """Ilu graczy wybrało którego zawodnika na którym slocie."""
        self.get_daily(daily_id)
        # Read real choices directly, so an old cached snapshot can never expose
        # synthetic votes that have already been retired.
        stats = list(SubmissionAnswer.objects.filter(
            daily_slot__daily_id=daily_id, is_correct=True,
            submission__is_practice=False, submission__is_seed=False,
        ).values('daily_slot_id', 'daily_slot__role', 'daily_slot__position',
                 'player__nickname', 'player__slug').annotate(pick_count=Count('id'))
          .order_by('daily_slot__position', '-pick_count', 'player__slug'))
        totals = {}
        for row in stats:
            totals[row['daily_slot_id']] = totals.get(row['daily_slot_id'], 0) + row['pick_count']
        cfg = ScoringConfig.objects.filter(is_active=True).first() or ScoringConfig()
        results = []
        for row in stats:
            percent = row['pick_count'] / totals[row['daily_slot_id']] * 100
            results.append({
                'slot_id': row['daily_slot_id'], 'slot_role': row['daily_slot__role'],
                'player': row['player__nickname'], 'player_slug': row['player__slug'],
                'pick_count': row['pick_count'], 'pick_percent': round(percent, 2),
                'rarity_tier': tier_for_percent(percent, cfg),
            })
        return Response({'daily_id': int(daily_id), 'results': results})

    @action(detail=False, methods=['get'], url_path=r'dailies/(?P<daily_id>[^/.]+)/score-distribution')
    def score_distribution(self, request, daily_id=None):
        """
        Rozkład wyników dla danego Daily plus pozycja gracza.

        Wynik to liczba punktów (wyżej = lepiej). Histogram grupujemy po pełnych
        punktach – `total_points` jest floatem, więc grupowanie po surowej wartości
        dawałoby tysiące jednoelementowych kubełków.
        """
        self.get_daily(daily_id)
        user_score = request.query_params.get('user_score')
        score = None
        if user_score is not None:
            try:
                score = float(user_score)
            except (TypeError, ValueError):
                raise ValidationError({'user_score': 'Wynik musi być skończoną liczbą'})
            if not math.isfinite(score):
                raise ValidationError({'user_score': 'Wynik musi być skończoną liczbą'})
            if not 0 <= score <= STARTING_POINTS:
                raise ValidationError({'user_score': 'Wynik musi mieścić się w zakresie 0–500'})
        scored = Submission.objects.filter(daily_id=daily_id, is_practice=False, is_seed=False).annotate(
            slot_count=Count('daily__slots', distinct=True),
            correct_count=Count('answers', filter=Q(answers__is_correct=True), distinct=True),
        ).filter(
            Q(is_scored=True) | Q(errors_used__gte=MAX_ERRORS)
            | Q(slot_count__gt=0, correct_count__gte=F('slot_count'))
        )

        buckets = {}
        for value in scored.values_list('total_points', flat=True):
            key = int(round(value or 0))
            buckets[key] = buckets.get(key, 0) + 1
        distribution = [{'score': k, 'count': v} for k, v in sorted(buckets.items())]

        agg = scored.aggregate(
            total=Count('id'),
            avg=Avg('total_points'),
            max=Max('total_points'),
            min=Min('total_points'),
        )
        try:
            agg['stddev'] = scored.aggregate(sd=StdDev('total_points')).get('sd')
        except Exception:
            agg['stddev'] = None

        total = agg.get('total') or 0
        percentile = rank = None
        if score is not None and total > 0:
            worse = scored.filter(total_points__lt=score).count()
            better = scored.filter(total_points__gt=score).count()
            percentile = round(worse / total * 100, 1)
            rank = better + 1

        return Response({
            'daily_id': int(daily_id),
            'distribution': distribution,
            'total_submissions': total,
            'seeded_count': 0,
            'real_count': total,
            'avg_score': round(agg.get('avg') or 0, 1) if total else None,
            'max_score': round(agg.get('max') or 0, 1) if total else None,
            'min_score': round(agg.get('min') or 0, 1) if total else None,
            'stddev': round(agg['stddev'], 1) if agg.get('stddev') is not None else None,
            'user_score': score,
            'percentile': percentile,
            'rank': rank,
        })
