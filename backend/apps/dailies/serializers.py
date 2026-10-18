from rest_framework import serializers
from .models import Daily, DailySlot, DailySlotCondition

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
            slots = list(self.instance.slots.prefetch_related('conditions')) if self.instance else []
            if (len(slots) != 5 or {slot.role for slot in slots} != {'top', 'jungle', 'mid', 'adc', 'support'}
                    or any(len(slot.conditions.all()) != 2 for slot in slots)):
                raise serializers.ValidationError({'status': 'Każda z pięciu pozycji musi mieć dokładnie dwa warunki.'})
        return attrs
