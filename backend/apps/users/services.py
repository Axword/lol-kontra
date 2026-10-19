from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.submissions.models import MAX_ERRORS, Submission
from .models import UserStats


@transaction.atomic
def refresh_user_stats(user_id):
    """Rebuild from finished games so retries and rescoring never double count."""
    get_user_model().objects.select_for_update().get(pk=user_id)
    stats, _ = UserStats.objects.get_or_create(user_id=user_id)
    games = list(Submission.objects.filter(user_id=user_id, is_practice=False, is_seed=False).annotate(
        slot_count=Count('daily__slots', distinct=True),
        correct_count=Count('answers', filter=Q(answers__is_correct=True), distinct=True),
    ).select_related('daily').order_by('daily__date'))
    games = [game for game in games if game.is_scored or game.errors_used >= MAX_ERRORS
             or (game.slot_count > 0 and game.correct_count >= game.slot_count)]
    stats.games_played = len(games)
    stats.total_points = sum(game.total_points for game in games)
    stats.avg_points = stats.total_points / len(games) if games else 0
    stats.best_score = min((game.total_points for game in games), default=0)
    answers = [answer for game in games for answer in game.answers.filter(is_correct=True)]
    stats.legendary_answers = sum(answer.rarity_tier == 'legendary' for answer in answers)
    stats.diamond_picks = sum(answer.is_diamond_pick for answer in answers)
    streak = longest = 0
    previous = None
    for game in games:
        streak = streak + 1 if previous and game.daily.date == previous + timedelta(days=1) else 1
        longest = max(longest, streak)
        previous = game.daily.date
    stats.max_streak = longest
    stats.current_streak = streak if previous and previous >= timezone.localdate() - timedelta(days=1) else 0
    stats.save()
    return stats
