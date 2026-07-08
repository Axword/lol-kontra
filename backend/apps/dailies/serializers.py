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
