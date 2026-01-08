from rest_framework import serializers
from .models import Issue
from units.serializers import UnitListSerializer
from tenants.serializers import TenantListSerializer


def get_unit_queryset():
    """Get unit queryset - will be filtered in __init__"""
    from units.models import Unit
    return Unit.objects.all()


def get_tenant_queryset():
    """Get tenant queryset - will be filtered in __init__"""
    from tenants.models import Tenant
    return Tenant.objects.all()


class IssueSerializer(serializers.ModelSerializer):
    """Serializer for Issue"""
    unit = UnitListSerializer(read_only=True)
    unit_id = serializers.PrimaryKeyRelatedField(
        queryset=get_unit_queryset(), source='unit', write_only=True, required=True
    )
    tenant = TenantListSerializer(read_only=True)
    tenant_id = serializers.PrimaryKeyRelatedField(
        queryset=get_tenant_queryset(), source='tenant', write_only=True, required=False, allow_null=True
    )
    
    class Meta:
        model = Issue
        fields = [
            'id', 'unit', 'unit_id', 'tenant', 'tenant_id',
            'title', 'description', 'status', 'priority',
            'assigned_to', 'raised_date', 'resolved_date',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'raised_date', 'resolved_date', 'created_at', 'updated_at']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter querysets based on user account
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            user = request.user
            from units.models import Unit
            from tenants.models import Tenant
            self.fields['unit_id'].queryset = Unit.objects.filter(account=user.account)
            self.fields['tenant_id'].queryset = Tenant.objects.filter(account=user.account)


class IssueListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list view"""
    unit_number = serializers.CharField(source='unit.unit_number', read_only=True)
    building_name = serializers.CharField(source='unit.building.name', read_only=True)
    tenant_name = serializers.CharField(source='tenant.name', read_only=True, allow_null=True)
    
    class Meta:
        model = Issue
        fields = [
            'id', 'building_name', 'unit_number', 'tenant_name',
            'title', 'status', 'priority', 'assigned_to', 'raised_date'
        ]

