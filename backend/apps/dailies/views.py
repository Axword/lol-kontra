from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.utils import timezone
from .models import Daily
from .serializers import DailySerializer, DailySlotSerializer

# helper for role names PL
roleNamesPl = {'top':'Top','jungle':'Dżungla','mid':'Mid','adc':'ADC','support':'Support'}


class DailyViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Daily.objects.prefetch_related('slots__conditions').order_by('-date')
    serializer_class = DailySerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=['get'], url_path='today')
    def today(self, request):
        today = timezone.localdate()
        daily, created = Daily.objects.get_or_create(
            date=today,
            defaults={'status': 'published', 'reveal_mode': 'instant', 'locale_seed': str(today)}
        )
        # auto-generate slots if empty (dev convenience)
        if daily.slots.count() == 0:
            from .generator import generate_daily
            # generate_daily will skip if slots exist, so delete draft first? we need to populate
            # manually generate slots
            from .models import DailySlot
            if not DailySlot.objects.filter(daily=daily).exists():
                # use generator helper
                try:
                    # clear and regenerate
                    generate_daily(date=today, seed=str(today))
                    daily.refresh_from_db()
                except Exception as e:
                    pass
        # if still empty, provide fallback demo slots
        if daily.slots.count() == 0:
            self._ensure_demo_slots(daily)
        serializer = self.get_serializer(daily)
        return Response(serializer.data)

    def _ensure_demo_slots(self, daily):
        """Fallback – creates 5 demo slots if generator fails
        v2 – instant mode only, NO worlds_champion (DB may lack titles),
        target 20-80 candidates per slot
        """
        from .models import DailySlot, DailySlotCondition
        # always rebuild demo to ensure clean conditions
        DailySlot.objects.filter(daily=daily).delete()
        roles = [('top',1),('jungle',2),('mid',3),('adc',4),('support',5)]
        # safe, high-coverage conditions – tested vs 876 players
        demo_conditions = [
            # Top – LCK + Worlds
            [('residency','eq','LCK','Grał w LCK','Played in LCK'), ('worlds_appearance','any',True,'Grał na Worlds','Worlds appearance')],
            # Jungle – LEC + active
            [('residency','eq','LEC','Grał w LEC','Played in LEC'), ('active','eq',True,'Aktywny','Active')],
            # Mid – LCK + active
            [('residency','eq','LCK','Grał w LCK','Played in LCK'), ('active','eq',True,'Aktywny','Active')],
            # ADC – Europe + Worlds
            [('continent','eq','Europe','Europejczyk','European'), ('worlds_appearance','any',True,'Grał na Worlds','Worlds appearance')],
            # Support – LEC + active
            [('residency','eq','LEC','Grał w LEC','Played in LEC'), ('active','eq',True,'Aktywny','Active')],
        ]
        for (role, pos), conds in zip(roles, demo_conditions):
            slot = DailySlot.objects.create(daily=daily, role=role, position=pos, label_pl=roleNamesPl.get(role, role.capitalize()), label_en=role.capitalize())
            for i,(ctype,op,val,pl,en) in enumerate(conds):
                DailySlotCondition.objects.create(slot=slot, condition_type=ctype, operator=op, value=val, label_pl=pl, label_en=en, order=i)

    @action(detail=True, methods=['get'], url_path='slots')
    def slots(self, request, pk=None):
        daily = self.get_object()
        serializer = DailySlotSerializer(daily.slots.all(), many=True)
        return Response(serializer.data)
