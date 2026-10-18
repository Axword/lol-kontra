from apps.dailies.validators import player_matches_slot


def is_practice_daily(daily):
    """Compatibility helper: archived games now count for their own daily."""
    return False


def validate_and_score_answer(answer_obj):
    """Validate under the caller's slot lock. Diamond bonuses are retired."""
    answer_obj.is_correct = player_matches_slot(answer_obj.player, answer_obj.daily_slot)
    answer_obj.is_diamond_pick = False
    answer_obj.diamond_awarded_at = None
    answer_obj.save(update_fields=['is_correct', 'is_diamond_pick', 'diamond_awarded_at'])
    return answer_obj.is_correct
