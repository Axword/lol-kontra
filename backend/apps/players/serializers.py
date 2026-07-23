from rest_framework import serializers
from .models import Player, Team, PlayerTeamHistory, CareerChampionStat


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = [
            'slug', 'name', 'region', 'country_code',
            'is_active', 'is_worlds_champion', 'worlds_titles_years', 'logo_url'
        ]


class PlayerTeamHistorySerializer(serializers.ModelSerializer):
    team = TeamSerializer(read_only=True)

    class Meta:
        model = PlayerTeamHistory
        fields = ['team', 'start_date', 'end_date', 'role']


class CareerChampionStatSerializer(serializers.ModelSerializer):
    class Meta:
        model = CareerChampionStat
        fields = [
            'champion_name', 'games_played', 'games_won', 'games_lost',
            'win_ratio', 'kills', 'deaths', 'assists', 'kda',
            'cs_per_min', 'dmg_per_min',
        ]


class PlayerListSerializer(serializers.ModelSerializer):
    team_history = PlayerTeamHistorySerializer(many=True, read_only=True)
    champion_stats = CareerChampionStatSerializer(many=True, read_only=True)

    class Meta:
        model = Player
        fields = [
            'id', 'slug', 'nickname', 'real_name', 'country_code',
            'residency', 'continent', 'primary_role', 'secondary_roles',
            'is_active', 'worlds_count', 'worlds_titles_count',
            'career_stats', 'attributes',
            'team_history', 'champion_stats',
        ]


class PlayerAutocompleteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Player
        fields = ['id', 'slug', 'nickname', 'primary_role', 'residency', 'country_code', 'is_active', 'worlds_count', 'worlds_titles_count', 'real_name']
