"""
Utilities for tracking and managing concurrent editing sessions
Uses cache-based locking for fast concurrent detection (free, no external dependencies)
Falls back to database model for persistence and audit trail
"""
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from .models import EditingSession
import logging

logger = logging.getLogger(__name__)


def _get_request_id():
    """Get request ID from thread-local storage"""
    try:
        thread_local = getattr(logging, '_thread_local', None)
        if thread_local:
            return getattr(thread_local, 'request_id', 'N/A')
    except Exception:
        pass
    return 'N/A'


def _log_with_request_id(level, message, exc_info=False):
    """Log message with request ID context"""
    request_id = _get_request_id()
    extra = {'request_id': request_id}
    if level == 'error':
        logger.error(f"[{request_id}] {message}", exc_info=exc_info, extra=extra)
    elif level == 'warning':
        logger.warning(f"[{request_id}] {message}", extra=extra)

# Cache timeout (5 minutes) - matches session timeout
CACHE_TIMEOUT = 300
CACHE_KEY_PREFIX = 'editing_session'


def _get_cache_key(resource_type, resource_id):
    """Generate cache key for a resource"""
    return f"{CACHE_KEY_PREFIX}:{resource_type}:{resource_id}"


def start_editing_session(user, resource_type, resource_id, action='edit', ip_address=None):
    """
    Start or update an editing session for a resource.
    Uses cache-based locking for fast concurrent detection.
    Returns (session, is_new) tuple.
    """
    cache_key = _get_cache_key(resource_type, resource_id)
    
    try:
        # Fast check using cache (atomic operation)
        cache_data = cache.get(cache_key)
        
        if cache_data:
            # Session exists in cache
            cached_user_id = cache_data.get('user_id')
            
            # If different user is editing, deny
            if cached_user_id != user.id:
                # Try to get database session for return
                try:
                    session = EditingSession.objects.filter(
                        resource_type=resource_type,
                        resource_id=resource_id
                    ).select_related('user').first()
                    return session, False
                except Exception:
                    return None, False
            
            # Same user - update cache and database
            cache_data['last_activity'] = timezone.now().isoformat()
            cache.set(cache_key, cache_data, CACHE_TIMEOUT)
            
            # Update database session
            with transaction.atomic():
                session, _ = EditingSession.objects.get_or_create(
                    resource_type=resource_type,
                    resource_id=resource_id,
                    defaults={
                        'user': user,
                        'action': action,
                        'ip_address': ip_address,
                        'started_at': timezone.now(),
                        'last_activity': timezone.now(),
                    }
                )
                if session.user == user:
                    session.update_activity()
            
            return session, False
        
        # No existing session - create new one
        # Use cache.add() for atomic lock acquisition
        session_data = {
            'user_id': user.id,
            'user_name': user.get_full_name() or user.username,
            'action': action,
            'started_at': timezone.now().isoformat(),
            'last_activity': timezone.now().isoformat(),
        }
        
        # Try to acquire lock atomically
        if cache.add(cache_key, session_data, CACHE_TIMEOUT):
            # Lock acquired - create database session
            with transaction.atomic():
                session, created = EditingSession.objects.get_or_create(
                    resource_type=resource_type,
                    resource_id=resource_id,
                    defaults={
                        'user': user,
                        'action': action,
                        'ip_address': ip_address,
                        'started_at': timezone.now(),
                        'last_activity': timezone.now(),
                    }
                )
                if not created:
                    # Session already exists in DB but cache was empty (stale)
                    session.user = user
                    session.action = action
                    session.ip_address = ip_address
                    session.started_at = timezone.now()
                    session.last_activity = timezone.now()
                    session.save()
                    created = True
            
            return session, created
        else:
            # Lock acquisition failed - someone else got it
            # This is a race condition, check again
            cache_data = cache.get(cache_key)
            if cache_data and cache_data.get('user_id') != user.id:
                try:
                    session = EditingSession.objects.filter(
                        resource_type=resource_type,
                        resource_id=resource_id
                    ).select_related('user').first()
                    return session, False
                except Exception:
                    return None, False
            
            # Edge case - retry
            return start_editing_session(user, resource_type, resource_id, action, ip_address)
            
    except Exception as e:
        _log_with_request_id('error', f"Error starting editing session: {e}", exc_info=True)
        # Fallback to database-only approach
        try:
            with transaction.atomic():
                session, created = EditingSession.objects.get_or_create(
                    resource_type=resource_type,
                    resource_id=resource_id,
                    defaults={
                        'user': user,
                        'action': action,
                        'ip_address': ip_address,
                        'started_at': timezone.now(),
                        'last_activity': timezone.now(),
                    }
                )
                if not created and session.user != user:
                    return session, False
                if not created:
                    session.update_activity()
                return session, created
        except Exception as e2:
            _log_with_request_id('error', f"Error in fallback database session: {e2}")
            return None, False


def check_editing_session(resource_type, resource_id, current_user=None):
    """
    Check if someone is currently editing a resource.
    Uses fast cache lookup first, falls back to database.
    Returns (is_being_edited, session, message) tuple.
    """
    cache_key = _get_cache_key(resource_type, resource_id)
    
    try:
        # Fast cache check first
        cache_data = cache.get(cache_key)
        
        if cache_data:
            cached_user_id = cache_data.get('user_id')
            cached_user_name = cache_data.get('user_name', 'Unknown')
            
            # If checking for current user, allow them to continue
            if current_user and cached_user_id == current_user.id:
                return False, None, None
            
            # Someone else is editing
            message = (
                f"{cached_user_name} is currently editing this. "
                f"Please wait or try again in a few minutes."
            )
            
            # Get database session for return
            try:
                session = EditingSession.objects.filter(
                    resource_type=resource_type,
                    resource_id=resource_id
                ).select_related('user').first()
                return True, session, message
            except Exception:
                return True, None, message
        
        # Cache miss - check database (might be stale cache)
        session = EditingSession.objects.filter(
            resource_type=resource_type,
            resource_id=resource_id
        ).select_related('user').first()
        
        if not session:
            return False, None, None
        
        # Check if session is still active
        if not session.is_active():
            # Stale session - clean it up
            session.delete()
            cache.delete(cache_key)  # Clean cache too
            return False, None, None
        
        # Update cache with database data
        cache_data = {
            'user_id': session.user.id,
            'user_name': session.user.get_full_name() or session.user.username,
            'action': session.action,
            'started_at': session.started_at.isoformat() if session.started_at else None,
            'last_activity': session.last_activity.isoformat() if session.last_activity else None,
        }
        cache.set(cache_key, cache_data, CACHE_TIMEOUT)
        
        # If checking for current user, allow them to continue
        if current_user and session.user == current_user:
            return False, session, None
        
        # Someone else is editing
        message = (
            f"{session.user.get_full_name() or session.user.username} is currently editing this. "
            f"Please wait or try again in a few minutes."
        )
        
        return True, session, message
        
    except Exception as e:
        _log_with_request_id('error', f"Error checking editing session: {e}", exc_info=True)
        return False, None, None


def end_editing_session(resource_type, resource_id, user=None):
    """
    End an editing session for a resource.
    Clears both cache and database.
    """
    cache_key = _get_cache_key(resource_type, resource_id)
    
    try:
        # Clear cache first (fast)
        cache_data = cache.get(cache_key)
        if cache_data:
            # Only clear if it's the same user (or no user specified)
            if not user or cache_data.get('user_id') == user.id:
                cache.delete(cache_key)
        
        # Clear database session
        query = EditingSession.objects.filter(
            resource_type=resource_type,
            resource_id=resource_id
        )
        
        # If user specified, only end if it's their session
        if user:
            query = query.filter(user=user)
        
        deleted_count = query.delete()[0]
        return deleted_count > 0
    except Exception as e:
        _log_with_request_id('error', f"Error ending editing session: {e}", exc_info=True)
        return False


def cleanup_stale_sessions(timeout_seconds=300):
    """
    Clean up stale editing sessions (older than timeout).
    Cleans both cache and database.
    Returns number of sessions cleaned up.
    """
    try:
        cutoff = timezone.now() - timezone.timedelta(seconds=timeout_seconds)
        
        # Get stale sessions from database
        stale_sessions = EditingSession.objects.filter(
            last_activity__lt=cutoff
        )
        
        # Clear cache for stale sessions
        for session in stale_sessions:
            cache_key = _get_cache_key(session.resource_type, session.resource_id)
            cache.delete(cache_key)
        
        # Delete from database
        deleted_count = stale_sessions.delete()[0]
        return deleted_count
    except Exception as e:
        _log_with_request_id('error', f"Error cleaning up stale sessions: {e}", exc_info=True)
        return 0

