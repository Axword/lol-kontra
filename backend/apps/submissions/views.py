from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.dailies.models import Daily

from .models import MAX_ERRORS, STARTING_POINTS, Submission
from .services import is_practice_daily
from .serializers import (
    AnswerCreateSerializer,
    SubmissionCreateSerializer,
    SubmissionOutputSerializer,
)


def _empty_state(daily) -> dict:
    """
    Stan gry dla kogoś, kto jeszcze nie zaczął. Zwracamy go zamiast 404, żeby frontend
    miał komplet liczników (max_errors, liczba slotów) bez zgadywania i bez zaszytych
    wartości po swojej stronie.
    """
    return {
        'id': None,
        'daily': daily.id,
        'submitted_at': None,
        'total_points': float(STARTING_POINTS),
        'starting_points': STARTING_POINTS,
        'unfilled_deduction': 0.0,
        'is_scored': False,
        'is_practice': is_practice_daily(daily),
        'errors_used': 0,
        'errors_left': MAX_ERRORS,
        'max_errors': MAX_ERRORS,
        'slots_total': daily.slots.count(),
        'correct_count': 0,
        'is_over': False,
        'answers': [],
    }


class SubmissionViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Submission.objects.select_related('daily').prefetch_related(
        'answers__player', 'answers__daily_slot', 'daily__slots'
    )
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            daily__status__in=['published', 'closed', 'scored'], daily__date__lte=timezone.localdate()
        )
        if self.request.user.is_authenticated:
            return queryset.filter(user=self.request.user)
        token = self.request.query_params.get('guest_token')
        return queryset.filter(user__isnull=True, guest_token=token) if token else queryset.none()

    def get_serializer_class(self):
        if self.action == 'create':
            return SubmissionCreateSerializer
        if self.action == 'answer':
            return AnswerCreateSerializer
        return SubmissionOutputSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        submission = serializer.save()
        data = SubmissionOutputSerializer(submission).data
        if getattr(submission, '_guest_token', None):
            data['guest_token'] = submission._guest_token
        return Response(
            data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['get'], url_path='me')
    def me(self, request):
        """Aktualny stan gry gracza dla danego Daily."""
        daily_id = request.query_params.get('daily_id')
        if not daily_id:
            return Response({'detail': 'Wymagany parametr daily_id'}, status=400)

        try:
            daily_id = int(daily_id)
        except (TypeError, ValueError):
            return Response({'detail': 'daily_id musi być liczbą całkowitą'}, status=400)
        daily = get_object_or_404(
            Daily, id=daily_id, status__in=['published', 'closed', 'scored'], date__lte=timezone.localdate()
        )
        mode = request.query_params.get('mode')
        if mode not in {None, 'official'}:
            return Response({'detail': 'Dostępny tryb: official'}, status=400)
        practice = False

        if request.user.is_authenticated:
            obj = self.get_queryset().filter(
                daily_id=daily_id, user=request.user, is_practice=practice
            ).first()
        else:
            guest_token = request.query_params.get('guest_token')
            obj = (
                self.get_queryset().filter(
                    daily_id=daily_id, guest_token=guest_token, is_practice=practice
                ).first()
                if guest_token else None
            )

        if not obj:
            state = _empty_state(daily)
            state['is_practice'] = practice
            return Response(state)
        return Response(SubmissionOutputSerializer(obj).data)

    @action(detail=False, methods=['post'], url_path='answer', permission_classes=[AllowAny])
    def answer(self, request):
        """
        Weryfikacja pojedynczego wyboru (tryb na żywo).

        Body: {daily_id, slot_id, player_slug, guest_token?}
        Zwraca stan odpowiedzi (trafiona / nie, tier, procent wyborów) razem z pełnym
        stanem gry: punkty, zużyte błędy, liczba trafień, czy gra zakończona.
        """
        serializer = AnswerCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        answer = serializer.save()
        return Response(serializer.to_representation(answer), status=status.HTTP_200_OK)
