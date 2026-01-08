"""
Global Permissions Middleware for Multi-Tenant SaaS

This middleware enforces:
1. Account-level isolation (no cross-account access)
2. Building-level permissions (OWNER vs MANAGER)
3. Role-based access control

CRITICAL: This middleware runs BEFORE all API views to provide
a security layer that prevents unauthorized access at the request level.
"""

import logging
import re
from django.http import JsonResponse
from django.urls import resolve
from django.db.models import Q

logger = logging.getLogger(__name__)


class AccountPermissionMiddleware:
    """
    Global middleware to enforce multi-tenant access control.
    
    Security Rules:
    1. Account Isolation: Users can ONLY access data in their account
    2. Building-Level: Managers can ONLY access assigned buildings
    3. Fail Closed: Deny access if we can't confidently determine permissions
    """
    
    # Paths that don't require permission checks
    EXEMPT_PATHS = [
        r'^/admin/',           # Django admin
        r'^/api/auth/',        # Authentication endpoints
        r'^/api/token/',       # JWT token endpoints
        r'^/accounts/login',   # Login page
        r'^/accounts/logout',  # Logout page
        r'^/accounts/register', # Registration
        r'^/health/',          # Health check
        r'^/static/',          # Static files
        r'^/media/',           # Media files
        r'^/__debug__/',       # Django Debug Toolbar
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        """Process the request through middleware"""
        
        # Check if path is exempt
        if self._is_exempt_path(request.path):
            return self.get_response(request)
        
        # Skip unauthenticated requests (handled by DRF permissions)
        if not request.user or not request.user.is_authenticated:
            return self.get_response(request)
        
        # Skip if user has no account
        if not hasattr(request.user, 'account') or not request.user.account:
            logger.warning(f"User {request.user.username} has no account")
            return self.get_response(request)
        
        # Extract resource IDs from request
        resource_ids = self._extract_resource_ids(request)
        
        # Validate account isolation
        account_violation = self._check_account_isolation(request.user, resource_ids)
        if account_violation:
            logger.warning(
                f"Account isolation violation: {request.user.username} "
                f"attempted to access {account_violation}"
            )
            return JsonResponse(
                {
                    'detail': 'Access denied: You do not have permission to access this resource.',
                    'error_code': 'ACCOUNT_ISOLATION_VIOLATION'
                },
                status=403
            )
        
        # Validate building-level access (for managers)
        building_violation = self._check_building_access(request.user, resource_ids)
        if building_violation:
            logger.warning(
                f"Building access violation: {request.user.username} "
                f"attempted to access {building_violation}"
            )
            return JsonResponse(
                {
                    'detail': 'Access denied: You do not have permission to access this building.',
                    'error_code': 'BUILDING_ACCESS_VIOLATION'
                },
                status=403
            )
        
        # All checks passed, continue to view
        response = self.get_response(request)
        return response
    
    def _is_exempt_path(self, path):
        """Check if path is exempt from permission checks"""
        for pattern in self.EXEMPT_PATHS:
            if re.match(pattern, path):
                return True
        return False
    
    def _extract_resource_ids(self, request):
        """
        Extract resource IDs from URL path and query parameters.
        
        Returns dict with resource IDs found in request:
        {
            'building_id': int,
            'unit_id': int,
            'tenant_id': int,
            'occupancy_id': int,
            'rent_id': int,
            'issue_id': int,
            'bed_id': int,
            'room_id': int
        }
        """
        resource_ids = {}
        
        # Extract from URL path parameters
        try:
            url_kwargs = resolve(request.path).kwargs
            
            # Map URL parameter names to resource types
            id_mappings = {
                'building_id': 'building_id',
                'unit_id': 'unit_id',
                'tenant_id': 'tenant_id',
                'occupancy_id': 'occupancy_id',
                'rent_id': 'rent_id',
                'issue_id': 'issue_id',
                'bed_id': 'bed_id',
                'room_id': 'room_id',
                'pk': 'pk',  # DRF generic primary key
            }
            
            for param_name, resource_type in id_mappings.items():
                if param_name in url_kwargs:
                    try:
                        resource_ids[resource_type] = int(url_kwargs[param_name])
                    except (ValueError, TypeError):
                        pass
            
            # Try to infer resource type from URL path
            if 'pk' in resource_ids:
                pk_value = resource_ids['pk']
                path = request.path
                
                if '/buildings/' in path:
                    resource_ids['building_id'] = pk_value
                elif '/units/' in path:
                    resource_ids['unit_id'] = pk_value
                elif '/tenants/' in path:
                    resource_ids['tenant_id'] = pk_value
                elif '/occupancies/' in path or '/occupancy/' in path:
                    resource_ids['occupancy_id'] = pk_value
                elif '/rents/' in path:
                    resource_ids['rent_id'] = pk_value
                elif '/issues/' in path:
                    resource_ids['issue_id'] = pk_value
                elif '/beds/' in path:
                    resource_ids['bed_id'] = pk_value
                elif '/rooms/' in path or '/pgrooms/' in path:
                    resource_ids['room_id'] = pk_value
        except:
            pass
        
        # Extract from query parameters
        query_params = request.GET
        for param in ['building', 'building_id', 'unit', 'unit_id', 'tenant', 'tenant_id']:
            if param in query_params:
                try:
                    value = int(query_params[param])
                    if 'building' in param:
                        resource_ids['building_id'] = value
                    elif 'unit' in param:
                        resource_ids['unit_id'] = value
                    elif 'tenant' in param:
                        resource_ids['tenant_id'] = value
                except (ValueError, TypeError):
                    pass
        
        # Extract from POST/PUT/PATCH data
        if request.method in ['POST', 'PUT', 'PATCH']:
            try:
                if hasattr(request, 'data'):
                    data = request.data
                    for key in ['building', 'building_id', 'unit', 'unit_id']:
                        if key in data:
                            try:
                                value = int(data[key])
                                if 'building' in key:
                                    resource_ids['building_id'] = value
                                elif 'unit' in key:
                                    resource_ids['unit_id'] = value
                            except (ValueError, TypeError):
                                pass
            except:
                pass
        
        return resource_ids
    
    def _check_account_isolation(self, user, resource_ids):
        """
        Verify that all resources belong to user's account.
        
        Returns:
            str: Description of violation if found, None if all checks pass
        """
        from buildings.models import Building
        from units.models import Unit, PGRoom, Bed
        from tenants.models import Tenant
        from occupancy.models import Occupancy
        from rent.models import Rent
        from issues.models import Issue
        
        user_account = user.account
        
        # Check Building
        if 'building_id' in resource_ids:
            try:
                building = Building.objects.get(id=resource_ids['building_id'])
                if building.account != user_account:
                    return f"Building {building.id} (belongs to account {building.account.name})"
            except Building.DoesNotExist:
                # Will be handled by view (404)
                pass
        
        # Check Unit
        if 'unit_id' in resource_ids:
            try:
                unit = Unit.objects.get(id=resource_ids['unit_id'])
                if unit.account != user_account:
                    return f"Unit {unit.id} (belongs to account {unit.account.name})"
            except Unit.DoesNotExist:
                pass
        
        # Check Tenant
        if 'tenant_id' in resource_ids:
            try:
                tenant = Tenant.objects.get(id=resource_ids['tenant_id'])
                if tenant.account != user_account:
                    return f"Tenant {tenant.id} (belongs to account {tenant.account.name})"
            except Tenant.DoesNotExist:
                pass
        
        # Check Occupancy
        if 'occupancy_id' in resource_ids:
            try:
                occupancy = Occupancy.objects.get(id=resource_ids['occupancy_id'])
                if occupancy.tenant.account != user_account:
                    return f"Occupancy {occupancy.id} (belongs to different account)"
            except Occupancy.DoesNotExist:
                pass
        
        # Check Rent
        if 'rent_id' in resource_ids:
            try:
                rent = Rent.objects.get(id=resource_ids['rent_id'])
                if rent.occupancy.tenant.account != user_account:
                    return f"Rent {rent.id} (belongs to different account)"
            except Rent.DoesNotExist:
                pass
        
        # Check Issue
        if 'issue_id' in resource_ids:
            try:
                issue = Issue.objects.get(id=resource_ids['issue_id'])
                if issue.unit.account != user_account:
                    return f"Issue {issue.id} (belongs to different account)"
            except Issue.DoesNotExist:
                pass
        
        # Check Bed
        if 'bed_id' in resource_ids:
            try:
                bed = Bed.objects.get(id=resource_ids['bed_id'])
                if bed.room.unit.account != user_account:
                    return f"Bed {bed.id} (belongs to different account)"
            except Bed.DoesNotExist:
                pass
        
        # Check PGRoom
        if 'room_id' in resource_ids:
            try:
                room = PGRoom.objects.get(id=resource_ids['room_id'])
                if room.unit.account != user_account:
                    return f"Room {room.id} (belongs to different account)"
            except PGRoom.DoesNotExist:
                pass
        
        # All checks passed
        return None
    
    def _check_building_access(self, user, resource_ids):
        """
        Verify that user has access to the building (for managers).
        
        Owners automatically have access to all buildings.
        Managers only have access to explicitly granted buildings.
        
        Returns:
            str: Description of violation if found, None if all checks pass
        """
        # Owners have access to all buildings - skip this check
        if user.role == 'OWNER':
            return None
        
        # For managers, check building-level access
        if user.role == 'MANAGER':
            from buildings.access import can_access_building
            from buildings.models import Building
            from units.models import Unit, Bed
            from occupancy.models import Occupancy
            from rent.models import Rent
            from issues.models import Issue
            
            building_to_check = None
            
            # Direct building access
            if 'building_id' in resource_ids:
                try:
                    building_to_check = Building.objects.get(id=resource_ids['building_id'])
                except Building.DoesNotExist:
                    pass
            
            # Unit access - check unit's building
            elif 'unit_id' in resource_ids:
                try:
                    unit = Unit.objects.get(id=resource_ids['unit_id'])
                    building_to_check = unit.building
                except Unit.DoesNotExist:
                    pass
            
            # Occupancy access - check building via unit or bed
            elif 'occupancy_id' in resource_ids:
                try:
                    occupancy = Occupancy.objects.get(id=resource_ids['occupancy_id'])
                    if occupancy.unit:
                        building_to_check = occupancy.unit.building
                    elif occupancy.bed:
                        building_to_check = occupancy.bed.room.unit.building
                except Occupancy.DoesNotExist:
                    pass
            
            # Rent access - check building via occupancy
            elif 'rent_id' in resource_ids:
                try:
                    rent = Rent.objects.get(id=resource_ids['rent_id'])
                    if rent.occupancy.unit:
                        building_to_check = rent.occupancy.unit.building
                    elif rent.occupancy.bed:
                        building_to_check = rent.occupancy.bed.room.unit.building
                except Rent.DoesNotExist:
                    pass
            
            # Issue access - check building via unit
            elif 'issue_id' in resource_ids:
                try:
                    issue = Issue.objects.get(id=resource_ids['issue_id'])
                    building_to_check = issue.unit.building
                except Issue.DoesNotExist:
                    pass
            
            # Bed access - check building via room
            elif 'bed_id' in resource_ids:
                try:
                    bed = Bed.objects.get(id=resource_ids['bed_id'])
                    building_to_check = bed.room.unit.building
                except Bed.DoesNotExist:
                    pass
            
            # Check if manager has access to the building
            if building_to_check:
                if not can_access_building(user, building_to_check):
                    return f"Building {building_to_check.name} (not granted to manager)"
        
        # All checks passed
        return None


class RequestLoggingMiddleware:
    """
    Optional middleware to log all API requests for security auditing.
    
    Logs:
    - User
    - Method
    - Path
    - Resource IDs accessed
    - Response status
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Skip logging for static files and health checks
        if request.path.startswith(('/static/', '/media/', '/health/')):
            return self.get_response(request)
        
        # Log request
        if request.user and request.user.is_authenticated:
            logger.info(
                f"Request: {request.method} {request.path} "
                f"by {request.user.username} ({request.user.role})"
            )
        
        # Process request
        response = self.get_response(request)
        
        # Log response status for failed requests
        if response.status_code >= 400:
            logger.warning(
                f"Failed request: {request.method} {request.path} "
                f"by {request.user.username if request.user.is_authenticated else 'Anonymous'} "
                f"- Status {response.status_code}"
            )
        
        return response

