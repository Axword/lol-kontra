from django.db import models
from django.conf import settings
from django.db.models import Q

class Submission(models.Model):
    daily = models.ForeignKey('dailies.Daily', on_delete=models.CASCADE, related_name='submissions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    guest_token = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    ip_hash = models.CharField(max_length=64, blank=True)
    is_scored = models.BooleanField(default=False)
    total_points = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['daily', 'user'], condition=Q(user__isnull=False), name='uniq_daily_user'),
            models.UniqueConstraint(fields=['daily', 'guest_token'], condition=Q(guest_token__isnull=False), name='uniq_daily_guest'),
        ]
        ordering = ['-submitted_at']

    def __str__(self):
        who = self.user or f"guest:{self.guest_token[:8]}"
        return f"{self.daily} – {who}"

class SubmissionAnswer(models.Model):
    RARITY_CHOICES = [
        ('common', 'Common'),
        ('rare', 'Rare'),
        ('epic', 'Epic'),
        ('legendary', 'Legendary'),
    ]
    submission = models.ForeignKey(Submission, related_name='answers', on_delete=models.CASCADE)
    daily_slot = models.ForeignKey('dailies.DailySlot', on_delete=models.PROTECT)
    player = models.ForeignKey('players.Player', on_delete=models.PROTECT)
    is_correct = models.BooleanField(default=False)
    rarity_tier = models.CharField(max_length=16, choices=RARITY_CHOICES, null=True, blank=True)
    rarity_percent = models.FloatField(null=True, blank=True)
    points_awarded = models.IntegerField(default=0)
    is_diamond_pick = models.BooleanField(default=False)
    diamond_awarded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [('submission', 'daily_slot')]
        constraints = [
            models.UniqueConstraint(fields=['daily_slot', 'player'], condition=Q(is_diamond_pick=True), name='uniq_diamond_per_slot_player')
        ]

    def __str__(self):
        return f"{self.submission_id} slot {self.daily_slot_id} -> {self.player}"
