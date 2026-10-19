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
