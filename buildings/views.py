from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from .models import Building, BuildingAccess
from .serializers import BuildingSerializer, BuildingListSerializer
from api.permissions import IsAccountOwner, IsOwnerOrManager
from api.filters import AccountFilterBackend


class BuildingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Building management
    
    Access Control:
    - Account-level isolation: Users only see buildings in their account
    - Building-level permissions:
      - OWNER: Can access ALL buildings in their account
      - MANAGER: Can only access buildings explicitly granted via BuildingAccess
    
    Uses atomic transactions for data consistency
    """
    permission_classes = [IsAuthenticated, IsOwnerOrManager]
    filter_backends = [AccountFilterBackend]
    search_fields = ['name', 'address']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_serializer_class(self):
        """Use list serializer for list view"""
        if self.action == 'list':
            return BuildingListSerializer
        return BuildingSerializer
    
    def get_queryset(self):
        """
        Filter buildings by user's account AND building-level permissions.
        
        - OWNER: All buildings in account
        - MANAGER: Only buildings granted access via BuildingAccess
        """
        from .access import get_accessible_buildings
        
        # Get buildings user has access to (handles both OWNER and MANAGER roles)
        return get_accessible_buildings(self.request.user).select_related('account')
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create building with atomic transaction"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(account=request.user.account)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Update building with atomic transaction and row-level locking"""
        building = Building.objects.select_for_update().filter(
            id=kwargs.get('pk'),
            account=request.user.account
        ).first()
        
        if not building:
            return Response(
                {'detail': 'Building not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(building, data=request.data, partial=kwargs.get('partial', False))
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    
    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        """Handle PATCH requests with concurrency control"""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    def perform_create(self, serializer):
        """Auto-assign account when creating building"""
        serializer.save(account=self.request.user.account)
    
    def retrieve(self, request, *args, **kwargs):
        """Get single building with access control check"""
        from .access import can_access_building
        
        building = self.get_object()
        
        # Verify user has access to this building
        if not can_access_building(request.user, building):
            return Response(
                {'detail': 'You do not have permission to access this building.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(building)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def units(self, request, pk=None):
        """Get all units for this building with access control"""
        from .access import can_access_building
        
        building = self.get_object()
        
        # Verify user has access to this building
        if not can_access_building(request.user, building):
            return Response(
                {'detail': 'You do not have permission to access this building.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        from units.serializers import UnitListSerializer
        from units.models import Unit
        
        # OPTIMIZED: select_related for building and account
        units = Unit.objects.filter(
            building=building, 
            account=request.user.account
        ).select_related('building', 'account')
        serializer = UnitListSerializer(units, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], url_path='grant-access')
    def grant_access(self, request, pk=None):
        """
        Grant building access to a manager (OWNER only).
        
        Body: { "manager_id": <user_id> }
        """
        # Only owners can grant access
        if request.user.role != 'OWNER':
            return Response(
                {'detail': 'Only owners can grant building access.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        building = self.get_object()
        manager_id = request.data.get('manager_id')
        
        if not manager_id:
            return Response(
                {'detail': 'manager_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get the manager
        from users.models import User
        try:
            manager = User.objects.get(
                id=manager_id,
                account=request.user.account,
                role='MANAGER'
            )
        except User.DoesNotExist:
            return Response(
                {'detail': 'Manager not found in your account'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Create or get existing access
        access, created = BuildingAccess.objects.get_or_create(
            user=manager,
            building=building,
            defaults={'created_by': request.user}
        )
        
        if created:
            return Response({
                'detail': f'Access granted to {manager.username} for {building.name}',
                'access_id': access.id
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'detail': f'{manager.username} already has access to {building.name}',
                'access_id': access.id
            }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], url_path='revoke-access')
    def revoke_access(self, request, pk=None):
        """
        Revoke building access from a manager (OWNER only).
        
        Body: { "manager_id": <user_id> }
        """
        # Only owners can revoke access
        if request.user.role != 'OWNER':
            return Response(
                {'detail': 'Only owners can revoke building access.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        building = self.get_object()
        manager_id = request.data.get('manager_id')
        
        if not manager_id:
            return Response(
                {'detail': 'manager_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Delete the access
        deleted_count, _ = BuildingAccess.objects.filter(
            user_id=manager_id,
            building=building,
            user__account=request.user.account
        ).delete()
        
        if deleted_count > 0:
            return Response({
                'detail': f'Access revoked successfully'
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'detail': 'No access found to revoke'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['get'], url_path='access-list')
    def access_list(self, request, pk=None):
        """
        List all managers who have access to this building (OWNER only).
        """
        # Only owners can view access list
        if request.user.role != 'OWNER':
            return Response(
                {'detail': 'Only owners can view building access list.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        building = self.get_object()
        
        # Get all access grants for this building
        accesses = BuildingAccess.objects.filter(
            building=building
        ).select_related('user', 'created_by')
        
        access_data = [{
            'id': access.id,
            'manager_id': access.user.id,
            'manager_username': access.user.username,
            'manager_email': access.user.email,
            'granted_at': access.created_at,
            'granted_by': access.created_by.username if access.created_by else None
        } for access in accesses]
        
        return Response({
            'building_id': building.id,
            'building_name': building.name,
            'managers_with_access': access_data,
            'count': len(access_data)
        })

