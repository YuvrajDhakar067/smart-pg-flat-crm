"""
Audit Log Model

IMMUTABLE: Audit logs cannot be edited or deleted after creation.
Purpose: Complete transparency and accountability for all system actions.
"""

from django.db import models
from django.conf import settings
from django.core.exceptions import PermissionDenied


# ============================================================================
# CUSTOM MANAGER AND QUERYSET
# ============================================================================

class AuditLogQuerySet(models.QuerySet):
    """Custom queryset for audit logs with filtering helpers"""
    
    def for_account(self, account):
        """Filter logs for a specific account"""
        return self.filter(account=account)
    
    def for_user(self, user):
        """Filter logs for a specific user"""
        return self.filter(user=user)
    
    def for_resource(self, resource_type, resource_id):
        """Filter logs for a specific resource"""
        return self.filter(resource_type=resource_type, resource_id=resource_id)
    
    def for_action(self, action):
        """Filter logs for a specific action"""
        return self.filter(action=action)
    
    def recent(self, limit=100):
        """Get recent logs"""
        return self.order_by('-timestamp')[:limit]


class AuditLogManager(models.Manager):
    """Custom manager for audit logs"""
    
    def get_queryset(self):
        return AuditLogQuerySet(self.model, using=self._db)
    
    def for_account(self, account):
        return self.get_queryset().for_account(account)
    
    def for_user(self, user):
        return self.get_queryset().for_user(user)
    
    def for_resource(self, resource_type, resource_id):
        return self.get_queryset().for_resource(resource_type, resource_id)
    
    def for_action(self, action):
        return self.get_queryset().for_action(action)
    
    def recent(self, limit=100):
        return self.get_queryset().recent(limit)


# ============================================================================
# AUDIT LOG MODEL
# ============================================================================

class AuditLog(models.Model):
    """
    Immutable audit log for tracking all system actions.
    
    Security:
    - Logs CANNOT be edited after creation
    - Logs CANNOT be deleted (except via cascading account deletion)
    - Owner sees all logs in account
    - Manager sees logs only for assigned buildings
    """
    
    # Action types
    ACTION_CREATE = 'CREATE'
    ACTION_UPDATE = 'UPDATE'
    ACTION_DELETE = 'DELETE'
    ACTION_VIEW = 'VIEW'
    ACTION_LOGIN = 'LOGIN'
    ACTION_LOGOUT = 'LOGOUT'
    ACTION_GRANT_ACCESS = 'GRANT_ACCESS'
    ACTION_REVOKE_ACCESS = 'REVOKE_ACCESS'
    ACTION_PAY_RENT = 'PAY_RENT'
    ACTION_ASSIGN_TENANT = 'ASSIGN_TENANT'
    ACTION_VACATE = 'VACATE'
    
    ACTION_CHOICES = [
        (ACTION_CREATE, 'Create'),
        (ACTION_UPDATE, 'Update'),
        (ACTION_DELETE, 'Delete'),
        (ACTION_VIEW, 'View'),
        (ACTION_LOGIN, 'Login'),
        (ACTION_LOGOUT, 'Logout'),
        (ACTION_GRANT_ACCESS, 'Grant Access'),
        (ACTION_REVOKE_ACCESS, 'Revoke Access'),
        (ACTION_PAY_RENT, 'Pay Rent'),
        (ACTION_ASSIGN_TENANT, 'Assign Tenant'),
        (ACTION_VACATE, 'Vacate'),
    ]
    
    # Resource types
    RESOURCE_BUILDING = 'Building'
    RESOURCE_UNIT = 'Unit'
    RESOURCE_PGROOM = 'PGRoom'
    RESOURCE_BED = 'Bed'
    RESOURCE_TENANT = 'Tenant'
    RESOURCE_OCCUPANCY = 'Occupancy'
    RESOURCE_RENT = 'Rent'
    RESOURCE_ISSUE = 'Issue'
    RESOURCE_USER = 'User'
    RESOURCE_ACCOUNT = 'Account'
    RESOURCE_BUILDING_ACCESS = 'BuildingAccess'
    
    RESOURCE_TYPE_CHOICES = [
        (RESOURCE_BUILDING, 'Building'),
        (RESOURCE_UNIT, 'Unit'),
        (RESOURCE_PGROOM, 'PG Room'),
        (RESOURCE_BED, 'Bed'),
        (RESOURCE_TENANT, 'Tenant'),
        (RESOURCE_OCCUPANCY, 'Occupancy'),
        (RESOURCE_RENT, 'Rent'),
        (RESOURCE_ISSUE, 'Issue'),
        (RESOURCE_USER, 'User'),
        (RESOURCE_ACCOUNT, 'Account'),
        (RESOURCE_BUILDING_ACCESS, 'Building Access'),
    ]
    
    # Core fields
    account = models.ForeignKey(
        'accounts.Account',
        on_delete=models.CASCADE,
        related_name='audit_logs',
        help_text="Account this action belongs to"
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        help_text="User who performed the action"
    )
    
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        db_index=True,
        help_text="Type of action performed"
    )
    
    resource_type = models.CharField(
        max_length=50,
        choices=RESOURCE_TYPE_CHOICES,
        db_index=True,
        help_text="Type of resource affected"
    )
    
    resource_id = models.IntegerField(
        db_index=True,
        null=True,
        blank=True,
        help_text="ID of the resource affected"
    )
    
    description = models.TextField(
        help_text="Human-readable description of the action"
    )
    
    # Request metadata
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the user"
    )
    
    user_agent = models.TextField(
        null=True,
        blank=True,
        help_text="User agent string from request"
    )
    
    # Additional context (JSON)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional context data"
    )
    
    # Timestamp
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the action occurred"
    )
    
    class Meta:
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['account', '-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['resource_type', 'resource_id']),
            models.Index(fields=['action', '-timestamp']),
        ]
        permissions = [
            ('view_all_audit_logs', 'Can view all audit logs in account'),
        ]
    
    def __str__(self):
        username = self.user.username if self.user else 'System'
        return f"{username} - {self.action} - {self.resource_type} #{self.resource_id} - {self.timestamp}"
    
    def save(self, *args, **kwargs):
        """
        Override save to enforce immutability.
        Only allow creation, not updates.
        """
        if self.pk is not None:
            # This is an update attempt
            raise PermissionDenied(
                "Audit logs are immutable and cannot be modified after creation."
            )
        
        # Allow creation
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """
        Override delete to prevent deletion.
        """
        raise PermissionDenied(
            "Audit logs are immutable and cannot be deleted."
        )
    
    @property
    def user_display(self):
        """Get user display name"""
        if self.user:
            return self.user.get_full_name() or self.user.username
        return "System"
    
    @property
    def action_display(self):
        """Get human-readable action"""
        return dict(self.ACTION_CHOICES).get(self.action, self.action)
    
    @property
    def resource_display(self):
        """Get human-readable resource"""
        return dict(self.RESOURCE_TYPE_CHOICES).get(self.resource_type, self.resource_type)
    
    # Custom manager
    objects = AuditLogManager()


class AuditLogQuerySet(models.QuerySet):
    """Custom queryset for audit logs with filtering helpers"""
    
    def for_account(self, account):
        """Filter logs for a specific account"""
        return self.filter(account=account)
    
    def for_user(self, user):
        """Filter logs for a specific user"""
        return self.filter(user=user)
    
    def for_resource(self, resource_type, resource_id):
        """Filter logs for a specific resource"""
        return self.filter(resource_type=resource_type, resource_id=resource_id)
    
    def for_action(self, action):
        """Filter logs for a specific action"""
        return self.filter(action=action)
    
    def recent(self, limit=100):
        """Get recent logs"""
        return self.order_by('-timestamp')[:limit]


class AuditLogManager(models.Manager):
    """Custom manager for audit logs"""
    
    def get_queryset(self):
        return AuditLogQuerySet(self.model, using=self._db)
    
    def for_account(self, account):
        return self.get_queryset().for_account(account)
    
    def for_user(self, user):
        return self.get_queryset().for_user(user)
    
    def for_resource(self, resource_type, resource_id):
        return self.get_queryset().for_resource(resource_type, resource_id)
    
    def for_action(self, action):
        return self.get_queryset().for_action(action)
    
    def recent(self, limit=100):
        return self.get_queryset().recent(limit)

