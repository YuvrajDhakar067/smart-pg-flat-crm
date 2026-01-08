from rest_framework import serializers
from .models import Rent
from occupancy.serializers import OccupancyListSerializer


def get_occupancy_queryset():
    """Get occupancy queryset - will be filtered in __init__"""
    from occupancy.models import Occupancy
    return Occupancy.objects.all()


class RentSerializer(serializers.ModelSerializer):
    """Serializer for Rent"""
    occupancy = OccupancyListSerializer(read_only=True)
    occupancy_id = serializers.PrimaryKeyRelatedField(
        queryset=get_occupancy_queryset(), source='occupancy', write_only=True, required=True
    )
    pending_amount = serializers.ReadOnlyField()
    
    class Meta:
        model = Rent
        fields = [
            'id', 'occupancy', 'occupancy_id', 'month', 'amount',
            'paid_amount', 'pending_amount', 'status', 'paid_date',
            'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'status', 'pending_amount', 'created_at', 'updated_at']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter queryset based on user account
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            user = request.user
            from occupancy.models import Occupancy
            self.fields['occupancy_id'].queryset = Occupancy.objects.filter(tenant__account=user.account)


class RentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list view"""
    tenant_name = serializers.CharField(source='occupancy.tenant.name', read_only=True)
    location = serializers.CharField(source='occupancy.location', read_only=True)
    pending_amount = serializers.ReadOnlyField()
    
    class Meta:
        model = Rent
        fields = [
            'id', 'tenant_name', 'location', 'month', 'amount',
            'paid_amount', 'pending_amount', 'status', 'paid_date'
        ]

