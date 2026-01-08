"""
Audit Logging Helper Functions

Provides a centralized way to log all system actions.
"""

from audit.models import AuditLog
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


def log_action(user, action, resource_type, resource_id, description, request=None, metadata=None):
    """
    Log an action to the audit log.
    
    Args:
        user: User who performed the action
        action: Action type (CREATE, UPDATE, DELETE, etc.)
        resource_type: Type of resource (Building, Unit, etc.)
        resource_id: ID of the resource
        description: Human-readable description
        request: Django request object (optional)
        metadata: Additional context data (optional)
    
    Returns:
        AuditLog instance
    
    Example:
        log_action(
            user=request.user,
            action=AuditLog.ACTION_CREATE,
            resource_type=AuditLog.RESOURCE_BUILDING,
            resource_id=building.id,
            description=f"Created building: {building.name}",
            request=request
        )
    """
    try:
        # Get user's account
        account = user.account if hasattr(user, 'account') else None
        
        if not account:
            logger.warning(f"Cannot log action: User {user.username} has no account")
            return None
        
        # Extract IP address from request
        ip_address = None
        user_agent = None
        
        if request:
            ip_address = get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]  # Limit length
        
        # Create audit log entry
        audit_log = AuditLog.objects.create(
            account=account,
            user=user,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata or {}
        )
        
        logger.info(f"Audit: {user.username} - {action} - {resource_type} #{resource_id}")
        
        return audit_log
        
    except Exception as e:
        # Don't fail the main operation if audit logging fails
        logger.error(f"Failed to create audit log: {e}", exc_info=True)
        return None


def log_action_async(user, action, resource_type, resource_id, description, request=None, metadata=None):
    """
    Log an action asynchronously (for performance-critical operations).
    
    Note: This is a placeholder. For true async logging, integrate with
    Celery or Django Channels.
    """
    # For now, just call the sync version
    # In production, you would queue this task
    return log_action(user, action, resource_type, resource_id, description, request, metadata)


def get_client_ip(request):
    """
    Extract client IP address from request.
    Handles proxies and load balancers.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    
    if x_forwarded_for:
        # X-Forwarded-For can contain multiple IPs, get the first one
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    
    return ip


def log_login(user, request, success=True):
    """Log user login"""
    description = f"User {user.username} logged in successfully" if success else f"Failed login attempt for {user.username}"
    
    return log_action(
        user=user,
        action=AuditLog.ACTION_LOGIN,
        resource_type=AuditLog.RESOURCE_USER,
        resource_id=user.id,
        description=description,
        request=request,
        metadata={'success': success}
    )


def log_logout(user, request):
    """Log user logout"""
    return log_action(
        user=user,
        action=AuditLog.ACTION_LOGOUT,
        resource_type=AuditLog.RESOURCE_USER,
        resource_id=user.id,
        description=f"User {user.username} logged out",
        request=request
    )


def log_building_create(user, building, request=None):
    """Log building creation"""
    return log_action(
        user=user,
        action=AuditLog.ACTION_CREATE,
        resource_type=AuditLog.RESOURCE_BUILDING,
        resource_id=building.id,
        description=f"Created building: {building.name}",
        request=request,
        metadata={
            'building_name': building.name,
            'address': building.address
        }
    )


def log_building_update(user, building, request=None):
    """Log building update"""
    return log_action(
        user=user,
        action=AuditLog.ACTION_UPDATE,
        resource_type=AuditLog.RESOURCE_BUILDING,
        resource_id=building.id,
        description=f"Updated building: {building.name}",
        request=request,
        metadata={
            'building_name': building.name
        }
    )


def log_tenant_assignment(user, occupancy, request=None):
    """Log tenant assignment to unit/bed"""
    if occupancy.unit:
        resource_name = f"Unit {occupancy.unit.unit_number}"
    elif occupancy.bed:
        resource_name = f"Bed {occupancy.bed.bed_number} in Room {occupancy.bed.room.unit.unit_number}"
    else:
        resource_name = "Unknown"
    
    return log_action(
        user=user,
        action=AuditLog.ACTION_ASSIGN_TENANT,
        resource_type=AuditLog.RESOURCE_OCCUPANCY,
        resource_id=occupancy.id,
        description=f"Assigned tenant {occupancy.tenant.name} to {resource_name}",
        request=request,
        metadata={
            'tenant_id': occupancy.tenant.id,
            'tenant_name': occupancy.tenant.name,
            'unit_id': occupancy.unit.id if occupancy.unit else None,
            'bed_id': occupancy.bed.id if occupancy.bed else None,
            'rent': str(occupancy.rent)
        }
    )


def log_rent_payment(user, rent, request=None):
    """Log rent payment"""
    return log_action(
        user=user,
        action=AuditLog.ACTION_PAY_RENT,
        resource_type=AuditLog.RESOURCE_RENT,
        resource_id=rent.id,
        description=f"Rent payment: ₹{rent.paid_amount} for {rent.occupancy.tenant.name} ({rent.month.strftime('%B %Y')})",
        request=request,
        metadata={
            'tenant_id': rent.occupancy.tenant.id,
            'tenant_name': rent.occupancy.tenant.name,
            'amount': str(rent.paid_amount),
            'month': rent.month.isoformat(),
            'status': rent.status
        }
    )


def log_issue_status_change(user, issue, old_status, new_status, request=None):
    """Log issue status change"""
    return log_action(
        user=user,
        action=AuditLog.ACTION_UPDATE,
        resource_type=AuditLog.RESOURCE_ISSUE,
        resource_id=issue.id,
        description=f"Changed issue status from {old_status} to {new_status}: {issue.title}",
        request=request,
        metadata={
            'issue_title': issue.title,
            'old_status': old_status,
            'new_status': new_status,
            'priority': issue.priority
        }
    )


def log_access_grant(user, building_access, request=None):
    """Log building access grant"""
    return log_action(
        user=user,
        action=AuditLog.ACTION_GRANT_ACCESS,
        resource_type=AuditLog.RESOURCE_BUILDING_ACCESS,
        resource_id=building_access.id,
        description=f"Granted {building_access.user.username} access to building: {building_access.building.name}",
        request=request,
        metadata={
            'granted_to_user_id': building_access.user.id,
            'granted_to_username': building_access.user.username,
            'building_id': building_access.building.id,
            'building_name': building_access.building.name
        }
    )


def log_access_revoke(user, building_access, request=None):
    """Log building access revocation"""
    return log_action(
        user=user,
        action=AuditLog.ACTION_REVOKE_ACCESS,
        resource_type=AuditLog.RESOURCE_BUILDING_ACCESS,
        resource_id=building_access.id,
        description=f"Revoked {building_access.user.username}'s access to building: {building_access.building.name}",
        request=request,
        metadata={
            'revoked_from_user_id': building_access.user.id,
            'revoked_from_username': building_access.user.username,
            'building_id': building_access.building.id,
            'building_name': building_access.building.name
        }
    )


def log_vacate(user, occupancy, request=None):
    """Log tenant vacating unit/bed"""
    if occupancy.unit:
        resource_name = f"Unit {occupancy.unit.unit_number}"
    elif occupancy.bed:
        resource_name = f"Bed {occupancy.bed.bed_number}"
    else:
        resource_name = "Unknown"
    
    return log_action(
        user=user,
        action=AuditLog.ACTION_VACATE,
        resource_type=AuditLog.RESOURCE_OCCUPANCY,
        resource_id=occupancy.id,
        description=f"Tenant {occupancy.tenant.name} vacated {resource_name}",
        request=request,
        metadata={
            'tenant_id': occupancy.tenant.id,
            'tenant_name': occupancy.tenant.name,
            'end_date': occupancy.end_date.isoformat() if occupancy.end_date else None
        }
    )


def get_resource_audit_trail(resource_type, resource_id, limit=50):
    """
    Get complete audit trail for a specific resource.
    
    Args:
        resource_type: Type of resource (Building, Unit, etc.)
        resource_id: ID of the resource
        limit: Maximum number of logs to return
    
    Returns:
        QuerySet of AuditLog entries
    """
    return AuditLog.objects.filter(
        resource_type=resource_type,
        resource_id=resource_id
    ).order_by('-timestamp')[:limit]


def get_user_activity(user, limit=100):
    """
    Get recent activity for a specific user.
    
    Args:
        user: User instance
        limit: Maximum number of logs to return
    
    Returns:
        QuerySet of AuditLog entries
    """
    return AuditLog.objects.filter(
        user=user
    ).order_by('-timestamp')[:limit]

