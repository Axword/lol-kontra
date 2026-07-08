from celery import shared_task
from django.utils import timezone
from apps.dailies.models import Daily
from .engine import score_daily

@shared_task
def nightly_scoring():
    """Uruchamiane po zamknięciu Daily"""
    today = timezone.localdate()
    # score wczorajszy
    try:
        daily = Daily.objects.get(date=today)
        # close it
        if daily.status == 'published':
            daily.status = 'closed'
            daily.closed_at = timezone.now()
            daily.save(update_fields=['status', 'closed_at'])
    except Daily.DoesNotExist:
        pass
    yesterday = today - timezone.timedelta(days=1)
    try:
        daily = Daily.objects.get(date=yesterday)
        score_daily(daily.id)
        daily.status = 'scored'
        daily.save(update_fields=['status'])
        return f"Scored daily {daily.id}"
    except Daily.DoesNotExist:
        return "No daily to score"

@shared_task
def score_daily_task(daily_id: int):
    return score_daily(daily_id)
