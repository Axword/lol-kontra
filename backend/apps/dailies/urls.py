from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DailyViewSet
from .community import roster_share

router = DefaultRouter()
router.register(r'dailies', DailyViewSet, basename='daily')

urlpatterns = [
    path('roster-shares/<uuid:share_key>.png', roster_share, name='roster-share'),
    path('', include(router.urls)),
]
