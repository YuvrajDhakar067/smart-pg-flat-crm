"""
URL configuration for smart_pg project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

# Import admin customization (just to apply it, not to use)
from smart_pg import admin as admin_customization  # noqa: F401

# Import health check URLs
from common.health import get_health_urls

def root_redirect(request):
    """Redirect root to dashboard or login"""
    if request.user.is_authenticated:
        return redirect('properties:dashboard')
    return redirect('accounts:login')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),  # API routes
    path('dashboard/', include('dashboard.urls')),  # Dashboard API routes
    path('accounts/', include('accounts.urls')),
    path('', include('properties.urls')),  # Properties routes (includes dashboard at root)
]

# Add health check endpoints (for load balancers, monitoring)
urlpatterns += get_health_urls()

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
