from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from .models import Unit, PGRoom, Bed
from .serializers import (
    UnitSerializer, UnitListSerializer,
    PGRoomSerializer, PGRoomListSerializer,
    BedSerializer, BedListSerializer
)
from api.permissions import IsAccountOwner, IsOwnerOrManager
from api.filters import AccountFilterBackend


class UnitViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Unit management
    Supports both Flats and PGs
    Uses atomic transactions for data consistency
    """
    permission_classes = [IsAuthenticated, IsOwnerOrManager]
    filter_backends = [AccountFilterBackend]
    search_fields = ['unit_number', 'building__name']
    ordering_fields = ['unit_number', 'expected_rent']
    ordering = ['unit_number']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return UnitListSerializer
        return UnitSerializer
    
    def get_queryset(self):
        """
        Filter units by user's account AND building-level permissions.
        
        - OWNER: All units in all buildings in their account
        - MANAGER: Only units in buildings they have access to
        """
        from buildings.access import filter_by_accessible_buildings
        
        # Start with account-level isolation
        queryset = Unit.objects.filter(account=self.request.user.account)
        
        # Apply building-level access control
        queryset = filter_by_accessible_buildings(queryset, self.request.user, 'building')
        
        # Filter by building if provided
        building_id = self.request.query_params.get('building', None)
        if building_id:
            queryset = queryset.filter(building_id=building_id)
        
        # Filter by unit type
        unit_type = self.request.query_params.get('unit_type', None)
        if unit_type:
            queryset = queryset.filter(unit_type=unit_type)
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create unit with atomic transaction"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(account=request.user.account)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Update unit with atomic transaction and row-level locking"""
        unit = Unit.objects.select_for_update().filter(
            id=kwargs.get('pk'),
            account=request.user.account
        ).first()
        
        if not unit:
            return Response(
                {'detail': 'Unit not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(unit, data=request.data, partial=kwargs.get('partial', False))
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    
    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        """Handle PATCH requests with concurrency control"""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    def perform_create(self, serializer):
        """Auto-assign account when creating unit"""
        serializer.save(account=self.request.user.account)
    
    def retrieve(self, request, *args, **kwargs):
        """Get single unit with access control check"""
        from buildings.access import can_access_building
        
        unit = self.get_object()
        
        # Verify user has access to this unit's building
        if not can_access_building(request.user, unit.building):
            return Response(
                {'detail': 'You do not have permission to access this unit.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(unit)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def occupancy(self, request, pk=None):
        """Get current occupancy for this unit with access control"""
        from buildings.access import can_access_building
        
        unit = self.get_object()
        
        # Verify user has access to this unit's building
        if not can_access_building(request.user, unit.building):
            return Response(
                {'detail': 'You do not have permission to access this unit.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        from occupancy.serializers import OccupancySerializer
        from occupancy.models import Occupancy
        
        # OPTIMIZED: select_related for tenant and related objects
        occupancy = Occupancy.objects.filter(
            unit=unit, 
            is_active=True
        ).select_related('tenant', 'unit', 'bed', 'bed__room').first()
        if occupancy:
            serializer = OccupancySerializer(occupancy)
            return Response(serializer.data)
        return Response({'detail': 'No active occupancy'}, status=status.HTTP_404_NOT_FOUND)


class PGRoomViewSet(viewsets.ModelViewSet):
    """
    ViewSet for PGRoom management
    Uses atomic transactions for data consistency
    """
    permission_classes = [IsAuthenticated, IsOwnerOrManager]
    filter_backends = [AccountFilterBackend]
    search_fields = ['room_number', 'unit__unit_number']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return PGRoomListSerializer
        return PGRoomSerializer
    
    def get_queryset(self):
        """
        Filter PG rooms by user's account AND building-level permissions.
        
        - OWNER: All PG rooms in all buildings in their account
        - MANAGER: Only PG rooms in buildings they have access to
        """
        from buildings.access import filter_by_accessible_buildings
        
        # Start with account-level isolation
        queryset = PGRoom.objects.filter(unit__account=self.request.user.account)
        
        # Apply building-level access control
        queryset = filter_by_accessible_buildings(queryset, self.request.user, 'unit__building')
        
        # Filter by unit if provided
        unit_id = self.request.query_params.get('unit', None)
        if unit_id:
            queryset = queryset.filter(unit_id=unit_id)
        
        # OPTIMIZED: select_related for unit and account
        return queryset.select_related('unit', 'unit__account', 'unit__building')
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create PG room with atomic transaction"""
        return super().create(request, *args, **kwargs)
    
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Update PG room with atomic transaction and row-level locking"""
        room = PGRoom.objects.select_for_update().filter(
            id=kwargs.get('pk'),
            unit__account=request.user.account
        ).first()
        
        if not room:
            return Response(
                {'detail': 'PG room not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(room, data=request.data, partial=kwargs.get('partial', False))
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    
    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        """Handle PATCH requests with concurrency control"""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)


class BedViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Bed management
    Uses atomic transactions and row-level locking for data consistency
    """
    permission_classes = [IsAuthenticated, IsOwnerOrManager]
    filter_backends = [AccountFilterBackend]
    search_fields = ['bed_number', 'room__room_number']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return BedListSerializer
        return BedSerializer
    
    def get_queryset(self):
        """
        Filter beds by user's account AND building-level permissions - OPTIMIZED
        
        - OWNER: All beds in all buildings in their account
        - MANAGER: Only beds in buildings they have access to
        """
        from buildings.access import filter_by_accessible_buildings
        
        # Start with account-level isolation
        queryset = Bed.objects.filter(room__unit__account=self.request.user.account)
        
        # Apply building-level access control
        queryset = filter_by_accessible_buildings(queryset, self.request.user, 'room__unit__building')
        
        # Filter by room if provided
        room_id = self.request.query_params.get('room', None)
        if room_id:
            queryset = queryset.filter(room_id=room_id)
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # OPTIMIZED: select_related for room, unit, and account
        return queryset.select_related(
            'room', 
            'room__unit', 
            'room__unit__account',
            'room__unit__building'
        )
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create bed with atomic transaction"""
        return super().create(request, *args, **kwargs)
    
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Update bed with atomic transaction and row-level locking"""
        bed = Bed.objects.select_for_update().filter(
            id=kwargs.get('pk'),
            room__unit__account=request.user.account
        ).first()
        
        if not bed:
            return Response(
                {'detail': 'Bed not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(bed, data=request.data, partial=kwargs.get('partial', False))
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    
    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        """Handle PATCH requests with concurrency control"""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

