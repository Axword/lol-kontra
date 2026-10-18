"""Permanent metadata for the first real successful choice of a slot/player."""
from django.db import transaction

from apps.dailies.models import Daily, DailySlot
from apps.submissions.models import SubmissionAnswer, SubmissionAttempt


@transaction.atomic
def award_first_pick(answer):
    if not answer.is_correct or answer.submission.is_practice or answer.submission.is_seed:
        return False
    # Reentrant under normal gameplay's existing locks, and safe if this helper
    # is called independently. Different guests cannot both claim the first hit.
    Daily.objects.select_for_update().get(pk=answer.daily_slot.daily_id)
    list(DailySlot.objects.select_for_update().filter(
        daily_id=answer.daily_slot.daily_id,
    ).order_by('pk').values_list('pk', flat=True))
    saved = SubmissionAnswer.objects.get(pk=answer.pk)
    if saved.is_diamond_pick:
        answer.is_diamond_pick = True
        answer.diamond_awarded_at = saved.diamond_awarded_at
        return True
    earlier = SubmissionAnswer.objects.filter(
        daily_slot_id=answer.daily_slot_id, player_id=answer.player_id,
        is_correct=True, submission__is_practice=False, submission__is_seed=False,
    ).exclude(pk=answer.pk)
    if earlier.exists():
        return False
    success = SubmissionAttempt.objects.filter(
        submission_id=answer.submission_id, daily_slot_id=answer.daily_slot_id,
        player_id=answer.player_id, is_correct=True,
    ).order_by('created_at', 'pk').first()
    awarded_at = success.created_at if success else answer.submission.submitted_at
    SubmissionAnswer.objects.filter(pk=answer.pk).update(
        is_diamond_pick=True, diamond_awarded_at=awarded_at,
    )
    answer.is_diamond_pick = True
    answer.diamond_awarded_at = awarded_at
    return True
