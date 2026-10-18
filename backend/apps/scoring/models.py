from django.db import models
from django.db.models import F, Q

class AnswerStatsDaily(models.Model):
    daily_slot = models.ForeignKey('dailies.DailySlot', on_delete=models.CASCADE)
    player = models.ForeignKey('players.Player', on_delete=models.CASCADE)
    pick_count = models.IntegerField(default=0)
    pick_percent = models.FloatField(default=0)
    rarity_tier = models.CharField(max_length=16)
    is_correct = models.BooleanField(default=True)

    class Meta:
        unique_together = [('daily_slot', 'player')]
        constraints = [
            models.CheckConstraint(check=Q(pick_count__gte=0), name='snapshot_count_nonnegative'),
            models.CheckConstraint(check=Q(pick_percent__gte=0, pick_percent__lte=100), name='snapshot_percent_0_100'),
        ]

    def __str__(self):
        return f"{self.daily_slot} – {self.player} {self.pick_percent:.2f}% {self.rarity_tier}"

class ScoringConfig(models.Model):
    # Display-only upper bounds; rarity tiers never change percentage deductions.
    is_active = models.BooleanField(default=True)

    threshold_rare = models.FloatField(default=15.0)
    threshold_epic = models.FloatField(default=5.0)
    threshold_legendary = models.FloatField(default=2.0)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(check=(
            Q(threshold_legendary__gte=0, threshold_legendary__lte=F('threshold_epic'))
            & Q(threshold_epic__lte=F('threshold_rare'), threshold_rare__lte=100)
        ), name='scoring_thresholds_ordered')]

    def __str__(self):
        return f"ScoringConfig active={self.is_active}"

    @classmethod
    def get_active(cls):
        obj = cls.objects.filter(is_active=True).first()
        if not obj:
            obj = cls.objects.create(is_active=True)
        return obj
