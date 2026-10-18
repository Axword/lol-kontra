import uuid

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.dailies.models import Daily, DailySlot
from apps.players.models import Player
from apps.scoring.engine import MIN_SAMPLE, compute_rarity, recalc_submission_total, score_daily, unfilled_deduction
from apps.users.services import refresh_user_stats

from .models import MAX_ERRORS, STARTING_POINTS, Submission, SubmissionAnswer, SubmissionAttempt
from .services import is_practice_daily, validate_and_score_answer


def _ensure_playable(daily):
    if daily.status not in {'published', 'closed', 'scored'} or daily.date > timezone.localdate():
        raise serializers.ValidationError('Ta plansza nie jest dostępna')


def _unchanged_answer(answer, submission, guest_token):
    answer._unchanged = True
    answer._submission = submission
    answer._guest_token = guest_token
    count, total = answer.scoring_pick_count, answer.scoring_sample_size
    answer._rarity = {
        'pick_percent': answer.rarity_percent,
        'pick_count': count, 'sample_size': total,
        'provisional': answer.is_correct and (total == 0 or (
            not submission.is_scored and answer.daily_slot.daily.status != 'scored' and total < MIN_SAMPLE
        )),
    }
    return answer


def _finish_submission(submission):
    recalc_submission_total(submission)
    if submission.daily.date < timezone.localdate() and submission.is_over:
        submission.is_scored = True
        submission.save(update_fields=['is_scored'])
    if submission.is_over and submission.daily.date < timezone.localdate():
        score_daily(submission.daily_id, finalize=False)
        submission.refresh_from_db()
    if submission.user_id and submission.is_over:
        refresh_user_stats(submission.user_id)


# --------------------------------------------------------------------------- #
#  Wyjście
# --------------------------------------------------------------------------- #

class SubmissionAnswerOutputSerializer(serializers.ModelSerializer):
    player_nickname = serializers.CharField(source='player.nickname', read_only=True)
    player_slug = serializers.CharField(source='player.slug', read_only=True)
    slot_role = serializers.CharField(source='daily_slot.role', read_only=True)
    deduction = serializers.SerializerMethodField()

    def get_deduction(self, obj):
        return max(0.0, -obj.points_awarded) if obj.is_correct else 0.0

    class Meta:
        model = SubmissionAnswer
        fields = [
            'id', 'daily_slot', 'slot_role', 'player', 'player_nickname', 'player_slug',
            'is_correct', 'rarity_tier', 'rarity_percent', 'points_awarded', 'deduction', 'is_diamond_pick',
        ]


class SubmissionOutputSerializer(serializers.ModelSerializer):
    """
    Pełny stan gry dla danego Daily. Frontend nie liczy niczego sam –
    wszystkie liczniki (punkty, błędy, trafienia) pochodzą stąd.
    """
    answers = SubmissionAnswerOutputSerializer(many=True, read_only=True)
    errors_left = serializers.IntegerField(read_only=True)
    max_errors = serializers.SerializerMethodField()
    slots_total = serializers.SerializerMethodField()
    correct_count = serializers.SerializerMethodField()
    is_over = serializers.BooleanField(read_only=True)
    starting_points = serializers.SerializerMethodField()
    unfilled_deduction = serializers.SerializerMethodField()

    def get_starting_points(self, obj):
        return STARTING_POINTS

    def get_unfilled_deduction(self, obj):
        return unfilled_deduction(obj)

    class Meta:
        model = Submission
        fields = [
            'id', 'daily', 'submitted_at', 'total_points', 'is_scored', 'is_practice',
            'errors_used', 'errors_left', 'max_errors',
            'slots_total', 'correct_count', 'is_over', 'answers', 'starting_points', 'unfilled_deduction',
        ]

    def get_max_errors(self, obj):
        return MAX_ERRORS

    def get_slots_total(self, obj):
        return obj.daily.slots.count()

    def get_correct_count(self, obj):
        return obj.answers.filter(is_correct=True).count()


# --------------------------------------------------------------------------- #
#  Pojedyncza próba (tryb na żywo) – główna ścieżka rozgrywki
# --------------------------------------------------------------------------- #

class AnswerCreateSerializer(serializers.Serializer):
    """
    Jedna próba odgadnięcia zawodnika na jednym slocie.

    Reguły egzekwowane serwerowo:
      * slot z poprawną odpowiedzią jest zamknięty – nie da się go zmienić,
      * każda pomyłka zwiększa `errors_used`; po MAX_ERRORS gra jest zakończona,
      * ta sama nietrafiona odpowiedź powtórzona na tym samym slocie nie liczy się
        drugi raz jako błąd (ochrona przed podwójnym kliknięciem / retry sieciowym).
    """
    daily_id = serializers.IntegerField(min_value=1)
    slot_id = serializers.IntegerField(min_value=1)
    player_slug = serializers.SlugField(max_length=80)
    guest_token = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=64)

    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user if request and request.user.is_authenticated else None

        guest_token = '' if user else (validated_data.get('guest_token') or '')
        if not user and not guest_token.strip():
            guest_token = str(uuid.uuid4())

        try:
            slot = DailySlot.objects.select_related('daily').get(
                id=validated_data['slot_id'], daily_id=validated_data['daily_id']
            )
        except DailySlot.DoesNotExist:
            raise serializers.ValidationError('Nieprawidłowy slot dla tego Daily')
        _ensure_playable(slot.daily)

        try:
            player = Player.objects.get(slug=validated_data['player_slug'])
        except Player.DoesNotExist:
            raise serializers.ValidationError('Nie znaleziono zawodnika')

        with transaction.atomic():
            # Every gameplay/scoring path locks its board before its children.
            # This also matches generation and calendar preparation.
            slot.daily = Daily.objects.select_for_update().get(pk=slot.daily_id)
            _ensure_playable(slot.daily)
            # All writes lock every daily slot in the same order, including late
            # archive scoring, so different slots cannot deadlock each other.
            list(DailySlot.objects.select_for_update().filter(daily=slot.daily).order_by('pk'))
            submission, _ = Submission.objects.get_or_create(
                daily_id=validated_data['daily_id'],
                user=user if user else None,
                guest_token=None if user else guest_token,
                is_practice=is_practice_daily(slot.daily),
                defaults={'ip_hash': ''},
            )
            submission = Submission.objects.select_for_update().get(pk=submission.pk)
            if submission.is_seed:
                raise serializers.ValidationError('Ten identyfikator rozgrywki nie jest dostępny')

            existing = SubmissionAnswer.objects.filter(
                submission=submission, daily_slot=slot
            ).first()

            if existing and existing.is_correct:
                return _unchanged_answer(existing, submission, guest_token)

            # Powtórzenie tej samej błędnej odpowiedzi nie liczy się jako nowy błąd.
            duplicate_miss = SubmissionAttempt.objects.filter(
                submission=submission, daily_slot=slot, player=player, is_correct=False
            ).exists() or bool(existing and not existing.is_correct and existing.player_id == player.pk)
            if duplicate_miss and existing:
                return _unchanged_answer(existing, submission, guest_token)

            if submission.is_over:
                raise serializers.ValidationError({
                    'detail': 'Gra jest zakończona', 'code': 'game_over',
                })

            if submission.answers.filter(is_correct=True, player=player).exclude(daily_slot=slot).exists():
                raise serializers.ValidationError({
                    'detail': 'Ten zawodnik jest już poprawnie wybrany na innej pozycji',
                    'code': 'duplicate_player',
                })

            if existing:
                existing.player = player
                existing.is_correct = False
                existing.rarity_tier = None
                existing.rarity_percent = None
                existing.points_awarded = 0.0
                existing.save()
                answer_obj = existing
            else:
                answer_obj = SubmissionAnswer.objects.create(
                    submission=submission, daily_slot=slot, player=player
                )

            # Validate before recording the percentage deduction.
            validate_and_score_answer(answer_obj)

            SubmissionAttempt.objects.create(
                submission=submission,
                daily_slot=slot,
                player=player,
                is_correct=answer_obj.is_correct,
            )

            if not answer_obj.is_correct and not duplicate_miss:
                submission.errors_used = min(MAX_ERRORS, submission.errors_used + 1)
                submission.save(update_fields=['errors_used'])

            rarity = compute_rarity(answer_obj)
            _finish_submission(submission)
            answer_obj.refresh_from_db()
            if submission.is_over and submission.daily.date < timezone.localdate():
                rarity = {
                    'pick_percent': answer_obj.rarity_percent,
                    'pick_count': answer_obj.scoring_pick_count,
                    'sample_size': answer_obj.scoring_sample_size,
                    'provisional': answer_obj.is_correct and answer_obj.scoring_sample_size == 0,
                }

        submission.refresh_from_db()
        answer_obj._rarity = rarity
        answer_obj._guest_token = guest_token
        answer_obj._submission = submission
        return answer_obj

    def to_representation(self, instance):
        data = SubmissionAnswerOutputSerializer(instance, context=self.context).data
        rarity = getattr(instance, '_rarity', {}) or {}
        submission = getattr(instance, '_submission', None) or instance.submission

        data['pick_percent'] = rarity.get('pick_percent')
        data['pick_count'] = rarity.get('pick_count')
        data['sample_size'] = rarity.get('sample_size')
        data['is_provisional'] = rarity.get('provisional', False)
        data['unchanged'] = getattr(instance, '_unchanged', False)

        data['total_points'] = submission.total_points
        data['starting_points'] = STARTING_POINTS
        data['unfilled_deduction'] = unfilled_deduction(submission)
        data['errors_used'] = submission.errors_used
        data['errors_left'] = submission.errors_left
        data['max_errors'] = MAX_ERRORS
        data['slots_total'] = submission.daily.slots.count()
        data['correct_count'] = submission.answers.filter(is_correct=True).count()
        data['is_over'] = submission.is_over
        data['submission_id'] = submission.id
        data['is_scored'] = submission.is_scored
        data['is_practice'] = submission.is_practice
        data['answers'] = SubmissionAnswerOutputSerializer(
            submission.answers.select_related('player', 'daily_slot').order_by('daily_slot__position'),
            many=True, context=self.context,
        ).data

        guest_token = getattr(instance, '_guest_token', None)
        if guest_token:
            data['guest_token'] = guest_token
        return data


# --------------------------------------------------------------------------- #
#  Zbiorcze wysłanie składu – używane w archiwum
# --------------------------------------------------------------------------- #

class SubmissionAnswerInputSerializer(serializers.Serializer):
    slot_id = serializers.IntegerField(min_value=1)
    player_slug = serializers.SlugField(max_length=80)


class SubmissionCreateSerializer(serializers.Serializer):
    daily_id = serializers.IntegerField(min_value=1)
    guest_token = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=64)
    answers = SubmissionAnswerInputSerializer(many=True)

    def validate(self, attrs):
        if not attrs['answers']:
            raise serializers.ValidationError('Brak odpowiedzi')
        slot_ids = [a['slot_id'] for a in attrs['answers']]
        if len(slot_ids) != len(set(slot_ids)):
            raise serializers.ValidationError('Duplikaty slotów')
        player_slugs = [answer['player_slug'] for answer in attrs['answers']]
        if len(player_slugs) != len(set(player_slugs)):
            raise serializers.ValidationError('Każda pozycja wymaga innego zawodnika')
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user if request and request.user.is_authenticated else None
        daily_id = validated_data['daily_id']

        guest_token = '' if user else (validated_data.get('guest_token') or '')
        if not user and not guest_token.strip():
            guest_token = str(uuid.uuid4())

        daily = Daily.objects.filter(id=daily_id).first()
        if daily is None:
            raise serializers.ValidationError('Daily nie istnieje')
        _ensure_playable(daily)

        with transaction.atomic():
            daily = Daily.objects.select_for_update().get(pk=daily_id)
            _ensure_playable(daily)
            # Board, slots and submission are always locked in this order.
            list(DailySlot.objects.select_for_update().filter(daily=daily).order_by('pk'))
            submission, created = Submission.objects.get_or_create(
                daily_id=daily_id,
                user=user if user else None,
                guest_token=None if user else guest_token,
                is_practice=is_practice_daily(daily),
                defaults={'ip_hash': ''},
            )
            if not created or submission.is_seed:
                raise serializers.ValidationError('Już wysłałeś odpowiedź dla tego Daily')

            for ans in validated_data['answers']:
                try:
                    player = Player.objects.get(slug=ans['player_slug'])
                    slot = DailySlot.objects.get(id=ans['slot_id'], daily_id=daily_id)
                except (Player.DoesNotExist, DailySlot.DoesNotExist):
                    raise serializers.ValidationError(f'Nieprawidłowy slot lub zawodnik: {ans}')

                answer_obj = SubmissionAnswer.objects.create(
                    submission=submission, daily_slot=slot, player=player
                )
                validate_and_score_answer(answer_obj)
                SubmissionAttempt.objects.create(
                    submission=submission, daily_slot=slot, player=player,
                    is_correct=answer_obj.is_correct,
                )
                compute_rarity(answer_obj)

            submission.errors_used = min(
                MAX_ERRORS, submission.answers.filter(is_correct=False).count()
            )
            submission.save(update_fields=['errors_used'])
            _finish_submission(submission)

        submission._guest_token = guest_token
        return submission
