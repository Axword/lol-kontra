from django.db.models import Count, Sum
from apps.submissions.models import SubmissionAnswer, Submission
from apps.scoring.models import AnswerStatsDaily, ScoringConfig
from apps.dailies.models import DailySlot

# Kontra.games style scoring
# Start: 500
# For each correct answer: deduction = 100 - pick_percent
# Diamond first pick: deduction = 100
# Lower total is better. We go down.

START_SCORE = 500.0

def score_daily(daily_id: int):
    cfg = ScoringConfig.get_active()
    daily_slots = DailySlot.objects.filter(daily_id=daily_id)

    for slot in daily_slots:
        answers_qs = SubmissionAnswer.objects.filter(daily_slot=slot, is_correct=True)
        # Count distinct submissions that answered this slot correctly
        total = answers_qs.values('submission').distinct().count()
        if total == 0:
            continue

        agg = answers_qs.values('player').annotate(pick_count=Count('id'))
        AnswerStatsDaily.objects.filter(daily_slot=slot).delete()

        stats_bulk = []
        for row in agg:
            player_id = row['player']
            pick_count = row['pick_count']
            pick_percent = (pick_count / total) * 100.0

            if pick_percent > cfg.threshold_rare:
                tier = 'common'
            elif pick_percent > cfg.threshold_epic:
                tier = 'rare'
            elif pick_percent > cfg.threshold_legendary:
                tier = 'epic'
            else:
                tier = 'legendary'

            deduction = round(100.0 - pick_percent, 1)

            stats_bulk.append(AnswerStatsDaily(
                daily_slot=slot,
                player_id=player_id,
                pick_count=pick_count,
                pick_percent=pick_percent,
                rarity_tier=tier,
                is_correct=True
            ))

            # FIX: points_awarded is now FloatField — no truncation
            upd_qs = SubmissionAnswer.objects.filter(daily_slot=slot, player_id=player_id, is_correct=True)
            upd_qs.update(
                rarity_tier=tier,
                rarity_percent=pick_percent,
                points_awarded=deduction,
            )

        AnswerStatsDaily.objects.bulk_create(stats_bulk)

        # Diamond pick: flat 100 deduction
        diamond_qs = SubmissionAnswer.objects.filter(daily_slot=slot, is_diamond_pick=True)
        diamond_qs.update(points_awarded=100.0)

    # Update submission totals
    # FIX: total_points is now FloatField — store actual score directly (no *10 encoding)
    submissions = Submission.objects.filter(daily_id=daily_id)
    for sub in submissions:
        total_deduction = sub.answers.aggregate(s=Sum('points_awarded'))['s'] or 0
        final_score = round(START_SCORE - float(total_deduction), 1)
        sub.total_points = final_score
        sub.is_scored = True
        sub.save(update_fields=['total_points', 'is_scored'])

    return True
