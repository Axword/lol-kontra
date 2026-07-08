from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AdminDailyViewSet, AdminScoringViewSet

router = DefaultRouter()
router.register(r'dailies', AdminDailyViewSet, basename='admin-daily')
router.register(r'scoring-config', AdminScoringViewSet, basename='admin-scoring')

urlpatterns = [
    path('', include(router.urls)),
]
