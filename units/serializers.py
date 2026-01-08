from rest_framework import serializers
from .models import Unit, PGRoom, Bed


class BedSerializer(serializers.ModelSerializer):
    """Serializer for Bed"""
    
    class Meta:
        model = Bed
        fields = ['id', 'room', 'bed_number', 'status', 'created_at']
        read_only_fields = ['id', 'created_at']


class PGRoomSerializer(serializers.ModelSerializer):
    """Serializer for PGRoom"""
    beds = BedSerializer(many=True, read_only=True)
    occupied_beds = serializers.ReadOnlyField()
    vacant_beds = serializers.ReadOnlyField()
    
    class Meta:
        model = PGRoom
        fields = [
            'id', 'unit', 'room_number', 'sharing_type',
            'beds', 'occupied_beds', 'vacant_beds', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class UnitSerializer(serializers.ModelSerializer):
    """Serializer for Unit"""
    pg_rooms = PGRoomSerializer(many=True, read_only=True, source='pg_rooms')
    
    class Meta:
        model = Unit
        fields = [
            'id', 'account', 'building', 'unit_number', 'unit_type',
            'bhk_type', 'expected_rent', 'deposit', 'status',
            'pg_rooms', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'account', 'created_at', 'updated_at']


class UnitListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list view"""
    building_name = serializers.CharField(source='building.name', read_only=True)
    
    class Meta:
        model = Unit
        fields = [
            'id', 'building_name', 'unit_number', 'unit_type',
            'bhk_type', 'expected_rent', 'status'
        ]


class PGRoomListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for PGRoom list"""
    unit_number = serializers.CharField(source='unit.unit_number', read_only=True)
    occupied_beds = serializers.ReadOnlyField()
    vacant_beds = serializers.ReadOnlyField()
    
    class Meta:
        model = PGRoom
        fields = ['id', 'unit_number', 'room_number', 'sharing_type', 'occupied_beds', 'vacant_beds']


class BedListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for Bed list"""
    room_number = serializers.CharField(source='room.room_number', read_only=True)
    unit_number = serializers.CharField(source='room.unit.unit_number', read_only=True)
    
    class Meta:
        model = Bed
        fields = ['id', 'unit_number', 'room_number', 'bed_number', 'status']

