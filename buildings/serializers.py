from rest_framework import serializers
from .models import Building


class BuildingSerializer(serializers.ModelSerializer):
    """Serializer for Building"""
    total_units = serializers.ReadOnlyField()
    occupied_units = serializers.ReadOnlyField()
    vacant_units = serializers.ReadOnlyField()
    
    class Meta:
        model = Building
        fields = [
            'id', 'account', 'name', 'address', 'total_floors',
            'total_units', 'occupied_units', 'vacant_units',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'account', 'created_at', 'updated_at']


class BuildingListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list view"""
    total_units = serializers.ReadOnlyField()
    occupied_units = serializers.ReadOnlyField()
    vacant_units = serializers.ReadOnlyField()
    
    class Meta:
        model = Building
        fields = [
            'id', 'name', 'address', 'total_floors',
            'total_units', 'occupied_units', 'vacant_units'
        ]

