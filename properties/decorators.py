"""
Custom decorators for role-based access control
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def owner_or_manager_required(view_func):
    """
    Decorator to ensure only OWNER or MANAGER can access the view.
    Tenants are not allowed.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        # Check if user has role
        if not hasattr(request.user, 'role'):
            messages.error(request, 'Your account does not have a valid role.')
            return redirect('accounts:profile')
        
        # Only allow OWNER or MANAGER
        if request.user.role not in ['OWNER', 'MANAGER']:
            messages.error(request, 'Access denied. This section is only for Owners and Managers.')
            return redirect('accounts:profile')
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view

