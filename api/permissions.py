"""
Multi-tenant permissions - ensure users can only access their own account data
"""
from rest_framework import permissions


class IsAccountOwner(permissions.BasePermission):
    """
    Permission to only allow users to access data belonging to their account.
    """
    
    def has_permission(self, request, view):
        """Check if user is authenticated"""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Check if object belongs to user's account"""
        # Get account from object
        account = getattr(obj, 'account', None)
        if not account:
            # Try to get from related objects
            if hasattr(obj, 'tenant'):
                account = obj.tenant.account
            elif hasattr(obj, 'unit'):
                account = obj.unit.account
            elif hasattr(obj, 'building'):
                account = obj.building.account
            elif hasattr(obj, 'occupancy'):
                account = obj.occupancy.account
        
        # Check if account matches user's account
        if account and request.user.account == account:
            return True
        
        return False


class IsOwnerOrManager(permissions.BasePermission):
    """
    Permission to allow Owner and Manager roles
    """
    
    def has_permission(self, request, view):
        """Check if user is authenticated and has correct role"""
        if not (request.user and request.user.is_authenticated):
            return False
        
        # Allow Owner and Manager
        return request.user.role in ['OWNER', 'MANAGER']

