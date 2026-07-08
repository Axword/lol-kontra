from django.contrib import admin
from .models import Player, Team, Coach, TournamentAppearance, PlayerTeamHistory

@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('nickname', 'real_name', 'primary_role', 'residency', 'country_code', 'worlds_count', 'worlds_titles_count', 'is_active')
    list_filter = ('primary_role', 'residency', 'is_active', 'continent')
    search_fields = ('nickname', 'real_name', 'slug')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('slug', 'name', 'region', 'country_code')
    search_fields = ('name', 'slug')

@admin.register(Coach)
class CoachAdmin(admin.ModelAdmin):
    search_fields = ('name', 'slug')

@admin.register(TournamentAppearance)
class TournamentAppearanceAdmin(admin.ModelAdmin):
    list_display = ('player', 'tournament_slug', 'year', 'team', 'role', 'placement')
    list_filter = ('year', 'role')

admin.site.register(PlayerTeamHistory)
