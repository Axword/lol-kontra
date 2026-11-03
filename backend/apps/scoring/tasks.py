from celery import shared_task
from django.utils import timezone
from apps.dailies.models import Daily
from .engine import score_daily

@shared_task
def nightly_scoring():
    """Uruchamiane po zamknięciu Daily"""
    today = timezone.localdate()
    yesterday = today - timezone.timedelta(days=1)
    scored = []
    for daily in Daily.objects.filter(date=yesterday, status__in=['published', 'closed', 'scored']).order_by('pk'):
        if daily.status == 'published':
            daily.status = 'closed'
            daily.closed_at = timezone.now()
            daily.save(update_fields=['status', 'closed_at'])
        score_daily(daily.id)
        daily.status = 'scored'
        daily.save(update_fields=['status'])
        scored.append(daily.id)
    if len(scored) == 1:
        return f"Scored daily {scored[0]}"
    return f"Scored dailies {scored}" if scored else "No daily to score"

@shared_task
def score_daily_task(daily_id: int):
    return score_daily(daily_id)
