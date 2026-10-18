from rest_framework import serializers
from urllib.parse import urlsplit

from .models import Player, Team


class VerifiedPlayerSerializer(serializers.ModelSerializer):
    portrait_url = serializers.SerializerMethodField()

    def get_portrait_url(self, instance):
        attributes = instance.attributes or {}
        value = attributes.get('portrait_url')
        if attributes.get('portrait_source') != 'Leaguepedia' or not isinstance(value, str):
            return None
        try:
            parsed = urlsplit(value)
            if (parsed.scheme == 'https' and parsed.hostname in
                    ('static.wikia.nocookie.net', 'vignette.wikia.nocookie.net')
                    and not parsed.username and not parsed.password and parsed.port in (None, 443)):
                return value
        except ValueError:
            pass
        return None
    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.attributes.get('activity_verified') is False:
            data.pop('is_active', None)
        if 'worlds_titles' not in instance.attributes and not instance.worlds_titles_count:
            data.pop('worlds_titles_count', None)
        return data


class PlayerListSerializer(VerifiedPlayerSerializer):
    """
    Publiczna lista zawodników.

    NIE zawiera `attributes` ani `career_stats` – to na ich podstawie sprawdzamy warunki
    slotów, więc wystawienie ich pozwalałoby rozwiązać planszę bez zgadywania.
    Pełne dane są dostępne w panelu administracyjnym.
    """
    class Meta:
        model = Player
        fields = [
            'id', 'slug', 'nickname', 'portrait_url', 'real_name', 'country_code',
            'residency', 'continent', 'primary_role', 'secondary_roles',
            'is_active', 'worlds_count', 'worlds_titles_count',
        ]


class PlayerAutocompleteSerializer(VerifiedPlayerSerializer):
    class Meta:
        model = Player
        fields = [
            'id', 'slug', 'nickname', 'portrait_url', 'real_name',
            'primary_role', 'residency', 'country_code', 'is_active',
        ]


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ['slug', 'name', 'region', 'country_code']
