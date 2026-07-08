from rest_framework import viewsets, mixins, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from django.db import transaction, IntegrityError
from .models import Submission, SubmissionAnswer
from .serializers import SubmissionCreateSerializer, SubmissionOutputSerializer, SubmissionAnswerOutputSerializer, AnswerCreateSerializer

class SubmissionViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Submission.objects.prefetch_related('answers__player', 'answers__daily_slot').all()
    permission_classes = [AllowAny]

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
        output = SubmissionOutputSerializer(submission)
        headers = {}
        return Response(output.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=False, methods=['get'], url_path='me')
    def me(self, request):
        daily_id = request.query_params.get('daily_id')
        if not daily_id:
            return Response({'detail': 'daily_id required'}, status=400)
        qs = self.get_queryset()
        if request.user.is_authenticated:
            obj = qs.filter(daily_id=daily_id, user=request.user).first()
        else:
            guest_token = request.query_params.get('guest_token')
            obj = qs.filter(daily_id=daily_id, guest_token=guest_token).first() if guest_token else None
        if not obj:
            return Response({'detail': 'not found'}, status=404)
        serializer = SubmissionOutputSerializer(obj)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='answer', permission_classes=[AllowAny])
    def answer(self, request):
        """
        PER-SLOT INSTANT verification.
        Body: {daily_id, slot_id, player_slug, guest_token?}
        Returns immediately: is_correct, rarity_tier, points_awarded, is_diamond_pick
        Slot becomes locked after first answer – cannot change.
        """
        serializer = AnswerCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        answer = serializer.save()
        # serializer.to_representation already called? No, we need output
        output_data = serializer.to_representation(answer)
        # status 201 if newly created, 200 if locked existing – simplify 200
        return Response(output_data, status=status.HTTP_200_OK)
