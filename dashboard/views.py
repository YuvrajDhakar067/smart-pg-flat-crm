"""
Role-Aware Dashboard API

Returns dashboard metrics filtered by user access:
- OWNER: Sees data for ALL buildings in their account
- MANAGER: Sees data ONLY for buildings assigned to them

SECURITY: All filtering happens in backend queries (no frontend filtering)
"""

from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from decimal import Decimal

from buildings.models import Building
from buildings.access import get_accessible_buildings, get_accessible_building_ids
from units.models import Unit, Bed
from tenants.models import Tenant
from occupancy.models import Occupancy
from rent.models import Rent
from issues.models import Issue


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_metrics(request):
    """
    Get dashboard metrics filtered by user's accessible buildings.
    
    Returns:
        JSON with dashboard metrics for accessible buildings only
    
    Security:
        - OWNER: All buildings in account
        - MANAGER: Only assigned buildings
        - All filtering done in backend queries
    """
    user = request.user
    
    # Validate user has account
    if not hasattr(user, 'account') or not user.account:
        return Response(
            {'detail': 'User account not found'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get accessible buildings based on user role
    accessible_buildings = get_accessible_buildings(user)
    accessible_building_ids = get_accessible_building_ids(user)
    
    # If no accessible buildings, return empty metrics
    if not accessible_building_ids:
        return Response({
            'total_buildings': 0,
            'total_units': 0,
            'occupied_units': 0,
            'vacant_units': 0,
            'occupancy_rate': 0.0,
            'total_tenants': 0,
            'active_tenants': 0,
            'expected_monthly_rent': 0,
            'collected_monthly_rent': 0,
            'pending_rent': 0,
            'collection_rate': 0.0,
            'open_issues': 0,
            'urgent_issues': 0,
            'user_role': user.role,
            'accessible_buildings_count': 0
        })
    
    # Calculate metrics with proper filtering
    current_month = timezone.now().date().replace(day=1)
    
    # 1. Building metrics
    total_buildings = accessible_buildings.count()
    
    # 2. Unit metrics (filtered by accessible buildings)
    unit_stats = Unit.objects.filter(
        account=user.account,
        building_id__in=accessible_building_ids
    ).aggregate(
        total=Count('id'),
        occupied=Count('id', filter=Q(status='OCCUPIED')),
        vacant=Count('id', filter=Q(status='VACANT'))
    )
    
    total_units = unit_stats['total'] or 0
    occupied_units = unit_stats['occupied'] or 0
    vacant_units = unit_stats['vacant'] or 0
    occupancy_rate = (occupied_units / total_units * 100) if total_units > 0 else 0.0
    
    # 3. Tenant metrics (filtered by accessible buildings via occupancy)
    total_tenants = Tenant.objects.filter(account=user.account).count()
    
    # Active tenants in accessible buildings
    active_tenants = Occupancy.objects.filter(
        tenant__account=user.account,
        is_active=True
    ).filter(
        Q(unit__building_id__in=accessible_building_ids) |
        Q(bed__room__unit__building_id__in=accessible_building_ids)
    ).values('tenant').distinct().count()
    
    # 4. Rent metrics (filtered by accessible buildings)
    expected_monthly_rent = Unit.objects.filter(
        account=user.account,
        building_id__in=accessible_building_ids,
        status='OCCUPIED'
    ).aggregate(total=Sum('expected_rent'))['total'] or Decimal('0')
    
    # Collected rent this month (filtered by accessible buildings)
    collected_monthly_rent = Rent.objects.filter(
        occupancy__tenant__account=user.account,
        month=current_month,
        status__in=['PAID', 'PARTIAL']
    ).filter(
        Q(occupancy__unit__building_id__in=accessible_building_ids) |
        Q(occupancy__bed__room__unit__building_id__in=accessible_building_ids)
    ).aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')
    
    pending_rent = expected_monthly_rent - collected_monthly_rent
    collection_rate = (collected_monthly_rent / expected_monthly_rent * 100) if expected_monthly_rent > 0 else 0.0
    
    # 5. Issue metrics (filtered by accessible buildings)
    open_issues = Issue.objects.filter(
        unit__account=user.account,
        unit__building_id__in=accessible_building_ids,
        status__in=['OPEN', 'ASSIGNED', 'IN_PROGRESS']
    ).count()
    
    urgent_issues = Issue.objects.filter(
        unit__account=user.account,
        unit__building_id__in=accessible_building_ids,
        status__in=['OPEN', 'IN_PROGRESS'],
        priority='URGENT'
    ).count()
    
    # Return metrics
    return Response({
        # Building metrics
        'total_buildings': total_buildings,
        
        # Unit metrics
        'total_units': total_units,
        'occupied_units': occupied_units,
        'vacant_units': vacant_units,
        'occupancy_rate': round(occupancy_rate, 1),
        
        # Tenant metrics
        'total_tenants': total_tenants,
        'active_tenants': active_tenants,
        
        # Rent metrics
        'expected_monthly_rent': float(expected_monthly_rent),
        'collected_monthly_rent': float(collected_monthly_rent),
        'pending_rent': float(pending_rent),
        'collection_rate': round(collection_rate, 1),
        
        # Issue metrics
        'open_issues': open_issues,
        'urgent_issues': urgent_issues,
        
        # Metadata
        'user_role': user.role,
        'accessible_buildings_count': len(accessible_building_ids),
        'current_month': current_month.strftime('%Y-%m')
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_detailed_metrics(request):
    """
    Get detailed dashboard metrics with breakdown by building.
    
    Returns detailed metrics for each accessible building.
    """
    user = request.user
    
    if not hasattr(user, 'account') or not user.account:
        return Response(
            {'detail': 'User account not found'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get accessible buildings
    accessible_buildings = get_accessible_buildings(user)
    accessible_building_ids = get_accessible_building_ids(user)
    
    if not accessible_building_ids:
        return Response({
            'buildings': [],
            'summary': {
                'total_buildings': 0,
                'total_expected_rent': 0,
                'total_collected_rent': 0
            }
        })
    
    current_month = timezone.now().date().replace(day=1)
    
    # Get building-level metrics
    building_metrics = []
    
    for building in accessible_buildings:
        # Unit stats for this building
        unit_stats = Unit.objects.filter(building=building).aggregate(
            total=Count('id'),
            occupied=Count('id', filter=Q(status='OCCUPIED')),
            vacant=Count('id', filter=Q(status='VACANT'))
        )
        
        # Expected rent for this building
        expected_rent = Unit.objects.filter(
            building=building,
            status='OCCUPIED'
        ).aggregate(total=Sum('expected_rent'))['total'] or Decimal('0')
        
        # Collected rent for this building this month
        collected_rent = Rent.objects.filter(
            month=current_month,
            status__in=['PAID', 'PARTIAL']
        ).filter(
            Q(occupancy__unit__building=building) |
            Q(occupancy__bed__room__unit__building=building)
        ).aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')
        
        # Issues for this building
        open_issues = Issue.objects.filter(
            unit__building=building,
            status__in=['OPEN', 'ASSIGNED', 'IN_PROGRESS']
        ).count()
        
        building_metrics.append({
            'building_id': building.id,
            'building_name': building.name,
            'total_units': unit_stats['total'] or 0,
            'occupied_units': unit_stats['occupied'] or 0,
            'vacant_units': unit_stats['vacant'] or 0,
            'expected_rent': float(expected_rent),
            'collected_rent': float(collected_rent),
            'collection_rate': (collected_rent / expected_rent * 100) if expected_rent > 0 else 0.0,
            'open_issues': open_issues
        })
    
    # Calculate summary
    total_expected = sum(b['expected_rent'] for b in building_metrics)
    total_collected = sum(b['collected_rent'] for b in building_metrics)
    
    return Response({
        'buildings': building_metrics,
        'summary': {
            'total_buildings': len(building_metrics),
            'total_expected_rent': total_expected,
            'total_collected_rent': total_collected,
            'overall_collection_rate': (total_collected / total_expected * 100) if total_expected > 0 else 0.0
        },
        'user_role': user.role,
        'current_month': current_month.strftime('%Y-%m')
    })


class DashboardViewSet(viewsets.ViewSet):
    """
    ViewSet for dashboard operations with role-aware filtering.
    
    All endpoints automatically filter by user's accessible buildings.
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get dashboard summary metrics"""
        return dashboard_metrics(request)
    
    @action(detail=False, methods=['get'])
    def detailed(self, request):
        """Get detailed building-level metrics"""
        return dashboard_detailed_metrics(request)
    
    @action(detail=False, methods=['get'])
    def recent_activity(self, request):
        """Get recent activity (issues, tenants, rent) for accessible buildings"""
        user = request.user
        
        if not hasattr(user, 'account') or not user.account:
            return Response({'detail': 'User account not found'}, status=400)
        
        accessible_building_ids = get_accessible_building_ids(user)
        
        # Recent issues (last 10)
        recent_issues = Issue.objects.filter(
            unit__account=user.account,
            unit__building_id__in=accessible_building_ids
        ).select_related('unit', 'unit__building').order_by('-raised_date')[:10]
        
        # Recent tenants (last 10)
        recent_tenants = Occupancy.objects.filter(
            tenant__account=user.account,
            is_active=True
        ).filter(
            Q(unit__building_id__in=accessible_building_ids) |
            Q(bed__room__unit__building_id__in=accessible_building_ids)
        ).select_related('tenant', 'unit', 'unit__building').order_by('-start_date')[:10]
        
        # Recent rent payments (last 10)
        recent_payments = Rent.objects.filter(
            occupancy__tenant__account=user.account,
            status__in=['PAID', 'PARTIAL']
        ).filter(
            Q(occupancy__unit__building_id__in=accessible_building_ids) |
            Q(occupancy__bed__room__unit__building_id__in=accessible_building_ids)
        ).select_related('occupancy', 'occupancy__tenant').order_by('-paid_date')[:10]
        
        return Response({
            'recent_issues': [{
                'id': issue.id,
                'title': issue.title,
                'status': issue.status,
                'priority': issue.priority,
                'building': issue.unit.building.name,
                'unit': issue.unit.unit_number,
                'raised_date': issue.raised_date
            } for issue in recent_issues],
            'recent_tenants': [{
                'id': occ.id,
                'tenant_name': occ.tenant.name,
                'building': occ.unit.building.name if occ.unit else occ.bed.room.unit.building.name,
                'unit': occ.unit.unit_number if occ.unit else f"{occ.bed.room.unit.unit_number}-{occ.bed.bed_number}",
                'start_date': occ.start_date,
                'rent': float(occ.rent)
            } for occ in recent_tenants],
            'recent_payments': [{
                'id': rent.id,
                'tenant_name': rent.occupancy.tenant.name,
                'amount': float(rent.paid_amount),
                'month': rent.month.strftime('%Y-%m'),
                'paid_date': rent.paid_date
            } for rent in recent_payments if rent.paid_date]
        })
