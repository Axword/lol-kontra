from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DailyViewSet

router = DefaultRouter()
router.register(r'dailies', DailyViewSet, basename='daily')

urlpatterns = [
    path('', include(router.urls)),
]
