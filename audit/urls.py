"""
Audit Log URLs
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from audit import views

app_name = 'audit'

# REST Framework router
router = DefaultRouter()
router.register(r'logs', views.AuditLogViewSet, basename='auditlog')

urlpatterns = [
    # Simple endpoints
    path('summary/', views.audit_summary, name='summary'),
    
    # ViewSet endpoints
    path('', include(router.urls)),
]

