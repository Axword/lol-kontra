from django.db.models import Case, IntegerField, Q, When
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Player
from .serializers import PlayerAutocompleteSerializer, PlayerListSerializer


class PlayerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Player.objects.all().order_by('nickname')
    serializer_class = PlayerListSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['primary_role', 'residency', 'country_code', 'is_active', 'continent']
    search_fields = ['nickname', 'real_name', 'slug']
    ordering_fields = ['nickname', 'worlds_count', 'worlds_titles_count']
    lookup_field = 'slug'

    def get_queryset(self):
        excluded = Player.objects.filter(attributes__worlds_verified=False).values('pk')
        return super().get_queryset().exclude(pk__in=excluded)

    @action(detail=False, methods=['get'], url_path='autocomplete')
    def autocomplete(self, request):
        """
        Podpowiedzi do wyszukiwarki zawodników.

        `role` zawęża listę do graczy występujących na danej pozycji (podstawowej lub
        dodatkowej) – panel wyboru dotyczy konkretnego slotu, więc nie ma sensu
        pokazywać w nim supportów, gdy gracz uzupełnia top.

        Odpowiedź celowo nie zawiera `attributes` ani `career_stats`: to są dane,
        na podstawie których weryfikujemy warunki, i podpowiadałyby rozwiązanie.
        """
        query = request.query_params.get('q', '').strip()
        role = request.query_params.get('role', '').strip().lower()

        qs = self.get_queryset()
        if role:
            qs = qs.filter(Q(primary_role=role) | Q(secondary_roles__contains=[role]))

        if query:
            qs = qs.filter(
                Q(nickname__icontains=query)
                | Q(real_name__icontains=query)
                | Q(slug__icontains=query)
            ).annotate(
                # Dokładne trafienie, potem początek nicku, potem reszta.
                match_rank=Case(
                    When(nickname__iexact=query, then=0),
                    When(nickname__istartswith=query, then=1),
                    When(nickname__icontains=query, then=2),
                    default=3,
                    output_field=IntegerField(),
                )
            ).order_by('match_rank', '-worlds_count', 'nickname')[:25]
        else:
            qs = qs.order_by('-worlds_count', 'nickname')[:25]

        return Response({'results': PlayerAutocompleteSerializer(qs, many=True).data})
