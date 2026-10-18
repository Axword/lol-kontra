"""Post-game choices and optimal five-person rosters, using actual vote counts."""
from itertools import product

from django.db.models import Count

from apps.players.serializers import PlayerAutocompleteSerializer
from apps.submissions.models import SubmissionAnswer

from .generator import count_candidates


def recommended_roster(slots, popular):
    # With five slots, an optimum always exists among each slot's top five:
    # at most four better candidates can be occupied by the other positions.
    options = [sorted(slot['players'], key=lambda player: (
        -player['pick_percent'] if popular else player['pick_percent'], player['slug']))[:len(slots)]
               for slot in slots]
    best, best_cost = None, None
    for roster in product(*options):
        if len({player['id'] for player in roster}) != len(slots):
            continue
        cost = sum(player['pick_percent'] for player in roster)
        if best is None or (cost > best_cost if popular else cost < best_cost):
            best, best_cost = roster, cost
    return {str(slot['slot_id']): player['id'] for slot, player in zip(slots, best)} if best else {}


def daily_solutions(daily):
    slots = []
    for slot in daily.slots.prefetch_related('conditions').order_by('position'):
        votes = SubmissionAnswer.objects.filter(
            daily_slot=slot, is_correct=True, submission__is_practice=False, submission__is_seed=False,
        )
        counts = dict(votes.values('player_id').annotate(n=Count('id')).values_list('player_id', 'n'))
        total = sum(counts.values())
        players = []
        for player in count_candidates(slot):
            players.append({**PlayerAutocompleteSerializer(player).data,
                            'pick_count': counts.get(player.id, 0),
                            'pick_percent': counts.get(player.id, 0) * 100 / total if total else 0})
        players.sort(key=lambda player: (-player['pick_count'], player['nickname'].casefold(), player['slug']))
        slots.append({'slot_id': slot.id, 'role': slot.role, 'sample_size': total, 'players': players})
    return {'daily_id': daily.id, 'slots': slots, 'popular': recommended_roster(slots, True),
            'rare': recommended_roster(slots, False)}
