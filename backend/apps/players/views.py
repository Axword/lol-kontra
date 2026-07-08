from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Player
from .serializers import PlayerListSerializer, PlayerAutocompleteSerializer

class PlayerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Player.objects.all().order_by('nickname')
    serializer_class = PlayerListSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['primary_role', 'residency', 'country_code', 'is_active', 'continent']
    search_fields = ['nickname', 'real_name', 'slug']
    ordering_fields = ['nickname', 'worlds_count', 'worlds_titles_count']
    lookup_field = 'slug'

    @action(detail=False, methods=['get'], url_path='autocomplete')
    def autocomplete(self, request):
        q = request.query_params.get('q', '').strip()
        qs = self.get_queryset()
        if q:
            qs = qs.filter(nickname__icontains=q)[:20]
        else:
            qs = qs[:20]
        serializer = PlayerAutocompleteSerializer(qs, many=True)
        return Response({'results': serializer.data})
