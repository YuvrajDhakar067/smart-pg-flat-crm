from rest_framework import serializers
from .models import Occupancy
from tenants.serializers import TenantListSerializer
from units.serializers import UnitListSerializer


def get_tenant_queryset():
    """Get tenant queryset - will be filtered in __init__"""
    from tenants.models import Tenant
    return Tenant.objects.all()


def get_unit_queryset():
    """Get unit queryset - will be filtered in __init__"""
    from units.models import Unit
    return Unit.objects.filter(unit_type='FLAT')


def get_bed_queryset():
    """Get bed queryset - will be filtered in __init__"""
    from units.models import Bed
    return Bed.objects.all()


class OccupancySerializer(serializers.ModelSerializer):
    """Serializer for Occupancy"""
    tenant = TenantListSerializer(read_only=True)
    tenant_id = serializers.PrimaryKeyRelatedField(
        queryset=get_tenant_queryset(), source='tenant', write_only=True, required=True
    )
    unit = UnitListSerializer(read_only=True)
    unit_id = serializers.PrimaryKeyRelatedField(
        queryset=get_unit_queryset(), source='unit', write_only=True, required=False, allow_null=True
    )
    bed_id = serializers.PrimaryKeyRelatedField(
        queryset=get_bed_queryset(), source='bed', write_only=True, required=False, allow_null=True
    )
    location = serializers.ReadOnlyField()
    
    class Meta:
        model = Occupancy
        fields = [
            'id', 'tenant', 'tenant_id', 'unit', 'unit_id', 'bed_id',
            'rent', 'deposit', 'start_date', 'end_date', 'is_active',
            'agreement_document', 'notes', 'location', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'location', 'created_at', 'updated_at']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter querysets based on user account
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            user = request.user
            from tenants.models import Tenant
            from units.models import Unit, Bed
            self.fields['tenant_id'].queryset = Tenant.objects.filter(account=user.account)
            self.fields['unit_id'].queryset = Unit.objects.filter(account=user.account, unit_type='FLAT')
            self.fields['bed_id'].queryset = Bed.objects.filter(room__unit__account=user.account)
    
    def validate(self, data):
        """Validate that either unit or bed is set, not both"""
        unit = data.get('unit')
        bed = data.get('bed')
        
        if not unit and not bed:
            raise serializers.ValidationError("Either unit (for flat) or bed (for PG) must be set.")
        
        if unit and bed:
            raise serializers.ValidationError("Cannot set both unit and bed. Use unit for flats, bed for PGs.")
        
        if unit and unit.unit_type != 'FLAT':
            raise serializers.ValidationError("Unit must be of type FLAT.")
        
        if bed and bed.room.unit.unit_type != 'PG':
            raise serializers.ValidationError("Bed must belong to a PG unit.")
        
        return data


class OccupancyListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list view"""
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    location = serializers.ReadOnlyField()
    
    class Meta:
        model = Occupancy
        fields = [
            'id', 'tenant_name', 'location', 'rent',
            'start_date', 'end_date', 'is_active'
        ]

