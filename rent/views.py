from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Q, Count
from django.db import transaction
from django.utils import timezone
from datetime import datetime
from .models import Rent
from .serializers import RentSerializer, RentListSerializer
from api.permissions import IsAccountOwner, IsOwnerOrManager
from api.filters import AccountFilterBackend


class RentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Rent management
    Handles monthly rent tracking and payments
    Uses atomic transactions for data consistency
    """
    permission_classes = [IsAuthenticated, IsOwnerOrManager]
    filter_backends = [AccountFilterBackend]
    search_fields = ['occupancy__tenant__name', 'occupancy__unit__unit_number']
    ordering_fields = ['month', 'created_at']
    ordering = ['-month']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return RentListSerializer
        return RentSerializer
    
    def get_queryset(self):
        """
        Filter rents by user's account AND building-level permissions
        
        - OWNER: All rent records in all buildings in their account
        - MANAGER: Only rent records in buildings they have access to
        """
        from buildings.access import get_accessible_building_ids
        
        # Start with account-level isolation
        queryset = Rent.objects.filter(occupancy__tenant__account=self.request.user.account)
        
        # Apply building-level access control
        accessible_building_ids = get_accessible_building_ids(self.request.user)
        
        # Filter rent records by accessible buildings (handle both flat and PG)
        queryset = queryset.filter(
            models.Q(occupancy__unit__building_id__in=accessible_building_ids) |
            models.Q(occupancy__bed__room__unit__building_id__in=accessible_building_ids)
        )
        
        # Filter by month
        month = self.request.query_params.get('month', None)
        if month:
            try:
                month_date = datetime.strptime(month, '%Y-%m').date().replace(day=1)
                queryset = queryset.filter(month=month_date)
            except ValueError:
                pass
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # OPTIMIZED: select_related for all foreign keys
        return queryset.select_related(
            'occupancy',
            'occupancy__tenant',
            'occupancy__tenant__account',
            'occupancy__unit',
            'occupancy__unit__building',
            'occupancy__unit__account',
            'occupancy__bed',
            'occupancy__bed__room',
            'occupancy__bed__room__unit',
            'occupancy__bed__room__unit__building'
        )
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create rent record with atomic transaction"""
        return super().create(request, *args, **kwargs)
    
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Update rent record with atomic transaction and row-level locking"""
        rent = Rent.objects.select_for_update().filter(
            id=kwargs.get('pk'),
            occupancy__tenant__account=request.user.account
        ).first()
        
        if not rent:
            return Response(
                {'detail': 'Rent record not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(rent, data=request.data, partial=kwargs.get('partial', False))
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    
    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        """Handle PATCH requests with concurrency control"""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get all pending rents"""
        rents = self.get_queryset().filter(status__in=['PENDING', 'PARTIAL'])
        serializer = self.get_serializer(rents, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        """
        Pay rent - update paid_amount
        Auto-updates status (PAID/PENDING/PARTIAL)
        Uses row-level locking to prevent race conditions during concurrent payments
        """
        from django.db import transaction
        
        paid_amount = request.data.get('paid_amount', None)
        
        if paid_amount is None:
            return Response(
                {'detail': 'paid_amount is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            paid_amount = float(paid_amount)
            if paid_amount < 0:
                raise ValueError
        except (ValueError, TypeError):
            return Response(
                {'detail': 'paid_amount must be a positive number'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Use atomic transaction with row-level locking
        try:
            with transaction.atomic():
                # Lock the rent row to prevent concurrent updates
                rent = Rent.objects.select_for_update().filter(id=pk).first()
                
                if not rent:
                    return Response(
                        {'detail': 'Rent record not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                # Verify user has permission
                if rent.occupancy.tenant.account != request.user.account:
                    return Response(
                        {'detail': 'You do not have permission to modify this rent record'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                # Update paid amount
                rent.paid_amount += paid_amount
                
                # Clamp to amount (can't pay more than due)
                if rent.paid_amount > rent.amount:
                    rent.paid_amount = rent.amount
                
                rent.save()  # Auto-updates status
                
                serializer = self.get_serializer(rent)
                return Response(serializer.data)
                
        except Exception as e:
            return Response(
                {'detail': f'Error processing payment: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get rent summary for current month - OPTIMIZED"""
        current_month = timezone.now().replace(day=1)
        rents = self.get_queryset().filter(month=current_month)
        
        # OPTIMIZED: Single aggregation query for all stats
        stats = rents.aggregate(
            total_expected=Sum('amount'),
            total_paid=Sum('paid_amount'),
            pending_count=Count('id', filter=Q(status__in=['PENDING', 'PARTIAL'])),
            paid_count=Count('id', filter=Q(status='PAID'))
        )
        
        total_expected = stats['total_expected'] or 0
        total_paid = stats['total_paid'] or 0
        total_pending = total_expected - total_paid
        
        return Response({
            'month': current_month.strftime('%Y-%m'),
            'total_expected': total_expected,
            'total_paid': total_paid,
            'total_pending': total_pending,
            'pending_count': stats['pending_count'],
            'paid_count': stats['paid_count'],
        })

