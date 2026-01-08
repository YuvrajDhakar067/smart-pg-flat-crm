"""
Audit Logging Signals

Automatically log actions using Django signals.
"""

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out

from buildings.models import Building
from units.models import Unit
from tenants.models import Tenant
from occupancy.models import Occupancy
from rent.models import Rent
from issues.models import Issue

from audit.models import AuditLog
from audit.helpers import (
    log_action,
    log_building_create,
    log_building_update,
    log_tenant_assignment,
    log_rent_payment,
    log_vacate
)


# ============================================================================
# AUTH SIGNALS
# ============================================================================

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Log successful login"""
    from audit.helpers import log_login
    log_login(user, request, success=True)


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """Log logout"""
    if user:
        from audit.helpers import log_logout
        log_logout(user, request)


# ============================================================================
# BUILDING SIGNALS
# ============================================================================

@receiver(post_save, sender=Building)
def log_building_save(sender, instance, created, **kwargs):
    """Log building creation/update"""
    if created:
        # Get the user from the current request (if available)
        # For signals, we need to pass user context
        # This will be handled by view decorators/methods
        pass
    else:
        # Update
        pass


# ============================================================================
# ISSUE STATUS CHANGE TRACKING
# ============================================================================

# Store previous status for comparison
_issue_previous_status = {}


@receiver(pre_save, sender=Issue)
def track_issue_status_before(sender, instance, **kwargs):
    """Track previous issue status before save"""
    if instance.pk:
        try:
            old_issue = Issue.objects.get(pk=instance.pk)
            _issue_previous_status[instance.pk] = old_issue.status
        except Issue.DoesNotExist:
            pass


@receiver(post_save, sender=Issue)
def log_issue_status_change_signal(sender, instance, created, **kwargs):
    """Log issue status changes"""
    if not created and instance.pk in _issue_previous_status:
        old_status = _issue_previous_status.pop(instance.pk)
        new_status = instance.status
        
        if old_status != new_status:
            # Status changed - log it
            # Note: We don't have request context here, so user will be None
            # Better to log this explicitly in views
            pass


# ============================================================================
# RENT STATUS CHANGE TRACKING
# ============================================================================

_rent_previous_status = {}


@receiver(pre_save, sender=Rent)
def track_rent_status_before(sender, instance, **kwargs):
    """Track previous rent status before save"""
    if instance.pk:
        try:
            old_rent = Rent.objects.get(pk=instance.pk)
            _rent_previous_status[instance.pk] = {
                'status': old_rent.status,
                'paid_amount': old_rent.paid_amount
            }
        except Rent.DoesNotExist:
            pass


@receiver(post_save, sender=Rent)
def log_rent_status_change_signal(sender, instance, created, **kwargs):
    """Log rent payment changes"""
    if not created and instance.pk in _rent_previous_status:
        old_data = _rent_previous_status.pop(instance.pk)
        
        # Check if payment was made
        if old_data['paid_amount'] != instance.paid_amount:
            # Payment was made - log it
            # Better to log this explicitly in views where we have user context
            pass


# Note: Most audit logging should be done explicitly in views/ViewSets
# where we have access to request.user and request context.
# Signals are useful for system-level events, but explicit logging
# in views provides better control and user attribution.

