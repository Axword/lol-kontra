from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import get_user_model
from .serializers import UserSerializer, UserStatsSerializer
from .models import UserStats

User = get_user_model()

class UserViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    @action(detail=False, methods=['get'], url_path='me', permission_classes=[IsAuthenticated])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='me/stats', permission_classes=[IsAuthenticated])
    def my_stats(self, request):
        stats, _ = UserStats.objects.get_or_create(user=request.user)
        return Response(UserStatsSerializer(stats).data)

# Leaderboard simple
from rest_framework.views import APIView
from django.db.models import F

class LeaderboardView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        qs = UserStats.objects.select_related('user').order_by('-total_points')[:100]
        data = [{
            'username': s.user.username,
            'total_points': s.total_points,
            'games_played': s.games_played,
            'best_score': s.best_score,
            'diamond_picks': s.diamond_picks,
            'legendary_answers': s.legendary_answers,
        } for s in qs]
        return Response({'results': data})
