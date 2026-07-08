from rest_framework import serializers
from .models import Player, Team

class PlayerListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Player
        fields = [
            'id', 'slug', 'nickname', 'real_name', 'country_code',
            'residency', 'continent', 'primary_role', 'secondary_roles',
            'is_active', 'worlds_count', 'worlds_titles_count',
            'career_stats', 'attributes'
        ]

class PlayerAutocompleteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Player
        fields = ['id', 'slug', 'nickname', 'primary_role', 'residency', 'country_code', 'is_active', 'worlds_count', 'worlds_titles_count', 'real_name']
