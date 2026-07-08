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

    def __str__(self):
        return f"{self.daily} – {self.get_role_display()}"

class DailySlotCondition(models.Model):
    CONDITION_TYPE = [
        ('role', 'Role'),
        ('region', 'Region'),
        ('residency', 'Residency'),
        ('country', 'Country'),
        ('continent', 'Continent'),
        ('team', 'Team'),
        ('league', 'League'),
        ('worlds_appearance', 'Worlds appearance'),
        ('worlds_champion', 'Worlds champion'),
        ('msi_appearance', 'MSI appearance'),
        ('coach', 'Coach'),
        ('champion_played', 'Champion played'),
        ('birth_year_range', 'Birth year range'),
        ('active', 'Active'),
        ('worlds_titles_min', 'Worlds titles min'),
    ]
    OPERATOR_CHOICES = [
        ('eq', 'Equals'),
        ('in', 'In'),
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
