from django.db import models

class AnswerStatsDaily(models.Model):
    daily_slot = models.ForeignKey(
        'dailies.DailySlot',
        on_delete=models.CASCADE,
        related_name='answer_stats',
        db_index=True,
    )
    player = models.ForeignKey(
        'players.Player',
        on_delete=models.CASCADE,
        related_name='answer_stats',
    )
    pick_count = models.IntegerField(default=0)
    pick_percent = models.FloatField(default=0)
    rarity_tier = models.CharField(max_length=16)
    is_correct = models.BooleanField(default=True)

    class Meta:
        unique_together = [('daily_slot', 'player')]
        indexes = [
            # For fetching all stats for a daily (across all slots)
            models.Index(fields=['daily_slot'], name='idx_stats_slot'),
        ]

    def __str__(self):
        return f"{self.daily_slot} – {self.player} {self.pick_percent:.2f}% {self.rarity_tier}"

class ScoringConfig(models.Model):
    is_active = models.BooleanField(default=True)
    points_common = models.IntegerField(default=10)
    points_rare = models.IntegerField(default=25)
    points_epic = models.IntegerField(default=60)
    points_legendary = models.IntegerField(default=120)
    diamond_bonus = models.IntegerField(default=50)

    threshold_rare = models.FloatField(default=20.0)
    threshold_epic = models.FloatField(default=10.0)
    threshold_legendary = models.FloatField(default=1.0)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"ScoringConfig active={self.is_active}"

    @classmethod
    def get_active(cls):
        obj = cls.objects.filter(is_active=True).first()
        if not obj:
            obj = cls.objects.create(is_active=True)
        return obj
