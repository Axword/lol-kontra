"""Change score direction using saved percentages, never a new vote sample."""
import math
from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.db import migrations
from django.db.models import Count
from django.utils import timezone


def recalculate_saved_scores(apps, schema_editor):
    alias = schema_editor.connection.alias
    Daily = apps.get_model('dailies', 'Daily')
    Slot = apps.get_model('dailies', 'DailySlot')
    Game = apps.get_model('submissions', 'Submission')
    Answer = apps.get_model('submissions', 'SubmissionAnswer')
    Stats = apps.get_model('users', 'UserStats')
    User = apps.get_model(settings.AUTH_USER_MODEL)
    # Same lock order as live submissions. Percentages, attempts, choices and
    # permanent first-pick metadata are never rewritten by this migration.
    list(Daily.objects.using(alias).select_for_update().order_by('pk').values_list('pk', flat=True))
    list(Slot.objects.using(alias).select_for_update().order_by('pk').values_list('pk', flat=True))
    games = list(Game.objects.using(alias).select_for_update().filter(is_seed=False).select_related('daily').order_by('pk'))
    list(User.objects.using(alias).select_for_update().filter(
        pk__in=Stats.objects.using(alias).values('user_id'),
    ).order_by('pk').values_list('pk', flat=True))
    counts = dict(Slot.objects.using(alias).values('daily_id').annotate(n=Count('pk')).values_list('daily_id', 'n'))
    answers = defaultdict(list)
    for answer in Answer.objects.using(alias).filter(submission__is_seed=False).order_by('pk'):
        percent = answer.rarity_percent
        if percent is not None and (not math.isfinite(percent) or not 0 <= percent <= 100):
            raise RuntimeError('Cannot migrate an invalid saved pick percentage')
        # A legacy answer without a known percentage gets the same cost as a
        # missing answer; it cannot become a zero-point perfect choice.
        cost = 100.0 if percent is None else percent
        Answer.objects.using(alias).filter(pk=answer.pk).update(points_awarded=cost - 100 if answer.is_correct else 0.0)
        if answer.is_correct:
            answers[answer.submission_id].append((answer, cost))
    user_games = defaultdict(list)
    for game in games:
        correct = answers[game.pk]
        slots = counts.get(game.daily_id, 0)
        total = sum(cost for _, cost in correct) + 100 * max(0, slots - len(correct)) if slots else 500.0
        total = round(max(0.0, min(500.0, total)), 6)
        Game.objects.using(alias).filter(pk=game.pk).update(total_points=total)
        game.total_points = total
        if game.user_id and not game.is_practice and (game.is_scored or game.errors_used >= 10 or slots > 0 and len(correct) >= slots):
            user_games[game.user_id].append(game)
    today = timezone.localdate()
    for stats in Stats.objects.using(alias).all():
        completed = sorted(user_games[stats.user_id], key=lambda game: game.daily.date)
        total = sum(game.total_points for game in completed)
        selected = [answer for game in completed for answer, _ in answers[game.pk]]
        streak = longest = 0
        previous = None
        for game in completed:
            streak = streak + 1 if previous and game.daily.date == previous + timedelta(days=1) else 1
            longest = max(longest, streak)
            previous = game.daily.date
        Stats.objects.using(alias).filter(pk=stats.pk).update(
            games_played=len(completed), total_points=total,
            avg_points=total / len(completed) if completed else 0,
            best_score=min((game.total_points for game in completed), default=0),
            legendary_answers=sum(answer.rarity_tier == 'legendary' for answer in selected),
            diamond_picks=sum(answer.is_diamond_pick for answer in selected),
            current_streak=streak if previous and previous >= today - timedelta(days=1) else 0,
            max_streak=longest,
        )


class Migration(migrations.Migration):
    dependencies = [
        ('scoring', '0006_uncommon_and_permanent_first_picks'),
        ('users', '0006_guestprofile_nickname_history'),
        ('submissions', '0006_uncommon_rarity'),
    ]
    operations = [migrations.RunPython(recalculate_saved_scores, migrations.RunPython.noop)]
