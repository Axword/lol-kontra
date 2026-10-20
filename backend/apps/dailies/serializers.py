from rest_framework import serializers
from .models import Daily, DailySlot, DailySlotCondition
from .generator import validate_daily

class DailySlotConditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailySlotCondition
        fields = ['id', 'condition_type', 'operator', 'value', 'label_pl', 'label_en', 'order']

class DailySlotSerializer(serializers.ModelSerializer):
    conditions = DailySlotConditionSerializer(many=True, read_only=True)
    class Meta:
        model = DailySlot
        fields = ['id', 'position', 'role', 'label_pl', 'label_en', 'conditions']

class DailySerializer(serializers.ModelSerializer):
    slots = DailySlotSerializer(many=True, read_only=True)
    class Meta:
        model = Daily
        fields = ['id', 'date', 'status', 'reveal_mode', 'slots']

    def validate(self, attrs):
        if attrs.get('status') == 'published':
            if not self.instance:
                raise serializers.ValidationError({'status': 'Najpierw przygotuj pięć pozycji w edytorze reguł.'})
            try:
                validate_daily(self.instance)
            except ValueError as exc:
                raise serializers.ValidationError({'status': str(exc)}) from exc
        return attrs
