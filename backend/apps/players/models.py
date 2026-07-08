from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField

ROLES = [
    ('top', 'Top'),
    ('jungle', 'Jungle'),
    ('mid', 'Mid'),
    ('adc', 'ADC'),
    ('support', 'Support'),
]

class Player(models.Model):
    slug = models.SlugField(unique=True, max_length=80)
    nickname = models.CharField(max_length=64, db_index=True)
    real_name = models.CharField(max_length=128, blank=True, null=True, default='')
    birth_year = models.IntegerField(null=True, blank=True)
    country_code = models.CharField(max_length=3, default='KR', blank=True)
    residency = models.CharField(max_length=8, db_index=True, default='LCK', blank=True)
    continent = models.CharField(max_length=16, blank=True, default='')
    primary_role = models.CharField(max_length=16, choices=ROLES, db_index=True, default='mid')
    secondary_roles = ArrayField(models.CharField(max_length=16), default=list, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    attributes = models.JSONField(default=dict)  # worlds_appearances, teams, coaches...
    career_stats = models.JSONField(default=dict)

    worlds_count = models.IntegerField(default=0, db_index=True)
    worlds_titles_count = models.IntegerField(default=0, db_index=True)

    search_vector = SearchVectorField(null=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            GinIndex(fields=['attributes']),
            models.Index(fields=['primary_role', 'is_active']),
            models.Index(fields=['nickname']),
        ]
        ordering = ['nickname']

    def __str__(self):
        return self.nickname

    @property
    def popularity_score(self):
        # do estymacji generatora – można nadpisać
        return self.attributes.get('popularity_score', 50)


class Team(models.Model):
    slug = models.SlugField(primary_key=True, max_length=64)
    name = models.CharField(max_length=128)
    region = models.CharField(max_length=8, blank=True)
    country_code = models.CharField(max_length=3, null=True, blank=True)

    def __str__(self):
        return self.name

class Coach(models.Model):
    slug = models.SlugField(primary_key=True, max_length=64)
    name = models.CharField(max_length=128)

    def __str__(self):
        return self.name

class PlayerTeamHistory(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='team_history')
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    role = models.CharField(max_length=16, choices=ROLES, blank=True)

    class Meta:
        verbose_name_plural = 'Player team history'

class TournamentAppearance(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='tournament_appearances')
    tournament_slug = models.CharField(max_length=64, db_index=True)  # worlds_2023
    year = models.IntegerField(db_index=True)
    team = models.ForeignKey(Team, null=True, blank=True, on_delete=models.SET_NULL)
    role = models.CharField(max_length=16, choices=ROLES, blank=True)
    placement = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = [('player', 'tournament_slug')]

class PlayerCoachHistory(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    coach = models.ForeignKey(Coach, on_delete=models.CASCADE)
    year = models.IntegerField(null=True, blank=True)
    team = models.ForeignKey(Team, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name_plural = 'Player coach history'
        unique_together = [('player', 'coach', 'year')]
