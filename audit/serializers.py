"""
Audit Log Serializers
"""

from rest_framework import serializers
from audit.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    """
    Serializer for AuditLog model.
    
    Read-only: Audit logs cannot be created/updated via API.
    """
    
    user_display = serializers.CharField(read_only=True)
    action_display = serializers.CharField(read_only=True)
    resource_display = serializers.CharField(read_only=True)
    
    user_username = serializers.CharField(source='user.username', read_only=True, allow_null=True)
    account_name = serializers.CharField(source='account.name', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id',
            'account',
            'account_name',
            'user',
            'user_username',
            'user_display',
            'action',
            'action_display',
            'resource_type',
            'resource_display',
            'resource_id',
            'description',
            'ip_address',
            'user_agent',
            'metadata',
            'timestamp'
        ]
        read_only_fields = fields  # All fields are read-only


class AuditLogSummarySerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for audit log summaries.
    """
    
    user_display = serializers.CharField(read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id',
            'user_display',
            'action',
            'resource_type',
            'description',
            'timestamp'
        ]
        read_only_fields = fields

