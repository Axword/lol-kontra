import logging

from django.db import transaction
from django.http import Http404
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .generator import generate_daily
from .models import Daily
from .serializers import DailySerializer, DailySlotSerializer

logger = logging.getLogger(__name__)


class DailyViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Daily.objects.prefetch_related('slots__conditions').order_by('-date')
    serializer_class = DailySerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return super().get_queryset().filter(
            date__lte=timezone.localdate(), status__in=['published', 'closed', 'scored'],
        )

    @action(detail=False, methods=['get'], url_path='today')
    def today(self, request):
        today = timezone.localdate()
        try:
            with transaction.atomic():
                daily = Daily.objects.select_for_update().filter(date=today).first()
                if daily is not None and daily.status == 'draft':
                    raise Http404
                if daily is None or not daily.slots.exists():
                    daily = generate_daily(date=today, seed=str(today))
                    daily.status = 'published'
                    daily.published_at = timezone.now()
                    daily.save(update_fields=['status', 'published_at'])
        except ValueError:
            logger.exception('Cannot generate daily for %s', today)
            return Response({'detail': 'Dzisiejsza plansza nie jest jeszcze dostępna.'}, status=503)
        daily = self.get_queryset().get(pk=daily.pk)
        return Response(self.get_serializer(daily).data)

    @action(detail=True, methods=['get'], url_path='slots')
    def slots(self, request, pk=None):
        daily = self.get_object()
        return Response(DailySlotSerializer(daily.slots.all(), many=True).data)

    @action(detail=False, methods=['post'], url_path='progress')
    def progress(self, request):
        """One private request for all calendar completion markers."""
        from django.db.models import Count, Q
        from rest_framework import serializers
        from apps.submissions.models import MAX_ERRORS, Submission
        from apps.users.serializers import GuestTokenField

        class Input(serializers.Serializer):
            guest_token = GuestTokenField(r'\A[A-Za-z0-9_-]{16,64}\Z', required=False, max_length=64, trim_whitespace=False)

        serializer = Input(data=request.data)
        serializer.is_valid(raise_exception=True)
        games = Submission.objects.filter(is_practice=False, is_seed=False, daily__in=self.get_queryset())
        if request.user.is_authenticated:
            games = games.filter(user=request.user)
        else:
            token = serializer.validated_data.get('guest_token')
            games = games.filter(user__isnull=True, guest_token=token) if token else games.none()
        rows = games.annotate(slots_total=Count('daily__slots', distinct=True),
                              correct=Count('answers', filter=Q(answers__is_correct=True), distinct=True))
        response = Response({'results': [{'daily_id': row.daily_id,
            'completed': row.errors_used >= MAX_ERRORS or (row.slots_total > 0 and row.correct >= row.slots_total)} for row in rows]})
        response['Cache-Control'] = 'private, no-store'
        return response

    @action(detail=True, methods=['get', 'post'], url_path='community')
    def community(self, request, pk=None):
        from .community import daily_community
        return daily_community(request, self.get_object())

    @action(detail=True, methods=['get'], url_path='solutions')
    def solutions(self, request, pk=None):
        from apps.submissions.models import Submission
        from .solutions import daily_solutions
        daily = self.get_object()
        submissions = Submission.objects.filter(daily=daily, is_practice=False, is_seed=False)
        if request.user.is_authenticated:
            submissions = submissions.filter(user=request.user)
        else:
            token = request.query_params.get('guest_token')
            submissions = submissions.filter(user__isnull=True, guest_token=token) if token else submissions.none()
        submission = submissions.first()
        if submission is None or not submission.is_over:
            return Response({'detail': 'Rozwiązania są dostępne po zakończeniu własnej gry.'}, status=403)
        return Response(daily_solutions(daily))
