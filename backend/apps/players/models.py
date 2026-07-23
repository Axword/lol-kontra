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
    is_active = models.BooleanField(default=True, db_index=True)
    is_worlds_champion = models.BooleanField(default=False, db_index=True,
        help_text='Czy drużyna kiedykolwiek wygrała Worlds')
    worlds_titles_years = models.JSONField(default=list, blank=True,
        help_text='Lista lat, w których drużyna wygrała Worlds, np. [2013, 2015, 2016]')
    logo_url = models.URLField(max_length=512, blank=True, default='')

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


class CareerChampionStat(models.Model):
    """
    Statystyki gracza na konkretnym championie w karierze.
    Dane pobierane z lol.fandom.com (Special:RunQuery/TournamentStatistics).
    """
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='champion_stats')
    champion_name = models.CharField(max_length=64, db_index=True)
    games_played = models.IntegerField(default=0)
    games_won = models.IntegerField(default=0)
    games_lost = models.IntegerField(default=0)
    win_ratio = models.FloatField(null=True, blank=True)
    kills = models.FloatField(null=True, blank=True)
    deaths = models.FloatField(null=True, blank=True)
    assists = models.FloatField(null=True, blank=True)
    kda = models.FloatField(null=True, blank=True)
    cs_per_min = models.FloatField(null=True, blank=True)
    dmg_per_min = models.FloatField(null=True, blank=True)
    source = models.CharField(max_length=32, default='lolwiki', db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('player', 'champion_name', 'source')]
        ordering = ['-games_played']
        indexes = [
            models.Index(fields=['player', '-games_played']),
            models.Index(fields=['champion_name']),
        ]

    def __str__(self):
        return f"{self.player.nickname} – {self.champion_name} ({self.games_played}G)"
