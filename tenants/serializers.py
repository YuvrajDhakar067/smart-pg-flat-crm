from rest_framework import serializers
from .models import Tenant


class TenantSerializer(serializers.ModelSerializer):
    """Serializer for Tenant"""
    current_occupancy_location = serializers.SerializerMethodField()
    
    class Meta:
        model = Tenant
        fields = [
            'id', 'account', 'name', 'phone', 'email',
            'id_proof_type', 'id_proof_number', 'address',
            'emergency_contact', 'current_occupancy_location',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'account', 'created_at', 'updated_at']
    
    def get_current_occupancy_location(self, obj):
        """Get current occupancy location"""
        occupancy = obj.current_occupancy
        if occupancy:
            return occupancy.location
        return None


class TenantListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list view"""
    has_active_occupancy = serializers.SerializerMethodField()
    
    class Meta:
        model = Tenant
        fields = ['id', 'name', 'phone', 'email', 'has_active_occupancy']
    
    def get_has_active_occupancy(self, obj):
        """Check if tenant has active occupancy"""
        return obj.current_occupancy is not None

