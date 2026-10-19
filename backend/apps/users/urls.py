from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GuestProfileView, GuestTeamsView, UserViewSet, LeaderboardView

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')

urlpatterns = [
    path('', include(router.urls)),
    path('leaderboard/', LeaderboardView.as_view(), name='leaderboard'),
    path('guest/profile/', GuestProfileView.as_view(), name='guest-profile'),
    path('guest/teams/', GuestTeamsView.as_view(), name='guest-teams'),
    path('users/me/', UserViewSet.as_view({'get': 'me'})),
    path('users/me/stats/', UserViewSet.as_view({'get': 'my_stats'})),
]
