from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserStats(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='stats')
    games_played = models.IntegerField(default=0)
    total_points = models.IntegerField(default=0)
    avg_points = models.FloatField(default=0)
    best_score = models.IntegerField(default=0)
    legendary_answers = models.IntegerField(default=0)
    diamond_picks = models.IntegerField(default=0)
    current_streak = models.IntegerField(default=0)
    max_streak = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'User stats'

    def __str__(self):
        return f"Stats {self.user}"

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_stats(sender, instance, created, **kwargs):
    if created:
        UserStats.objects.get_or_create(user=instance)
