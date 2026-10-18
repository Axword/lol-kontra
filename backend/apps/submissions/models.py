from django.db import models
from django.conf import settings
from django.db.models import F, Q

# Ile pomyłek gracz może popełnić na jednej planszy. Jedno miejsce w całym projekcie –
# frontend pobiera tę wartość z API, nie trzyma własnej kopii.
MAX_ERRORS = 10
STARTING_POINTS = 500
UNFILLED_SLOT_DEDUCTION = 100


class Submission(models.Model):
    daily = models.ForeignKey('dailies.Daily', on_delete=models.CASCADE, related_name='submissions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    guest_token = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    ip_hash = models.CharField(max_length=64, blank=True)
    is_scored = models.BooleanField(default=False)
    is_practice = models.BooleanField(default=False)
    is_seed = models.BooleanField(default=False)

    # 500 minus the pick percentages and final unfilled-slot deductions.
    total_points = models.FloatField(default=500.0)

    # Licznik pomyłek prowadzony po stronie serwera – klient go tylko wyświetla.
    errors_used = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['daily', 'user', 'is_practice'], condition=Q(user__isnull=False), name='uniq_daily_user_mode'),
            models.UniqueConstraint(fields=['daily', 'guest_token', 'is_practice'], condition=Q(guest_token__isnull=False), name='uniq_daily_guest_mode'),
            models.CheckConstraint(check=Q(total_points__gte=0, total_points__lte=500), name='sub_score_0_500'),
            models.CheckConstraint(check=Q(errors_used__gte=0, errors_used__lte=10), name='sub_errors_0_10'),
            models.CheckConstraint(check=(
                Q(user__isnull=False, guest_token__isnull=True)
                | Q(user__isnull=True, guest_token__isnull=False, guest_token__regex=r'[^[:space:]]')
            ), name='sub_exactly_one_identity'),
            models.CheckConstraint(check=(Q(is_seed=False) | Q(is_practice=False, user__isnull=True)), name='sub_seed_guest_official'),
        ]
        ordering = ['-submitted_at']

    def __str__(self):
        who = self.user or f"guest:{(self.guest_token or '')[:8]}"
        return f"{self.daily} – {who}"

    @property
    def errors_left(self) -> int:
        return max(0, MAX_ERRORS - self.errors_used)

    @property
    def is_over(self) -> bool:
        """Gra kończy się po wyczerpaniu błędów albo po zamknięciu wszystkich slotów."""
        if self.errors_used >= MAX_ERRORS:
            return True
        slots_total = self.daily.slots.count()
        if slots_total == 0:
            return False
        return self.answers.filter(is_correct=True).count() >= slots_total


class SubmissionAnswer(models.Model):
    """Aktualny (i po trafieniu – ostateczny) wybór gracza na danym slocie."""

    RARITY_CHOICES = [
        ('common', 'Common'),
        ('uncommon', 'Uncommon'),
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

    # Signed correction: -1 means one point deducted, never a tier bonus.
    points_awarded = models.FloatField(default=0.0)
    scoring_pick_count = models.PositiveIntegerField(default=0)
    scoring_sample_size = models.PositiveIntegerField(default=0)

    is_diamond_pick = models.BooleanField(default=False)
    diamond_awarded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [('submission', 'daily_slot')]
        constraints = [
            models.CheckConstraint(check=Q(points_awarded__gte=-100, points_awarded__lte=0), name='answer_deduction_minus100_0'),
            models.CheckConstraint(check=Q(is_correct=True) | Q(points_awarded=0), name='answer_wrong_has_zero_points'),
            models.CheckConstraint(check=Q(rarity_percent__isnull=True) | Q(rarity_percent__gte=0, rarity_percent__lte=100), name='answer_percent_0_100'),
            models.CheckConstraint(check=Q(scoring_pick_count__lte=F('scoring_sample_size')), name='answer_count_within_sample'),
            models.UniqueConstraint(fields=['submission', 'player'], condition=Q(is_correct=True), name='uniq_correct_player_per_sub'),
            models.UniqueConstraint(
                fields=['daily_slot', 'player'],
                condition=Q(is_diamond_pick=True),
                name='uniq_diamond_per_slot_player',
            )
        ]

    def __str__(self):
        return f"{self.submission_id} slot {self.daily_slot_id} -> {self.player}"


class SubmissionAttempt(models.Model):
    """
    Pełna historia prób – każde kliknięcie gracza, także nietrafione.

    Dzięki temu licznik błędów jest prowadzony serwerowo (klient nie może go obejść),
    a po zakończeniu gry da się pokazać przebieg rozgrywki.
    """
    submission = models.ForeignKey(Submission, related_name='attempts', on_delete=models.CASCADE)
    daily_slot = models.ForeignKey('dailies.DailySlot', on_delete=models.CASCADE)
    player = models.ForeignKey('players.Player', on_delete=models.PROTECT)
    is_correct = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [models.Index(fields=['submission', 'daily_slot'], name='submissions_sub_slot_idx')]

    def __str__(self):
        mark = 'OK' if self.is_correct else 'X'
        return f"[{mark}] {self.player} @ slot {self.daily_slot_id}"
