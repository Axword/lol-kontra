from django.contrib import admin
from .models import Submission, SubmissionAnswer

class SubmissionAnswerInline(admin.TabularInline):
    model = SubmissionAnswer
    extra = 0
    readonly_fields = ('rarity_tier', 'rarity_percent', 'points_awarded', 'is_diamond_pick')

@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('id', 'daily', 'user', 'guest_token', 'submitted_at', 'total_points', 'is_scored')
    list_filter = ('is_scored', 'daily')
    inlines = [SubmissionAnswerInline]
    search_fields = ('user__username', 'guest_token')

@admin.register(SubmissionAnswer)
class SubmissionAnswerAdmin(admin.ModelAdmin):
    list_display = ('submission', 'daily_slot', 'player', 'is_correct', 'rarity_tier', 'points_awarded', 'is_diamond_pick')
    list_filter = ('is_correct', 'rarity_tier', 'is_diamond_pick')
