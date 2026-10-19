from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import F, Q
from .worlds_teams import WORLDS_2026_TEAM_IDS

class UserStats(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='stats')
    games_played = models.IntegerField(default=0)
    total_points = models.FloatField(default=0)
    avg_points = models.FloatField(default=0)
    best_score = models.FloatField(default=0)
    legendary_answers = models.IntegerField(default=0)
    diamond_picks = models.IntegerField(default=0)
    current_streak = models.IntegerField(default=0)
    max_streak = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'User stats'
        constraints = [
            models.CheckConstraint(check=Q(games_played__gte=0, legendary_answers__gte=0,
                diamond_picks__gte=0, current_streak__gte=0, max_streak__gte=0), name='userstats_counts_nonnegative'),
            models.CheckConstraint(check=Q(total_points__gte=0, total_points__lte=F('games_played') * 500.0), name='userstats_total_within_games'),
            models.CheckConstraint(check=Q(avg_points__gte=0, avg_points__lte=500,
                best_score__gte=0, best_score__lte=500), name='userstats_scores_0_500'),
            models.CheckConstraint(check=Q(current_streak__lte=F('max_streak'), max_streak__lte=F('games_played')), name='userstats_streaks_within_games'),
        ]

    def __str__(self):
        return f"Stats {self.user}"


class GuestProfile(models.Model):
    # A guest token is a bearer credential. Profiles only store its keyed hash;
    # neither the token nor this private identity key is serialized publicly.
    guest_key = models.CharField(max_length=64, unique=True, editable=False)
    nickname = models.CharField(max_length=24, blank=True, default='')
    has_custom_nickname = models.BooleanField(default=False, db_default=False)
    supported_team = models.CharField(max_length=16, blank=True, default='', db_default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(guest_key__regex=r'^[a-f0-9]{64}$'), name='guestprofile_key_is_sha256'),
            models.CheckConstraint(check=Q(supported_team='') | Q(supported_team__in=WORLDS_2026_TEAM_IDS),
                                   name='guestprofile_supported_team_valid'),
        ]

    def __str__(self):
        return self.nickname or 'Guest profile'


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_stats(sender, instance, created, **kwargs):
    if created:
        UserStats.objects.get_or_create(user=instance)
