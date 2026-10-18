from django.db import models
from django.conf import settings

ROLE_CHOICES = [
    ('top', 'Top'),
    ('jungle', 'Jungle'),
    ('mid', 'Mid'),
    ('adc', 'ADC'),
    ('support', 'Support'),
]

class Daily(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('closed', 'Closed'),
        ('scored', 'Scored'),
    ]
    REVEAL_CHOICES = [
        ('instant', 'Instant'),
        # after_close removed – 2026-07-07 per product decision
    ]

    date = models.DateField(unique=True, db_index=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='draft')
    locale_seed = models.CharField(max_length=64, blank=True)
    reveal_mode = models.CharField(max_length=16, choices=REVEAL_CHOICES, default='instant')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    published_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']
        verbose_name_plural = 'Dailies'
        constraints = [
            models.CheckConstraint(check=models.Q(status__in=['draft', 'published', 'closed', 'scored']), name='daily_status_valid'),
            models.CheckConstraint(check=models.Q(reveal_mode='instant'), name='daily_reveal_mode_valid'),
            models.CheckConstraint(check=models.Q(published_at__isnull=True) | models.Q(closed_at__isnull=True) | models.Q(closed_at__gte=models.F('published_at')), name='daily_timestamps_ordered'),
        ]

    def __str__(self):
        return f"Daily #{self.id} – {self.date}"

class DailySlot(models.Model):
    daily = models.ForeignKey(Daily, related_name='slots', on_delete=models.CASCADE)
    position = models.IntegerField()  # 1..5
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    label_pl = models.CharField(max_length=128, blank=True)
    label_en = models.CharField(max_length=128, blank=True)

    class Meta:
        unique_together = [('daily', 'position'), ('daily', 'role')]
        ordering = ['position']
        constraints = [
            models.CheckConstraint(check=models.Q(position__range=(1, 5)), name='daily_slot_position_valid'),
            models.CheckConstraint(check=models.Q(role__in=[role for role, _ in ROLE_CHOICES]), name='daily_slot_role_valid'),
        ]

    def __str__(self):
        return f"{self.daily} – {self.get_role_display()}"

class DailySlotCondition(models.Model):
    CONDITION_TYPE = [
        # podstawowe
        ('role', 'Rola'),
        ('region', 'Region'),
        ('residency', 'Residency'),
        ('country', 'Kraj'),
        ('continent', 'Kontynent'),
        ('team', 'Drużyna'),
        ('team_year', 'Drużyna w konkretnym roku'),
        ('league', 'Liga'),
        ('coach', 'Trener'),
        ('active', 'Aktywny / emerytowany'),
        ('birth_year_range', 'Rok urodzenia'),
        ('champion_played', 'Grał championem'),
        # Worlds – występy
        ('worlds_appearance', 'Występ na Worlds'),
        ('worlds_count_min', 'Min. liczba występów na Worlds'),
        ('worlds_debut_year', 'Debiut na Worlds'),
        ('worlds_last_year', 'Ostatni Worlds'),
        ('worlds_early_era', 'Worlds w erze S1-S3'),
        ('worlds_teams_min', 'Min. liczba organizacji na Worlds'),
        ('worlds_multi_role', 'Worlds na kilku rolach'),
        # Worlds – osiągnięcia
        ('worlds_champion', 'Mistrz Worlds'),
        ('worlds_titles_min', 'Min. liczba tytułów Worlds'),
        ('worlds_final', 'Finał Worlds'),
        ('worlds_final_lost', 'Przegrany finał Worlds'),
        ('worlds_semifinal', 'Półfinał Worlds'),
        ('worlds_group_escape', 'Wyjście z grupy'),
        ('worlds_never_escaped', 'Nigdy nie wyszedł z grupy'),
        ('worlds_never_won', 'Nigdy nie wygrał Worlds'),
        ('worlds_playin', 'Przeszedł play-in'),
        ('pentakill_worlds', 'Pentakill na Worlds'),
        ('worlds_win_rate', 'Win rate na Worlds'),
        ('worlds_games', 'Liczba meczów na Worlds'),
        ('worlds_top5_champion', 'Champion w top 5 na Worlds'),
        ('career_top5_champion', 'Champion w top 5 kariery'),
        ('worlds_eliminated_stage', 'Etap odpadnięcia z Worlds'),
        # inne
        ('msi_appearance', 'Występ na MSI'),
        ('leagues_min', 'Min. liczba lig głównych'),
        ('wildcard_region', 'Region wildcard'),
        ('import_player', 'Import (gra poza swoim regionem)'),
    ]
    OPERATOR_CHOICES = [
        ('eq', 'Equals'),
        ('in', 'In'),
        ('gt', '>'),
        ('lt', '<'),
        ('gte', '>='),
        ('lte', '<='),
        ('any', 'Any'),
    ]

    slot = models.ForeignKey(DailySlot, related_name='conditions', on_delete=models.CASCADE)
    condition_type = models.CharField(max_length=32, choices=CONDITION_TYPE)
    operator = models.CharField(max_length=8, choices=OPERATOR_CHOICES, default='eq')
    value = models.JSONField()
    label_pl = models.CharField(max_length=256)
    label_en = models.CharField(max_length=256)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']
        constraints = [
            models.CheckConstraint(check=models.Q(operator__in=['eq', 'in', 'gt', 'lt', 'gte', 'lte', 'any']), name='daily_condition_operator_valid'),
            models.CheckConstraint(check=models.Q(order__gte=0), name='daily_condition_order_gte0'),
        ]
