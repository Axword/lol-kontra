from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from apps.dailies.validators import player_matches_slot

def try_award_diamond_pick(daily_slot, player, submission_id, timeout=48*3600):
    """
    Redis SETNX first-write-wins.
    Returns True if awarded.
    """
    key = f"diamond:{daily_slot.daily_id}:{daily_slot.id}:{player.id}"
    # cache.add = SETNX
    added = cache.add(key, submission_id, timeout=timeout)
    return added

def validate_and_score_answer(answer_obj):
    """
    Waliduje poprawność odpowiedzi, przyznaje Diamond jeśli pierwszy.
    Nie liczy rarity – to robi nightly job.
    """
    player = answer_obj.player
    slot = answer_obj.daily_slot

    is_correct = player_matches_slot(player, slot)
    answer_obj.is_correct = is_correct

    if is_correct:
        awarded = try_award_diamond_pick(slot, player, answer_obj.submission_id)
        if awarded:
            answer_obj.is_diamond_pick = True
            answer_obj.diamond_awarded_at = timezone.now()
    answer_obj.save(update_fields=['is_correct', 'is_diamond_pick', 'diamond_awarded_at'])
    return is_correct
