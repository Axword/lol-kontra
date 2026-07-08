from django.contrib import admin
from .models import UserStats

@admin.register(UserStats)
class UserStatsAdmin(admin.ModelAdmin):
    list_display = ('user', 'games_played', 'total_points', 'best_score', 'diamond_picks', 'legendary_answers', 'current_streak')
    search_fields = ('user__username',)
