from django.db.models import Q
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

    def get_queryset(self):
        qs = super().get_queryset()
        # Prefetch related data for detail views
        if self.action == 'retrieve':
            qs = qs.prefetch_related('team_history__team', 'champion_stats')
        return qs

    @action(detail=False, methods=['get'], url_path='autocomplete')
    def autocomplete(self, request):
        """
        Autocomplete graczy – wymaga min. 2 znaków.
        Zwraca wyniki posortowane: exact > starts_with > contains.
        """
        q = request.query_params.get('q', '').strip()
        limit = min(int(request.query_params.get('limit', 20)), 50)

        if len(q) < 2:
            return Response({'results': [], 'count': 0})

        # Szukanie po contiguous substring
        exact = Player.objects.filter(
            Q(nickname__iexact=q) | Q(slug__iexact=q)
        )
        starts_with = Player.objects.filter(
            Q(nickname__istartswith=q) | Q(slug__istartswith=q)
        ).exclude(
            Q(nickname__iexact=q) | Q(slug__iexact=q)
        )
        contains = Player.objects.filter(
            Q(nickname__icontains=q) | Q(real_name__icontains=q)
        ).exclude(
            Q(nickname__istartswith=q) | Q(slug__istartswith=q) | Q(nickname__iexact=q)
        )

        results = list(exact[:5]) + list(starts_with[:15]) + list(contains[:limit])
        # deduplicate by slug
        seen = set()
        unique = []
        for p in results:
            if p.slug not in seen:
                seen.add(p.slug)
                unique.append(p)

        serializer = PlayerAutocompleteSerializer(unique[:limit], many=True)
        return Response({'results': serializer.data, 'count': len(unique)})
