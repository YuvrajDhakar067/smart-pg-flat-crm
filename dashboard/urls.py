"""
Dashboard API URLs
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'dashboard'

# REST Framework router
router = DefaultRouter()
router.register(r'', views.DashboardViewSet, basename='dashboard')

urlpatterns = [
    # Simple endpoints
    path('metrics/', views.dashboard_metrics, name='metrics'),
    path('detailed/', views.dashboard_detailed_metrics, name='detailed'),
    
    # ViewSet endpoints (includes /summary/, /detailed/, /recent_activity/)
    path('api/', include(router.urls)),
]

