from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import UserStats

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined']

class UserStatsSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    class Meta:
        model = UserStats
        fields = ['username', 'games_played', 'total_points', 'avg_points', 'best_score',
                  'legendary_answers', 'diamond_picks', 'current_streak', 'max_streak', 'updated_at']
