"""
Custom decorators for security and error handling with request ID logging
"""
from functools import wraps
from django.shortcuts import redirect, render
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
import logging

logger = logging.getLogger(__name__)


def _get_request_id(request):
    """Get request ID from request object"""
    return getattr(request, 'request_id', 'N/A')


def _log_with_request_id(level, request, message, exc_info=False):
    """Log message with request ID context"""
    request_id = _get_request_id(request)
    extra = {'request_id': request_id}
    if level == 'error':
        logger.error(f"[{request_id}] {message}", exc_info=exc_info, extra=extra)
    elif level == 'warning':
        logger.warning(f"[{request_id}] {message}", extra=extra)
    elif level == 'info':
        logger.info(f"[{request_id}] {message}", extra=extra)


def owner_or_manager_required(view_func):
    """
    Decorator to ensure only Owner or Manager can access the view
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please login to access this page.')
            return redirect('accounts:login')
        
        if not hasattr(request.user, 'role') or request.user.role not in ['OWNER', 'MANAGER']:
            messages.error(request, 'Access denied. Only Owners and Managers can access this page.')
            _log_with_request_id('warning', request, 
                f"Unauthorized access attempt by user {request.user.username} (role: {getattr(request.user, 'role', 'None')})")
            return redirect('accounts:login')
        
        # Check if user has account
        if not hasattr(request.user, 'account') or not request.user.account:
            messages.warning(request, 'Your account is not properly configured. Please contact administrator.')
            return redirect('accounts:profile')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def handle_errors(view_func):
    """
    Decorator to handle common errors gracefully with proper logging
    Only logs important errors, not every exception
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except Http404:
            # 404 errors are common and expected - don't log
            raise
        except PermissionDenied:
            messages.error(request, 'You do not have permission to access this resource.')
            _log_with_request_id('warning', request, 
                f"Permission denied for user {request.user.username if request.user.is_authenticated else 'Anonymous'} - {view_func.__name__}")
            # Avoid redirect loop - if already on dashboard, go to building list
            if request.resolver_match and request.resolver_match.url_name == 'dashboard':
                return redirect('properties:building_list')
            return redirect('properties:dashboard')
        except ValueError as e:
            # Validation errors - log but don't show full traceback
            _log_with_request_id('warning', request, 
                f"Validation error in {view_func.__name__}: {str(e)}")
            messages.error(request, f'Invalid input: {str(e)}')
            # Try to stay on same page if possible
            referer = request.META.get('HTTP_REFERER')
            if referer:
                return redirect(referer)
            return redirect('properties:dashboard')
        except Exception as e:
            # Only log unexpected errors (not common exceptions)
            error_type = type(e).__name__
            error_message = str(e)
            
            # Log with request ID and context
            _log_with_request_id('error', request, 
                f"Unexpected error in {view_func.__name__}: {error_type}: {error_message}", 
                exc_info=True)
            
            # User-friendly message
            messages.error(request, 'An error occurred. Please try again or contact support.')
            
            # Avoid redirect loop
            if request.resolver_match and request.resolver_match.url_name == 'dashboard':
                return redirect('properties:building_list')
            return redirect('properties:dashboard')
    return _wrapped_view


def account_required(view_func):
    """
    Decorator to ensure user has an account
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        account = getattr(request, 'account', None)
        if not account:
            if hasattr(request.user, 'account') and request.user.account:
                request.account = request.user.account
            else:
                messages.warning(request, 'Your account is not properly configured.')
                return redirect('accounts:profile')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

