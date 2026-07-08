from django.contrib import admin
from .models import AnswerStatsDaily, ScoringConfig

@admin.register(AnswerStatsDaily)
class AnswerStatsDailyAdmin(admin.ModelAdmin):
    list_display = ('daily_slot', 'player', 'pick_count', 'pick_percent', 'rarity_tier')
    list_filter = ('rarity_tier',)

@admin.register(ScoringConfig)
class ScoringConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_active', 'points_common', 'points_rare', 'points_epic', 'points_legendary', 'diamond_bonus', 'updated_at')
