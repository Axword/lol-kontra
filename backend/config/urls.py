from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from rest_framework import routers

urlpatterns = [
    path('admin/', admin.site.urls),
    # API v1
    path('api/v1/auth/', include('dj_rest_auth.urls')),
    path('api/v1/auth/registration/', include('dj_rest_auth.registration.urls')),
    path('api/v1/auth/social/', include('allauth.socialaccount.urls')),
    path('api/v1/', include('apps.players.urls')),
    path('api/v1/', include('apps.dailies.urls')),
    path('api/v1/', include('apps.submissions.urls')),
    path('api/v1/', include('apps.scoring.urls')),
    path('api/v1/', include('apps.users.urls')),
    path('api/v1/admin/', include('apps.admin_tools.urls')),
    # OpenAPI
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
