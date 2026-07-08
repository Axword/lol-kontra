from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from apps.dailies.models import Daily, DailySlot
from apps.dailies.serializers import DailySerializer
from apps.dailies.generator import generate_daily, count_candidates, generate_slot
from apps.scoring.tasks import score_daily_task
from apps.scoring.models import ScoringConfig
from apps.scoring.models import ScoringConfig as ScoringConfigModel
from rest_framework import serializers

class AdminDailyViewSet(viewsets.ModelViewSet):
    queryset = Daily.objects.all().order_by('-date')
    serializer_class = DailySerializer
    permission_classes = [IsAdminUser]

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        daily = self.get_object()
        from django.utils import timezone
        daily.status = 'published'
        daily.published_at = timezone.now()
        daily.save(update_fields=['status', 'published_at'])
        return Response({'status': 'published'})

    @action(detail=True, methods=['post'])
    def rescore(self, request, pk=None):
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
