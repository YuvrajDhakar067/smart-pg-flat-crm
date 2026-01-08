from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db import models
from .models import Occupancy
from .serializers import OccupancySerializer, OccupancyListSerializer
from api.permissions import IsAccountOwner, IsOwnerOrManager
from api.filters import AccountFilterBackend


class OccupancyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Occupancy management
    MOST IMPORTANT - Handles tenant assignment to units/beds
    """
    permission_classes = [IsAuthenticated, IsOwnerOrManager]
    filter_backends = [AccountFilterBackend]
    search_fields = ['tenant__name', 'unit__unit_number']
    ordering_fields = ['start_date', 'created_at']
    ordering = ['-start_date']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return OccupancyListSerializer
        return OccupancySerializer
    
    def get_queryset(self):
        """
        Filter occupancies by user's account AND building-level permissions - OPTIMIZED
        
        - OWNER: All occupancies in all buildings in their account
        - MANAGER: Only occupancies in buildings they have access to
        """
        from buildings.access import get_accessible_building_ids
        
        # Start with account-level isolation
        queryset = Occupancy.objects.filter(tenant__account=self.request.user.account)
        
        # Apply building-level access control
        accessible_building_ids = get_accessible_building_ids(self.request.user)
        
        # Filter occupancies by accessible buildings (handle both flat and PG)
        queryset = queryset.filter(
            models.Q(unit__building_id__in=accessible_building_ids) |
            models.Q(bed__room__unit__building_id__in=accessible_building_ids)
        )
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            is_active = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active)
        
        # OPTIMIZED: select_related for all foreign keys
        return queryset.select_related(
            'tenant',
            'tenant__account',
            'unit',
            'unit__building',
            'unit__account',
            'bed',
            'bed__room',
            'bed__room__unit',
            'bed__room__unit__building',
            'bed__room__unit__account'
        )
    
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """
        Update occupancy (e.g., reassign tenant to different unit/bed)
        Uses row-level locking to prevent race conditions
        """
        from units.models import Unit, Bed
        
        # Lock the existing occupancy
        occupancy = Occupancy.objects.select_for_update().filter(id=kwargs.get('pk')).first()
        
        if not occupancy:
            return Response(
                {'detail': 'Occupancy not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verify user has permission
        if occupancy.tenant.account != request.user.account:
            return Response(
                {'detail': 'You do not have permission to modify this occupancy'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(occupancy, data=request.data, partial=kwargs.get('partial', False))
        serializer.is_valid(raise_exception=True)
        
        new_unit = serializer.validated_data.get('unit', occupancy.unit)
        new_bed = serializer.validated_data.get('bed', occupancy.bed)
        
        # If unit/bed is changing, lock the new unit/bed and check availability
        if new_unit and new_unit != occupancy.unit:
            # Lock the new unit
            locked_unit = Unit.objects.select_for_update().filter(id=new_unit.id).first()
            if not locked_unit:
                return Response(
                    {'detail': 'Unit not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check if new unit is already occupied
            existing = Occupancy.objects.select_for_update().filter(
                unit=locked_unit, 
                is_active=True
            ).exclude(id=occupancy.id).first()
            if existing:
                return Response(
                    {'detail': f'Unit {locked_unit.unit_number} is currently being edited or already occupied. Please retry.'},
                    status=status.HTTP_409_CONFLICT
                )
        
        if new_bed and new_bed != occupancy.bed:
            # Lock the new bed
            locked_bed = Bed.objects.select_for_update().filter(id=new_bed.id).first()
            if not locked_bed:
                return Response(
                    {'detail': 'Bed not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check if new bed is already occupied
            existing = Occupancy.objects.select_for_update().filter(
                bed=locked_bed, 
                is_active=True
            ).exclude(id=occupancy.id).first()
            if existing:
                return Response(
                    {'detail': f'Bed {locked_bed.bed_number} is currently being edited or already occupied. Please retry.'},
                    status=status.HTTP_409_CONFLICT
                )
        
        # Save the updated occupancy
        serializer.save()
        
        return Response(serializer.data)
    
    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        """Handle PATCH requests with concurrency control"""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create occupancy and update unit/bed status
        Prevents double booking using row-level locking
        """
        from units.models import Unit, Bed
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        unit = serializer.validated_data.get('unit')
        bed = serializer.validated_data.get('bed')
        
        # Lock the unit or bed row to prevent race conditions
        if unit:
            # Lock the unit row for update
            locked_unit = Unit.objects.select_for_update().filter(id=unit.id).first()
            if not locked_unit:
                return Response(
                    {'detail': 'Unit not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check for existing active occupancy with locking
            existing = Occupancy.objects.select_for_update().filter(
                unit=locked_unit, 
                is_active=True
            ).first()
            if existing:
                return Response(
                    {'detail': f'Unit {locked_unit.unit_number} is currently being edited or already occupied. Please retry.'},
                    status=status.HTTP_409_CONFLICT
                )
                
        elif bed:
            # Lock the bed row for update
            locked_bed = Bed.objects.select_for_update().filter(id=bed.id).first()
            if not locked_bed:
                return Response(
                    {'detail': 'Bed not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check for existing active occupancy with locking
            existing = Occupancy.objects.select_for_update().filter(
                bed=locked_bed, 
                is_active=True
            ).first()
            if existing:
                return Response(
                    {'detail': f'Bed {locked_bed.bed_number} is currently being edited or already occupied. Please retry.'},
                    status=status.HTTP_409_CONFLICT
                )
        
        # Create occupancy
        occupancy = serializer.save()
        
        # Update unit/bed status (handled by model save)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def vacate(self, request, pk=None):
        """
        Vacate occupancy - set end_date and is_active=False
        Updates unit/bed status to VACANT
        Uses row-level locking to prevent concurrent modifications
        """
        # Lock the occupancy row
        occupancy = Occupancy.objects.select_for_update().filter(id=pk).first()
        
        if not occupancy:
            return Response(
                {'detail': 'Occupancy not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verify user has permission to access this occupancy
        if occupancy.tenant.account != request.user.account:
            return Response(
                {'detail': 'You do not have permission to modify this occupancy'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if not occupancy.is_active:
            return Response(
                {'detail': 'Occupancy is already inactive'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from django.utils import timezone
        occupancy.end_date = timezone.now().date()
        occupancy.is_active = False
        occupancy.save()
        
        serializer = self.get_serializer(occupancy)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get all active occupancies"""
        occupancies = self.get_queryset().filter(is_active=True)
        serializer = self.get_serializer(occupancies, many=True)
        return Response(serializer.data)

