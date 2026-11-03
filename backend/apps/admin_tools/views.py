from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django.utils import timezone
from apps.dailies.models import Daily, DailySlot, valid_requirement_count
from apps.dailies.serializers import DailySerializer
from apps.dailies.generator import (generate_daily, count_candidates, generate_slot, validate_daily,
                                   validate_board_diversity)
from apps.scoring.models import ScoringConfig
from apps.scoring.models import ScoringConfig as ScoringConfigModel
from rest_framework import serializers

class AdminDailyViewSet(viewsets.ModelViewSet):
    queryset = Daily.objects.all().order_by('-date')
    serializer_class = DailySerializer
    permission_classes = [IsAdminUser]

    def _validate_future_diversity(self, daily, target=None):
        if (target or daily.date) > timezone.localdate():
            validate_board_diversity([slot.conditions.all()
                for slot in daily.slots.prefetch_related('conditions')])

    def perform_update(self, serializer):
        attrs = serializer.validated_data
        publishing = attrs.get('status') == 'published'
        moving_published = 'date' in attrs and serializer.instance.status == 'published'
        if publishing or moving_published:
            try:
                self._validate_future_diversity(serializer.instance, attrs.get('date'))
            except ValueError as exc:
                raise serializers.ValidationError({'status': str(exc)}) from exc
        super().perform_update(serializer)

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        daily = self.get_object()
        try:
            validate_daily(daily)
            self._validate_future_diversity(daily)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        daily.status = 'published'
        daily.published_at = timezone.now()
        daily.save(update_fields=['status', 'published_at'])
        return Response({'status': 'published'})

    @action(detail=True, methods=['post'])
    def rescore(self, request, pk=None):
        from apps.scoring.tasks import score_daily_task
        score_daily_task.delay(int(pk))
        return Response({'status': 'rescore_queued'})

    @action(detail=False, methods=['post'])
    def generate(self, request):
        from django.utils import timezone
        date = request.data.get('date')
        if date:
            from datetime import datetime
            date = datetime.fromisoformat(date).date()
        daily = generate_daily(date=date)
        return Response(DailySerializer(daily).data, status=status.HTTP_201_CREATED)

class ScoringConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScoringConfigModel
        fields = '__all__'

class AdminScoringViewSet(viewsets.ModelViewSet):
    queryset = ScoringConfigModel.objects.all()
    serializer_class = ScoringConfigSerializer
    permission_classes = [IsAdminUser]
