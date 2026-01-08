"""
API URLs for PropEase
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts.views import AccountViewSet
from buildings.views import BuildingViewSet
from units.views import UnitViewSet, PGRoomViewSet, BedViewSet
from tenants.views import TenantViewSet
from occupancy.views import OccupancyViewSet
from rent.views import RentViewSet
from issues.views import IssueViewSet
from dashboard.views import DashboardViewSet

# Create router
router = DefaultRouter()
router.register(r'accounts', AccountViewSet, basename='account')
router.register(r'buildings', BuildingViewSet, basename='building')
router.register(r'units', UnitViewSet, basename='unit')
router.register(r'pg-rooms', PGRoomViewSet, basename='pgroom')
router.register(r'beds', BedViewSet, basename='bed')
router.register(r'tenants', TenantViewSet, basename='tenant')
router.register(r'occupancies', OccupancyViewSet, basename='occupancy')
router.register(r'rents', RentViewSet, basename='rent')
router.register(r'issues', IssueViewSet, basename='issue')
router.register(r'dashboard', DashboardViewSet, basename='dashboard')

urlpatterns = [
    # JWT Authentication
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Audit logs
    path('audit/', include('audit.urls')),
    
    # API routes
    path('', include(router.urls)),
]

