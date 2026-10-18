from django.contrib import admin
from .models import AnswerStatsDaily, ScoringConfig

@admin.register(AnswerStatsDaily)
class AnswerStatsDailyAdmin(admin.ModelAdmin):
    list_display = ('daily_slot', 'player', 'pick_count', 'pick_percent', 'rarity_tier')
    list_filter = ('rarity_tier',)

@admin.register(ScoringConfig)
class ScoringConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_active', 'threshold_rare', 'threshold_epic', 'threshold_legendary', 'updated_at')
