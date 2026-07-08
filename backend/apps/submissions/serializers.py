from rest_framework import serializers
from django.db import transaction
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
