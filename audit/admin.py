"""
Audit Log Admin - READ ONLY

Audit logs are immutable and cannot be edited or deleted via admin.
"""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """
    Read-only admin for audit logs.
    
    Features:
    - View logs only (no edit/delete)
    - Filter by action, resource type, user, date
    - Search by description
    - Display metadata in JSON format
    """
    
    list_display = [
        'id',
        'timestamp',
        'user_link',
        'action',
        'resource_type',
        'resource_id',
        'description_short',
        'ip_address'
    ]
    
    list_filter = [
        'action',
        'resource_type',
        'timestamp',
        ('user', admin.RelatedOnlyFieldListFilter),
    ]
    
    search_fields = [
        'description',
        'user__username',
        'user__email',
        'ip_address'
    ]
    
    readonly_fields = [
        'account',
        'user',
        'action',
        'resource_type',
        'resource_id',
        'description',
        'ip_address',
        'user_agent',
        'metadata_display',
        'timestamp'
    ]
    
    fieldsets = (
        ('Action Details', {
            'fields': ('action', 'resource_type', 'resource_id', 'description')
        }),
        ('User Information', {
            'fields': ('account', 'user', 'ip_address', 'user_agent')
        }),
        ('Additional Context', {
            'fields': ('metadata_display', 'timestamp'),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'timestamp'
    
    ordering = ['-timestamp']
    
    # Disable all editing
    def has_add_permission(self, request):
        """Disable manual creation via admin"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable editing"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Disable deletion"""
        return False
    
    def get_actions(self, request):
        """Disable bulk actions"""
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions
    
    @admin.display(description='User')
    def user_link(self, obj):
        """Display user as clickable link"""
        if obj.user:
            url = reverse('admin:users_user_change', args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return "System"
    
    @admin.display(description='Description')
    def description_short(self, obj):
        """Display truncated description"""
        max_length = 80
        if len(obj.description) > max_length:
            return f"{obj.description[:max_length]}..."
        return obj.description
    
    @admin.display(description='Metadata')
    def metadata_display(self, obj):
        """Display metadata in formatted JSON"""
        if obj.metadata:
            import json
            return format_html(
                '<pre>{}</pre>',
                json.dumps(obj.metadata, indent=2)
            )
        return "No metadata"

