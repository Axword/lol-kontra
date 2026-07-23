from django.db import models
from django.conf import settings
from django.db.models import Q

class Submission(models.Model):
    daily = models.ForeignKey('dailies.Daily', on_delete=models.CASCADE, related_name='submissions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    guest_token = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    ip_hash = models.CharField(max_length=64, blank=True)
    is_scored = models.BooleanField(default=False, db_index=True)
    # FIX: FloatField — scoring uses decimal deductions (97.5, 85.3 etc.)
    total_points = models.FloatField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['daily', 'user'], condition=Q(user__isnull=False), name='uniq_daily_user'),
            models.UniqueConstraint(fields=['daily', 'guest_token'], condition=Q(guest_token__isnull=False), name='uniq_daily_guest'),
        ]
        indexes = [
            # Composite index for scoring queries: filter by daily + is_scored
            models.Index(fields=['daily', 'is_scored'], name='idx_submission_daily_scored'),
        ]
        ordering = ['-submitted_at']

    def __str__(self):
        who = self.user or f"guest:{(self.guest_token or '?')[:8]}"
        return f"{self.daily} – {who}"

class SubmissionAnswer(models.Model):
    RARITY_CHOICES = [
        ('common', 'Common'),
        ('rare', 'Rare'),
        ('epic', 'Epic'),
        ('legendary', 'Legendary'),
    ]
    submission = models.ForeignKey(Submission, related_name='answers', on_delete=models.CASCADE)
    daily_slot = models.ForeignKey('dailies.DailySlot', on_delete=models.PROTECT, related_name='answers')
    player = models.ForeignKey('players.Player', on_delete=models.PROTECT, related_name='submission_answers')
    is_correct = models.BooleanField(default=False, db_index=True)
    rarity_tier = models.CharField(max_length=16, choices=RARITY_CHOICES, null=True, blank=True)
    rarity_percent = models.FloatField(null=True, blank=True)
    # FIX: FloatField — deduction is 100 - pick_percent (e.g. 97.5), not an integer
    points_awarded = models.FloatField(default=0)
    is_diamond_pick = models.BooleanField(default=False, db_index=True)
    diamond_awarded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [('submission', 'daily_slot')]
        constraints = [
            models.UniqueConstraint(fields=['daily_slot', 'player'], condition=Q(is_diamond_pick=True), name='uniq_diamond_per_slot_player')
        ]
        indexes = [
            # For scoring engine: filter by daily_slot + is_correct
            models.Index(fields=['daily_slot', 'is_correct'], name='idx_answer_slot_correct'),
            # For stats: group by daily_slot + player
            models.Index(fields=['daily_slot', 'player'], name='idx_answer_slot_player'),
        ]

    def __str__(self):
        return f"{self.submission_id} slot {self.daily_slot_id} -> {self.player}"
