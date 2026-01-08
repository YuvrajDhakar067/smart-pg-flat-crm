"""
Health Check Endpoints for Smart PG & Flat Management CRM

Provides endpoints for:
- Liveness checks (is the app running?)
- Readiness checks (can the app serve requests?)
- Deep health checks (database, cache, etc.)
"""

import time
import logging
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


@csrf_exempt
@require_GET
def health_check(request):
    """
    Basic health check - returns 200 if app is running.
    Used by load balancers and container orchestration.
    """
    return JsonResponse({
        'status': 'healthy',
        'timestamp': time.time(),
    })


@csrf_exempt
@require_GET
def readiness_check(request):
    """
    Readiness check - verifies app can serve requests.
    Checks database and cache connectivity.
    """
    checks = {
        'database': False,
        'cache': False,
    }
    errors = []
    
    # Check database connection
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        checks['database'] = True
    except Exception as e:
        errors.append(f'Database: {str(e)}')
        logger.error(f'Health check - Database error: {e}')
    
    # Check cache connection
    try:
        cache_key = 'health_check_test'
        cache.set(cache_key, 'ok', 10)
        if cache.get(cache_key) == 'ok':
            checks['cache'] = True
            cache.delete(cache_key)
        else:
            errors.append('Cache: Failed to read/write')
    except Exception as e:
        errors.append(f'Cache: {str(e)}')
        logger.error(f'Health check - Cache error: {e}')
    
    # Determine overall status
    all_healthy = all(checks.values())
    status_code = 200 if all_healthy else 503
    
    return JsonResponse({
        'status': 'ready' if all_healthy else 'not_ready',
        'timestamp': time.time(),
        'checks': checks,
        'errors': errors if errors else None,
    }, status=status_code)


@csrf_exempt
@require_GET
def deep_health_check(request):
    """
    Deep health check - comprehensive system status.
    Use sparingly as it may be resource intensive.
    """
    from django.contrib.auth import get_user_model
    from buildings.models import Building
    from tenants.models import Tenant
    
    checks = {
        'database': {'status': False, 'latency_ms': None},
        'cache': {'status': False, 'latency_ms': None},
        'models': {'status': False, 'details': {}},
    }
    errors = []
    
    # Database check with latency
    try:
        start = time.time()
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        latency = (time.time() - start) * 1000
        checks['database'] = {'status': True, 'latency_ms': round(latency, 2)}
    except Exception as e:
        errors.append(f'Database: {str(e)}')
        logger.error(f'Deep health check - Database error: {e}')
    
    # Cache check with latency
    try:
        start = time.time()
        cache_key = 'deep_health_check_test'
        cache.set(cache_key, 'ok', 10)
        result = cache.get(cache_key)
        latency = (time.time() - start) * 1000
        
        if result == 'ok':
            checks['cache'] = {'status': True, 'latency_ms': round(latency, 2)}
            cache.delete(cache_key)
        else:
            errors.append('Cache: Read/write failed')
    except Exception as e:
        errors.append(f'Cache: {str(e)}')
        logger.error(f'Deep health check - Cache error: {e}')
    
    # Model checks (verify DB schema)
    try:
        User = get_user_model()
        model_checks = {
            'users': User.objects.count(),
            'buildings': Building.objects.count(),
            'tenants': Tenant.objects.count(),
        }
        checks['models'] = {'status': True, 'details': model_checks}
    except Exception as e:
        errors.append(f'Models: {str(e)}')
        logger.error(f'Deep health check - Model error: {e}')
    
    # Calculate overall status
    critical_checks = [checks['database']['status'], checks['cache']['status']]
    all_healthy = all(critical_checks)
    status_code = 200 if all_healthy else 503
    
    return JsonResponse({
        'status': 'healthy' if all_healthy else 'unhealthy',
        'timestamp': time.time(),
        'checks': checks,
        'errors': errors if errors else None,
        'version': '1.0.0',
    }, status=status_code)


def get_health_urls():
    """
    Returns URL patterns for health endpoints.
    Add to your urls.py:
        from common.health import get_health_urls
        urlpatterns += get_health_urls()
    """
    from django.urls import path
    
    return [
        path('health/', health_check, name='health_check'),
        path('health/ready/', readiness_check, name='readiness_check'),
        path('health/deep/', deep_health_check, name='deep_health_check'),
    ]

