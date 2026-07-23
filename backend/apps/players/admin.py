from django.contrib import admin
from .models import Player, Team, Coach, TournamentAppearance, PlayerTeamHistory, CareerChampionStat

@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('nickname', 'real_name', 'primary_role', 'residency', 'country_code', 'worlds_count', 'worlds_titles_count', 'is_active')
    list_filter = ('primary_role', 'residency', 'is_active', 'continent')
    search_fields = ('nickname', 'real_name', 'slug')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('slug', 'name', 'region', 'country_code', 'is_active', 'is_worlds_champion')
    list_filter = ('region', 'is_active', 'is_worlds_champion')
    search_fields = ('name', 'slug')

@admin.register(Coach)
class CoachAdmin(admin.ModelAdmin):
    search_fields = ('name', 'slug')

@admin.register(TournamentAppearance)
class TournamentAppearanceAdmin(admin.ModelAdmin):
    list_display = ('player', 'tournament_slug', 'year', 'team', 'role', 'placement')
    list_filter = ('year', 'role')

@admin.register(PlayerTeamHistory)
class PlayerTeamHistoryAdmin(admin.ModelAdmin):
    list_display = ('player', 'team', 'role', 'start_date', 'end_date')
    list_filter = ('role',)
    search_fields = ('player__nickname', 'team__name')

@admin.register(CareerChampionStat)
class CareerChampionStatAdmin(admin.ModelAdmin):
    list_display = ('player', 'champion_name', 'games_played', 'win_ratio', 'kda', 'source')
    list_filter = ('source', 'champion_name')
    search_fields = ('player__nickname', 'champion_name')
