"""500 starting points minus pick percentages; higher scores are better.

Live deductions use official choices recorded before the current answer. They
stay fixed until final scoring. Final scoring uses the full official population.
Rarity tiers remain legacy metadata and never affect points.
"""
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from apps.dailies.models import Daily, DailySlot
from apps.scoring.models import AnswerStatsDaily, ScoringConfig
from apps.submissions.models import STARTING_POINTS, UNFILLED_SLOT_DEDUCTION, Submission, SubmissionAnswer
from apps.users.services import refresh_user_stats

MIN_SAMPLE = 25


def tier_for_percent(pick_percent: float, cfg: ScoringConfig = None) -> str:
    """Legacy display metadata; tiers never award points."""
    cfg = cfg or ScoringConfig.get_active()
    if pick_percent > cfg.threshold_rare:
        return 'common'
    if pick_percent > cfg.threshold_epic:
        return 'rare'
    if pick_percent > cfg.threshold_legendary:
        return 'epic'
    return 'legendary'


def slot_pick_stats(slot_id: int, player_id: int, *, exclude_answer_id=None):
    qs = SubmissionAnswer.objects.filter(
        daily_slot_id=slot_id, is_correct=True, submission__is_practice=False,
    )
    if exclude_answer_id is not None:
        qs = qs.exclude(pk=exclude_answer_id)
    total = qs.count()
    count = qs.filter(player_id=player_id).count() if total else 0
    return count, total, count / total * 100.0 if total else 0.0


def answer_pick_stats(answer_obj, *, final=False):
    """A new official answer does not count itself in its live population."""
    if final or answer_obj.daily_slot.daily.status == 'scored':
        snapshot = AnswerStatsDaily.objects.filter(daily_slot_id=answer_obj.daily_slot_id)
        total = snapshot.aggregate(n=Sum('pick_count'))['n'] or 0
        if total:
            picked = snapshot.filter(player_id=answer_obj.player_id).first()
            count = picked.pick_count if picked else 0
            return count, total, count / total * 100.0, True
    exclude_id = None if final or answer_obj.submission.is_practice else answer_obj.pk
    return (*slot_pick_stats(answer_obj.daily_slot_id, answer_obj.player_id, exclude_answer_id=exclude_id), False)


def compute_rarity(answer_obj, cfg: ScoringConfig = None, *, final=False):
    """Save a percentage deduction and the population used to compute it."""
    cfg = cfg or ScoringConfig.get_active()
    if answer_obj.is_correct:
        count, total, percent, final_sample = answer_pick_stats(answer_obj, final=final)
        tier = tier_for_percent(percent, cfg)
        points = -percent if percent else 0.0
        provisional = total == 0 or (not final_sample and total < MIN_SAMPLE)
    else:
        count, total, percent, tier, points, provisional = 0, 0, None, None, 0.0, False
    answer_obj.rarity_tier = tier
    answer_obj.rarity_percent = percent
    answer_obj.points_awarded = points
    answer_obj.scoring_pick_count = count
    answer_obj.scoring_sample_size = total
    answer_obj.is_diamond_pick = False
    answer_obj.diamond_awarded_at = None
    answer_obj.save(update_fields=[
        'rarity_tier', 'rarity_percent', 'points_awarded', 'scoring_pick_count',
        'scoring_sample_size', 'is_diamond_pick', 'diamond_awarded_at',
    ])
    return {
        'tier': tier, 'pick_percent': percent, 'pick_count': count,
        'sample_size': total, 'points': points, 'provisional': provisional,
    }


def unfilled_deduction(submission) -> float:
    if not submission.is_over and not submission.is_scored:
        return 0.0
    missing = max(0, submission.daily.slots.count() - submission.answers.filter(is_correct=True).count())
    return float(missing * UNFILLED_SLOT_DEDUCTION)


def recalc_submission_total(submission) -> float:
    correction = submission.answers.filter(is_correct=True).aggregate(s=Sum('points_awarded'))['s'] or 0.0
    total = STARTING_POINTS + correction - unfilled_deduction(submission)
    submission.total_points = round(max(0.0, min(float(STARTING_POINTS), total)), 6)
    submission.save(update_fields=['total_points'])
    return submission.total_points


@transaction.atomic
def score_daily(daily_id: int, *, finalize=None):
    """Rebuild shares and scores atomically without changing board publication.

    ``finalize=None`` finalizes closed past boards. ``finalize=False`` also
    prepares seed votes for current/future boards and updates late archive games
    without closing unfinished games. Explicit True never finalizes a future or
    currently published board.
    """
    daily = Daily.objects.select_for_update().get(pk=daily_id)
    can_finalize = daily.date < timezone.localdate() and daily.status in {'closed', 'scored'}
    finalize = can_finalize if finalize is None else bool(finalize and can_finalize)
    cfg = ScoringConfig.get_active()
    slots = list(DailySlot.objects.select_for_update().filter(daily_id=daily_id).order_by('pk'))
    for slot in slots:
        correct = SubmissionAnswer.objects.filter(
            daily_slot=slot, is_correct=True, submission__is_practice=False,
        )
        total = correct.count()
        AnswerStatsDaily.objects.filter(daily_slot=slot).delete()
        stats = []
        for row in correct.values('player').annotate(pick_count=Count('id')):
            percent = row['pick_count'] / total * 100.0
            tier = tier_for_percent(percent, cfg)
            stats.append(AnswerStatsDaily(
                daily_slot=slot, player_id=row['player'], pick_count=row['pick_count'],
                pick_percent=percent, rarity_tier=tier, is_correct=True,
            ))
            correct.filter(player_id=row['player']).update(
                rarity_tier=tier, rarity_percent=percent, points_awarded=-percent,
                scoring_pick_count=row['pick_count'], scoring_sample_size=total,
                is_diamond_pick=False, diamond_awarded_at=None,
            )
        AnswerStatsDaily.objects.bulk_create(stats)

    # Only colliding historical practice games retain this legacy flag. They
    # remain preserved but never alter the official population or leaderboard.
    for answer in SubmissionAnswer.objects.filter(
        daily_slot__daily_id=daily_id, submission__is_practice=True,
    ).select_related('daily_slot__daily', 'submission'):
        compute_rarity(answer, cfg, final=True)
    SubmissionAnswer.objects.filter(daily_slot__daily_id=daily_id, is_correct=False).update(
        points_awarded=0.0, rarity_tier=None, rarity_percent=None,
        scoring_pick_count=0, scoring_sample_size=0, is_diamond_pick=False, diamond_awarded_at=None,
    )

    for submission in Submission.objects.select_for_update().filter(daily_id=daily_id).select_related('daily'):
        if finalize and not submission.is_practice:
            submission.is_scored = True
            submission.save(update_fields=['is_scored'])
        recalc_submission_total(submission)

    user_ids = Submission.objects.filter(
        daily_id=daily_id, user__isnull=False, is_practice=False, is_seed=False,
    ).order_by('user_id').values_list('user_id', flat=True).distinct()
    for user_id in user_ids:
        refresh_user_stats(user_id)
    return True
