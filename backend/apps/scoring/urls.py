from django.urls import path
from .views import ScoringViewSet

answer_stats_view = ScoringViewSet.as_view({'get': 'answer_stats'})
score_dist_view = ScoringViewSet.as_view({'get': 'score_distribution'})

urlpatterns = [
    path('dailies/<int:daily_id>/answer-stats/', answer_stats_view, name='answer-stats'),
    path('dailies/<int:daily_id>/score-distribution/', score_dist_view, name='score-distribution'),
]
