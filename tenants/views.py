from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from .models import Tenant
from .serializers import TenantSerializer, TenantListSerializer
from api.permissions import IsAccountOwner, IsOwnerOrManager
from api.filters import AccountFilterBackend


class TenantViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Tenant management
    Filtered by account - users can only see their account's tenants
    Uses atomic transactions for data consistency
    """
    permission_classes = [IsAuthenticated, IsOwnerOrManager]
    filter_backends = [AccountFilterBackend]
    search_fields = ['name', 'phone', 'email', 'id_proof_number']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return TenantListSerializer
        return TenantSerializer
    
    def get_queryset(self):
        """Filter tenants by user's account - OPTIMIZED"""
        # OPTIMIZED: select_related for account
        return Tenant.objects.filter(account=self.request.user.account).select_related('account')
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create tenant with atomic transaction"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(account=request.user.account)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Update tenant with atomic transaction and row-level locking"""
        tenant = Tenant.objects.select_for_update().filter(
            id=kwargs.get('pk'),
            account=request.user.account
        ).first()
        
        if not tenant:
            return Response(
                {'detail': 'Tenant not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(tenant, data=request.data, partial=kwargs.get('partial', False))
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    
    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        """Handle PATCH requests with concurrency control"""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    def perform_create(self, serializer):
        """Auto-assign account when creating tenant"""
        serializer.save(account=self.request.user.account)
    
    @action(detail=True, methods=['get'])
    def occupancy(self, request, pk=None):
        """Get current occupancy for this tenant"""
        tenant = self.get_object()
        from occupancy.serializers import OccupancySerializer
        
        # OPTIMIZED: Get occupancy with select_related
        from occupancy.models import Occupancy
        occupancy = Occupancy.objects.filter(
            tenant=tenant,
            is_active=True
        ).select_related(
            'tenant',
            'unit',
            'unit__building',
            'bed',
            'bed__room',
            'bed__room__unit'
        ).first()
        
        if occupancy:
            serializer = OccupancySerializer(occupancy)
            return Response(serializer.data)
        return Response({'detail': 'No active occupancy'}, status=status.HTTP_404_NOT_FOUND)

