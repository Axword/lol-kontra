from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SubmissionViewSet
from . import infinity

router = DefaultRouter()
router.register(r'submissions', SubmissionViewSet, basename='submission')

urlpatterns = [
    path('infinity/state/', infinity.state),
    path('infinity/start/', infinity.start),
    path('infinity/answer/', infinity.answer),
    path('infinity/leaderboard/', infinity.leaderboard),
    path('', include(router.urls)),
]
