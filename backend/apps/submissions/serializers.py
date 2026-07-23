from rest_framework import serializers
from django.db import transaction, IntegrityError
from django.db.models import Sum
from .models import Submission, SubmissionAnswer
from apps.players.models import Player
from apps.dailies.models import DailySlot
from .services import validate_and_score_answer

class SubmissionAnswerInputSerializer(serializers.Serializer):
    slot_id = serializers.IntegerField()
    player_slug = serializers.SlugField()

class SubmissionCreateSerializer(serializers.Serializer):
    daily_id = serializers.IntegerField()
    guest_token = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    answers = SubmissionAnswerInputSerializer(many=True)

    def validate(self, attrs):
        if len(attrs['answers']) == 0:
            raise serializers.ValidationError("Brak odpowiedzi")
        # sprawdź unikalne sloty
        slot_ids = [a['slot_id'] for a in attrs['answers']]
        if len(slot_ids) != len(set(slot_ids)):
            raise serializers.ValidationError("Duplikaty slotów")
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user if request and request.user.is_authenticated else None
        daily_id = validated_data['daily_id']
        guest_token = validated_data.get('guest_token')

        if not user and not guest_token:
            raise serializers.ValidationError("Wymagany user lub guest_token")

        # normalize guest_token – empty string not allowed
        if guest_token == '':
            import uuid
            guest_token = str(uuid.uuid4())

        from apps.dailies.models import Daily
        try:
            daily = Daily.objects.get(id=daily_id)
        except Daily.DoesNotExist:
            raise serializers.ValidationError("Daily nie istnieje")

        with transaction.atomic():
            submission, created = Submission.objects.get_or_create(
                daily_id=daily_id,
                user=user if user else None,
                guest_token=None if user else guest_token,
                defaults={'ip_hash': ''}
            )
            if not created:
                raise serializers.ValidationError("Już wysłałeś odpowiedź dla tego Daily")

            # create answers
            for ans in validated_data['answers']:
                try:
                    player = Player.objects.get(slug=ans['player_slug'])
                    slot = DailySlot.objects.get(id=ans['slot_id'], daily_id=daily_id)
                except (Player.DoesNotExist, DailySlot.DoesNotExist):
                    raise serializers.ValidationError(f"Nieprawidłowy slot/player: {ans}")
                answer_obj = SubmissionAnswer.objects.create(
                    submission=submission,
                    daily_slot=slot,
                    player=player,
                )
                # walidacja + diamond
                validate_and_score_answer(answer_obj)

        # --- instant scoring ---
        # jeśli reveal_mode == instant, od razu przelicz rarity dla tego Daily
        if daily.reveal_mode == 'instant':
            try:
                from apps.scoring.engine import score_daily
                # szybkie przeliczenie – może być kosztowne przy dużej liczbie submissions,
                # ale dla MVP OK (<1s dla <10k)
                score_daily(daily_id)
                submission.refresh_from_db()
            except Exception:
                pass  # fail silently, nightly job naprawi

        return submission

class SubmissionAnswerOutputSerializer(serializers.ModelSerializer):
    player_nickname = serializers.CharField(source='player.nickname', read_only=True)
    player_slug = serializers.CharField(source='player.slug', read_only=True)
    slot_role = serializers.CharField(source='daily_slot.role', read_only=True)

    class Meta:
        model = SubmissionAnswer
        fields = ['id', 'daily_slot', 'slot_role', 'player', 'player_nickname', 'player_slug',
                  'is_correct', 'rarity_tier', 'rarity_percent', 'points_awarded', 'is_diamond_pick']

class SubmissionOutputSerializer(serializers.ModelSerializer):
    answers = SubmissionAnswerOutputSerializer(many=True, read_only=True)
    class Meta:
        model = Submission
        fields = ['id', 'daily', 'submitted_at', 'total_points', 'is_scored', 'answers']


# --- PER-SLOT INSTANT ANSWER ---
class AnswerCreateSerializer(serializers.Serializer):
    daily_id = serializers.IntegerField()
    slot_id = serializers.IntegerField()
    player_slug = serializers.SlugField()
    guest_token = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user if request and request.user.is_authenticated else None
        daily_id = validated_data['daily_id']
        slot_id = validated_data['slot_id']
        player_slug = validated_data['player_slug']
        guest_token = validated_data.get('guest_token')

        if not user and not guest_token:
            # auto generate
            import uuid
            guest_token = str(uuid.uuid4())

        if guest_token == '':
            import uuid
            guest_token = str(uuid.uuid4())

        from apps.dailies.models import Daily, DailySlot
        try:
            daily = Daily.objects.get(id=daily_id)
            slot = DailySlot.objects.get(id=slot_id, daily_id=daily_id)
            player = Player.objects.get(slug=player_slug)
        except (Daily.DoesNotExist, DailySlot.DoesNotExist):
            raise serializers.ValidationError("Nieprawidłowy daily/slot")
        except Player.DoesNotExist:
            raise serializers.ValidationError("Nieprawidłowy gracz")

        with transaction.atomic():
            submission, _ = Submission.objects.get_or_create(
                daily_id=daily_id,
                user=user if user else None,
                guest_token=None if user else guest_token,
                defaults={'ip_hash': ''}
            )

            existing = SubmissionAnswer.objects.filter(submission=submission, daily_slot=slot).first()
            if existing:
                if existing.is_correct:
                    # locked – cannot change correct answer
                    return existing
                # retry allowed: overwrite the wrong answer
                existing.player = player
                existing.is_correct = False
                existing.rarity_tier = None
                existing.rarity_percent = None
                existing.points_awarded = 0
                existing.is_diamond_pick = False
                existing.save()
                answer_obj = existing
            else:
                try:
                    answer_obj = SubmissionAnswer.objects.create(
                        submission=submission,
                        daily_slot=slot,
                        player=player,
                    )
                except IntegrityError:
                    answer_obj = SubmissionAnswer.objects.get(submission=submission, daily_slot=slot)
                    if answer_obj.is_correct:
                        return answer_obj

            # validate instantly (is_correct + diamond)
            validate_and_score_answer(answer_obj)

        # FAST kontra scoring – instant, no full score_daily
        # deduction = 100 - pick_percent (or 100 for diamond)
        # remaining = 500 - sum deductions
        try:
            pick_percent = getattr(answer_obj, 'rarity_percent', None) or 0.0
            is_dia = answer_obj.is_diamond_pick
            deduction = 100.0 if is_dia else round(100.0 - pick_percent, 1)
            answer_obj.points_awarded = deduction
            answer_obj.save(update_fields=['points_awarded'])

            # compute running total from existing answers
            # FIX: total_points is now FloatField — store actual score directly
            existing_ded = submission.answers.aggregate(s=Sum('points_awarded'))['s'] or 0
            remaining = round(500.0 - float(existing_ded), 1)
            submission.total_points = remaining
            submission.save(update_fields=['total_points'])
        except Exception:
            pass

        answer_obj._guest_token = guest_token
        answer_obj._submission_total = submission.total_points
        answer_obj._pick_percent = getattr(answer_obj, 'rarity_percent', None) or 0.0
        answer_obj._deduction = answer_obj.points_awarded
        return answer_obj

    def to_representation(self, instance):
        data = SubmissionAnswerOutputSerializer(instance, context=self.context).data
        # kontra fields
        data['pick_percent'] = round(getattr(instance, '_pick_percent', 0.0) or getattr(instance, 'rarity_percent', 0.0) or 0.0, 1)
        data['deduction'] = getattr(instance, '_deduction', instance.points_awarded or 0)
        # FIX: total_points is now FloatField — no more /10 decoding
        total = getattr(instance, '_submission_total', None)
        if total is not None:
            data['total_points'] = round(float(total), 1)
            data['remaining_score'] = data['total_points']
            data['start_score'] = 500
        else:
            data['total_points'] = 500
            data['remaining_score'] = 500
            data['start_score'] = 500

        gt = getattr(instance, '_guest_token', None)
        if gt:
            data['guest_token'] = gt
        try:
            sub = instance.submission
            answered = sub.answers.count()
            data['answered_count'] = answered
            data['submission_id'] = sub.id
        except Exception:
            pass
        return data
