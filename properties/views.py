from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Sum, Count, Q, Avg, Prefetch
from django.utils import timezone
from django.http import Http404
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.contrib import messages
from datetime import datetime, timedelta
from decimal import Decimal
import functools
import logging
from buildings.models import Building
from units.models import Unit, PGRoom, Bed
from tenants.models import Tenant
from rent.models import Rent
from issues.models import Issue
from occupancy.models import Occupancy
from common.utils import get_site_settings, validate_account_access
from common.decorators import owner_or_manager_required, handle_errors
from audit.helpers import get_client_ip
from .forms import (
    BuildingForm, UnitForm,
    TenantForm, OccupancyForm, RentForm, IssueForm
)

logger = logging.getLogger(__name__)


def owner_required(view_func):
    """Decorator to require OWNER role"""
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not hasattr(request.user, 'role') or request.user.role != 'OWNER':
            messages.error(request, 'Only owners can perform this action.')
            return redirect('properties:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
@owner_or_manager_required
@handle_errors
def dashboard(request):
    """Owner/Manager Dashboard - Enhanced with more visibility - OPTIMIZED QUERIES"""
    account = getattr(request, 'account', None)
    if not account:
        # Get account from user if not set by middleware
        if hasattr(request.user, 'account') and request.user.account:
            account = request.user.account
            request.account = account
        else:
            from django.contrib import messages
            messages.warning(request, 'Your account is not properly configured.')
            return redirect('accounts:profile')
    
    try:
        from buildings.access import get_accessible_buildings, get_accessible_building_ids
        
        current_month = timezone.now().date().replace(day=1)
        last_month = (current_month - timedelta(days=1)).replace(day=1)
        
        # Get accessible buildings for this user (OWNER sees all, MANAGER sees only granted)
        accessible_buildings = get_accessible_buildings(request.user)
        accessible_building_ids = get_accessible_building_ids(request.user)
        
        # OPTIMIZED: Use values_list for counts and aggregations - filtered by accessible buildings
        total_buildings = accessible_buildings.count()
        
        # OPTIMIZED: Single query with aggregation for unit counts - filtered by accessible buildings
        unit_stats = Unit.objects.filter(
            account=account,
            building_id__in=accessible_building_ids
        ).aggregate(
            total=Count('id'),
            occupied=Count('id', filter=Q(status='OCCUPIED')),
            vacant=Count('id', filter=Q(status='VACANT')),
            pg_count=Count('id', filter=Q(unit_type='PG')),
            flat_count=Count('id', filter=Q(unit_type='FLAT')),
            occupied_flats=Count('id', filter=Q(unit_type='FLAT', status='OCCUPIED')),
            vacant_flats=Count('id', filter=Q(unit_type='FLAT', status='VACANT')),
        )
        total_units = unit_stats['total']
        occupied_units = unit_stats['occupied']
        vacant_units = unit_stats['vacant']
        total_flats = unit_stats['flat_count']
        occupied_flats = unit_stats['occupied_flats']
        vacant_flats = unit_stats['vacant_flats']
        
        # OPTIMIZED: Use values_list for expected rent calculation - filtered by accessible buildings
        monthly_expected_rent = Unit.objects.filter(
            account=account,
            building_id__in=accessible_building_ids,
            status='OCCUPIED'
        ).aggregate(total=Sum('expected_rent'))['total'] or Decimal('0')
        
        # OPTIMIZED: Use values_list for vacancy loss - filtered by accessible buildings
        # Flat vacancy loss (vacant units)
        flat_vacancy_loss = Unit.objects.filter(
            account=account,
            building_id__in=accessible_building_ids,
            status='VACANT',
            unit_type='FLAT'
        ).aggregate(total=Sum('expected_rent'))['total'] or Decimal('0')
        
        # OPTIMIZED: PG metrics with single aggregation - filtered by accessible buildings
        pg_stats = PGRoom.objects.filter(
            unit__account=account,
            unit__building_id__in=accessible_building_ids
        ).aggregate(
            total_rooms=Count('id'),
            total_beds=Count('beds'),
            occupied_beds=Count('beds', filter=Q(beds__status='OCCUPIED')),
            vacant_beds=Count('beds', filter=Q(beds__status='VACANT'))
        )
        total_pg_rooms = pg_stats['total_rooms'] or 0
        total_beds = Bed.objects.filter(
            room__unit__account=account,
            room__unit__building_id__in=accessible_building_ids
        ).count()
        occupied_beds = Bed.objects.filter(
            room__unit__account=account,
            room__unit__building_id__in=accessible_building_ids,
            status='OCCUPIED'
        ).count()
        vacant_beds = Bed.objects.filter(
            room__unit__account=account,
            room__unit__building_id__in=accessible_building_ids,
            status='VACANT'
        ).count()
        
        # Calculate bed vacancy loss (estimate based on average bed rent from active occupancies)
        # Get average rent from active PG occupancies
        avg_bed_rent = Occupancy.objects.filter(
            tenant__account=account,
            bed__room__unit__building_id__in=accessible_building_ids,
            is_active=True,
            rent__gt=0
        ).aggregate(avg=Avg('rent'))['avg'] or Decimal('5000')  # Default ₹5000 if no data
        
        bed_vacancy_loss = Decimal(str(avg_bed_rent)) * vacant_beds
        
        # Total vacancy loss (flats + beds)
        vacancy_loss = flat_vacancy_loss + bed_vacancy_loss
        
        # Total vacancies (vacant flats + vacant beds)
        total_vacancies = vacant_flats + vacant_beds
        
        # ========== RENT CALCULATION (Consistent Methodology) ==========
        # Expected Rent = What should be collected based on occupied units/beds
        # Collected Rent = What has actually been paid (from Rent records)
        # Pending Rent = Expected - Collected
        
        # 1. Calculate EXPECTED RENT from active occupancies
        # For FLATS: Use unit's expected_rent (one rent per flat)
        # For PG: Use sum of bed occupancy rents
        
        # Get expected rent from FLAT occupancies (use unit's expected_rent, not occupancy.rent)
        flat_expected = Unit.objects.filter(
            account=account,
            building_id__in=accessible_building_ids,
            unit_type='FLAT',
            status='OCCUPIED'
        ).aggregate(total=Sum('expected_rent'))['total'] or Decimal('0')
        
        # Get expected rent from PG BED occupancies (sum of each bed's rent)
        pg_expected = Occupancy.objects.filter(
            tenant__account=account,
            bed__room__unit__building_id__in=accessible_building_ids,
            is_active=True
        ).aggregate(total=Sum('rent'))['total'] or Decimal('0')
        
        # Total expected rent per month
        rent_expected = flat_expected + pg_expected
        
        # 2. Calculate COLLECTED RENT from Rent records for current month
        rent_collected = Rent.objects.filter(
            month=current_month
        ).filter(
            Q(occupancy__unit__account=account, occupancy__unit__building_id__in=accessible_building_ids) |
            Q(occupancy__bed__room__unit__account=account, occupancy__bed__room__unit__building_id__in=accessible_building_ids)
        ).aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')
        
        # 3. Calculate PENDING RENT
        rent_pending = max(Decimal('0'), rent_expected - rent_collected)
        
        # Collection rate
        collection_rate = (rent_collected / rent_expected * 100) if rent_expected > 0 else 0
        
        # Last month comparison
        last_month_collected = Rent.objects.filter(
            month=last_month
        ).filter(
            Q(occupancy__unit__account=account, occupancy__unit__building_id__in=accessible_building_ids) |
            Q(occupancy__bed__room__unit__account=account, occupancy__bed__room__unit__building_id__in=accessible_building_ids)
        ).aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')
        
        revenue_change = rent_collected - last_month_collected
        revenue_change_percent = ((rent_collected - last_month_collected) / last_month_collected * 100) if last_month_collected > 0 else 0
        occupancy_rate = (occupied_units / total_units * 100) if total_units > 0 else 0
        
        # OPTIMIZED: Issues with select_related (use count() for efficiency) - filtered by accessible buildings
        open_issues = Issue.objects.filter(
            unit__account=account,
            unit__building_id__in=accessible_building_ids,
            status__in=['OPEN', 'IN_PROGRESS', 'ASSIGNED']
        ).count()
        
        urgent_issues = Issue.objects.filter(
            unit__account=account,
            unit__building_id__in=accessible_building_ids,
            status__in=['OPEN', 'IN_PROGRESS'],
            priority='URGENT'
        ).count()
        
        # OPTIMIZED: Fetch recent issues - completely avoid Issue queryset evaluation to prevent FieldError
        # The error "Field Issue.tenant cannot be both deferred and traversed using select_related"
        # occurs because tenant is nullable and Django has issues with select_related on nullable FKs
        # Solution: Fetch issue IDs first, then get unit/building data separately to avoid any queryset conflicts
        # This approach uses only values_list and values() - no model instances, no select_related, no deferred fields
        recent_issues = []
        try:
            # Step 1: Get issue IDs only (no relationships, no deferred fields, no select_related)
            # Using values_list with flat=True ensures we only get IDs, no queryset evaluation issues
            # Filtered by accessible buildings
            issue_ids = list(Issue.objects.filter(
                unit__account=account,
                unit__building_id__in=accessible_building_ids
            ).values_list('id', flat=True).order_by('-raised_date')[:5])
            
            if issue_ids:
                # Step 2: Get issue basic data using values() only (no model instances)
                # This avoids any deferred field or select_related conflicts
                try:
                    issue_basic_data = {
                        issue['id']: issue for issue in Issue.objects.filter(
                            id__in=issue_ids
                        ).values('id', 'title', 'status', 'priority', 'raised_date', 'unit_id')
                    }
                except Exception as e:
                    logger.warning(f"Error fetching issue basic data: {e}")
                    issue_basic_data = {}
                
                # Step 3: Get unit data separately (no relationships to Issue)
                unit_ids = [data['unit_id'] for data in issue_basic_data.values() if data.get('unit_id')]
                unit_data = {}
                if unit_ids:
                    try:
                        unit_data = {
                            unit['id']: unit for unit in Unit.objects.filter(
                                id__in=unit_ids
                            ).values('id', 'unit_number', 'building_id')
                        }
                    except Exception as e:
                        logger.warning(f"Error fetching unit data: {e}")
                
                # Step 4: Get building data separately (no relationships to Issue or Unit)
                building_ids = [unit['building_id'] for unit in unit_data.values() if unit.get('building_id')]
                building_data = {}
                if building_ids:
                    try:
                        building_data = {
                            b['id']: b for b in Building.objects.filter(
                                id__in=building_ids
                            ).values('id', 'name')
                        }
                    except Exception as e:
                        logger.warning(f"Error fetching building data: {e}")
                
                # Step 5: Combine all data into simple objects (no model instances)
                from types import SimpleNamespace
                for issue_id in issue_ids:
                    if issue_id not in issue_basic_data:
                        continue
                    try:
                        issue_info = issue_basic_data[issue_id]
                        unit_id = issue_info.get('unit_id')
                        unit_info = unit_data.get(unit_id, {}) if unit_id else {}
                        building_id = unit_info.get('building_id')
                        building_info = building_data.get(building_id, {}) if building_id else {}
                        
                        issue_obj = SimpleNamespace(
                            id=issue_info['id'],
                            title=issue_info.get('title', 'N/A'),
                            status=issue_info.get('status', 'OPEN'),
                            priority=issue_info.get('priority', 'MEDIUM'),
                            raised_date=issue_info.get('raised_date'),
                            created_at=issue_info.get('raised_date'),  # Alias for template
                            unit_number=unit_info.get('unit_number', 'N/A'),
                            building_name=building_info.get('name', 'N/A'),
                        )
                        recent_issues.append(issue_obj)
                    except Exception as e:
                        logger.warning(f"Error creating issue object for ID {issue_id}: {e}")
                        continue
        except Exception as e:
            # Comprehensive error handling - log but don't crash
            logger.error(f"Critical error fetching recent issues: {e}", exc_info=True)
            recent_issues = []  # Return empty list to prevent template errors
        
        # OPTIMIZED: Tenant stats - Count unique tenants living in accessible buildings
        # Total residents = unique tenants with active occupancies in accessible buildings
        total_tenants = Tenant.objects.filter(
            account=account
        ).filter(
            Q(occupancies__unit__building_id__in=accessible_building_ids, occupancies__is_active=True) |
            Q(occupancies__bed__room__unit__building_id__in=accessible_building_ids, occupancies__is_active=True)
        ).distinct().count()
        
        # Active occupancies count (for reference)
        active_occupancies = Occupancy.objects.filter(
            tenant__account=account,
            is_active=True
        ).filter(
            Q(unit__building_id__in=accessible_building_ids) |
            Q(bed__room__unit__building_id__in=accessible_building_ids)
        ).count()
        
        # OPTIMIZED: Recent buildings with select_related (limit for performance)
        # Convert to list to avoid queryset evaluation issues in template
        # Filtered by accessible buildings
        recent_buildings = list(accessible_buildings.select_related('account').order_by('-created_at')[:5])
        
        # OPTIMIZED: Building performance - aggregated properly by building
        # Get expected rent per building from occupied units
        building_performance_dict = {}
        
        # Get expected rent from FLAT units
        flat_expected = Unit.objects.filter(
            building__account=account,
            building_id__in=accessible_building_ids,
            unit_type='FLAT',
            status='OCCUPIED'
        ).values('building_id').annotate(
            expected=Sum('expected_rent')
        )
        
        for item in flat_expected:
            building_id = item['building_id']
            if building_id not in building_performance_dict:
                building_performance_dict[building_id] = {'expected': Decimal('0'), 'collected': Decimal('0')}
            building_performance_dict[building_id]['expected'] += item['expected'] or Decimal('0')
        
        # Get expected rent from PG units (sum of occupied bed rents)
        pg_expected = Occupancy.objects.filter(
            tenant__account=account,
            bed__room__unit__building_id__in=accessible_building_ids,
            is_active=True
        ).values('bed__room__unit__building_id').annotate(
            expected=Sum('rent')
        )
        
        for item in pg_expected:
            building_id = item['bed__room__unit__building_id']
            if building_id not in building_performance_dict:
                building_performance_dict[building_id] = {'expected': Decimal('0'), 'collected': Decimal('0')}
            building_performance_dict[building_id]['expected'] += item['expected'] or Decimal('0')
        
        # Get collected amounts per building for current month
        # For FLAT units
        flat_collected = Rent.objects.filter(
            occupancy__unit__building__account=account,
            occupancy__unit__building_id__in=accessible_building_ids,
            month=current_month
        ).values('occupancy__unit__building_id').annotate(
            collected=Sum('paid_amount')
        )
        
        for item in flat_collected:
            building_id = item['occupancy__unit__building_id']
            if building_id in building_performance_dict:
                building_performance_dict[building_id]['collected'] += item['collected'] or Decimal('0')
        
        # For PG beds
        pg_collected = Rent.objects.filter(
            occupancy__bed__room__unit__building__account=account,
            occupancy__bed__room__unit__building_id__in=accessible_building_ids,
            month=current_month
        ).values('occupancy__bed__room__unit__building_id').annotate(
            collected=Sum('paid_amount')
        )
        
        for item in pg_collected:
            building_id = item['occupancy__bed__room__unit__building_id']
            if building_id in building_performance_dict:
                building_performance_dict[building_id]['collected'] += item['collected'] or Decimal('0')
        
        # Build the final list with building objects
        building_performance = []
        if building_performance_dict:
            buildings_dict = {b.id: b for b in Building.objects.filter(
                id__in=building_performance_dict.keys()
            ).select_related('account')}
            
            for building_id, data in building_performance_dict.items():
                if data['expected'] > 0 and building_id in buildings_dict:
                    building_performance.append({
                        'building': buildings_dict[building_id],
                        'expected': data['expected'],
                        'collected': data['collected'],
                        'rate': (data['collected'] / data['expected'] * 100) if data['expected'] > 0 else 0
                    })
        
        # Sort by collection rate (best performers first)
        building_performance.sort(key=lambda x: x['rate'], reverse=True)
        
        # Count of rent records with PENDING/PARTIAL status (for display purposes)
        pending_payments_count = Rent.objects.filter(
            occupancy__tenant__account=account,
            status__in=['PENDING', 'PARTIAL'],
            month=current_month
        ).filter(
            Q(occupancy__unit__building_id__in=accessible_building_ids) |
            Q(occupancy__bed__room__unit__building_id__in=accessible_building_ids)
        ).count()
        
        # Use the consistent rent_pending calculated earlier
        pending_rent = rent_pending
        
        # OPTIMIZED: Alerts with optimized queries - filtered by accessible buildings
        overdue_count = Rent.objects.filter(
            occupancy__tenant__account=account,
            status__in=['PENDING', 'PARTIAL'],
            month__lt=current_month
        ).filter(
            Q(occupancy__unit__building_id__in=accessible_building_ids) |
            Q(occupancy__bed__room__unit__building_id__in=accessible_building_ids)
        ).count()
        
        alerts = []
        if overdue_count > 0:
            alerts.append({
                'type': 'danger',
                'icon': 'exclamation-triangle',
                'message': f'{overdue_count} rent payment(s) overdue',
                'link': 'properties:rent_management'
            })
        if urgent_issues > 0:
            alerts.append({
                'type': 'danger',
                'icon': 'exclamation-circle',
                'message': f'{urgent_issues} urgent issue(s) need attention',
                'link': 'properties:issue_list'
            })
        if total_vacancies > 0:
            alerts.append({
                'type': 'warning',
                'icon': 'house-door',
                'message': f'{total_vacancies} vacancy(ies) - Potential loss: ₹{vacancy_loss:,.0f}/month',
                'link': 'properties:vacancy'
            })
        if collection_rate < 70 and monthly_expected_rent > 0:
            alerts.append({
                'type': 'warning',
                'icon': 'cash-coin',
                'message': f'Collection rate is {collection_rate:.1f}% - Below target',
                'link': 'properties:rent_management'
            })
        
        # Get site settings
        site_settings = get_site_settings()
        dashboard_welcome = None
        try:
            from common.models import ContentBlock
            # Avoid .only() to prevent any potential conflicts with deferred fields
            content_block = ContentBlock.objects.filter(key='dashboard_welcome', is_active=True).first()
            if content_block:
                dashboard_welcome = content_block.content
        except:
            pass
        
        context = {
            'account': account,
            'site_settings': site_settings,
            'dashboard_welcome': dashboard_welcome,
            'total_buildings': total_buildings,
            'total_units': total_units,
            'occupied_units': occupied_units,
            'vacant_units': vacant_units,
            'occupancy_rate': round(occupancy_rate, 1),
            'total_pg_rooms': total_pg_rooms,
            'total_beds': total_beds,
            'occupied_beds': occupied_beds,
            'vacant_beds': vacant_beds,
            'total_vacancies': total_vacancies,
            'flat_vacancy_loss': flat_vacancy_loss,
            'bed_vacancy_loss': bed_vacancy_loss,
            'total_flats': total_flats,
            'occupied_flats': occupied_flats,
            'vacant_flats': vacant_flats,
            'monthly_expected_rent': rent_expected,  # Use consistent metric from Rent records
            'collected_this_month': rent_collected,  # Use consistent metric from Rent records
            'collected_last_month': last_month_collected,
            'pending_rent': pending_rent,
            'pending_payments_count': pending_payments_count,
            'collection_rate': round(collection_rate, 1),
            'revenue_change': revenue_change,
            'revenue_change_percent': round(revenue_change_percent, 1),
            'open_issues': open_issues,
            'urgent_issues': urgent_issues,
            'recent_issues': recent_issues,
            'total_tenants': total_tenants,
            'active_occupancies': active_occupancies,
            'vacancy_loss': vacancy_loss,
            'recent_buildings': recent_buildings,
            'building_performance': building_performance[:5] if building_performance else [],
            'current_month': current_month,
            'alerts': alerts,
        }
        
        return render(request, 'properties/dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Error in dashboard view: {str(e)}", exc_info=True)
        from django.contrib import messages
        messages.error(request, 'An error occurred while loading the dashboard. Please try again.')
        return render(request, 'properties/dashboard.html', {
            'account': account,
            'error': True
        })


@login_required
@owner_or_manager_required
@handle_errors
def building_list(request):
    """List all buildings - OPTIMIZED with prefetch_related"""
    account = getattr(request, 'account', None)
    if not account and hasattr(request.user, 'account') and request.user.account:
        account = request.user.account
        request.account = account
    
    if not account:
        from django.contrib import messages
        messages.warning(request, 'Your account is not properly configured.')
        return redirect('accounts:profile')
    
    try:
        # Get accessible buildings for managers
        from buildings.access import get_accessible_buildings
        accessible_buildings = get_accessible_buildings(request.user)
        
        # OPTIMIZED: Prefetch units with PG rooms and beds - filter by accessible buildings
        buildings = accessible_buildings.prefetch_related(
            'units',
            'units__pg_rooms',
            'units__pg_rooms__beds'
        )
        
        # Summary statistics across all buildings
        total_occupied = 0
        total_vacant = 0
        total_capacity = 0
        
        # Add computed stats for each building
        building_list = []
        for building in buildings:
            # Check if this is a PG building (has any PG units)
            has_pg = any(unit.unit_type == 'PG' for unit in building.units.all())
            
            if has_pg:
                # PG Building: Count rooms and beds
                total_rooms = 0
                total_beds = 0
                occupied_beds = 0
                
                for unit in building.units.all():
                    if unit.unit_type == 'PG':
                        for room in unit.pg_rooms.all():
                            total_rooms += 1
                            for bed in room.beds.all():
                                total_beds += 1
                                if bed.status == 'OCCUPIED':
                                    occupied_beds += 1
                
                building.is_pg = True
                building.room_count = total_rooms
                building.bed_count = total_beds
                building.occupied_bed_count = occupied_beds
                building.vacant_bed_count = total_beds - occupied_beds
                
                # Add to summary (for PG, we count beds)
                total_occupied += occupied_beds
                total_vacant += (total_beds - occupied_beds)
                total_capacity += total_beds
            else:
                # Flat Building: Count units
                building.is_pg = False
                occupied = building.units.filter(status='OCCUPIED').count()
                vacant = building.units.filter(status='VACANT').count()
                building.unit_count = building.units.count()
                building.occupied_count = occupied
                building.vacant_count = vacant
                
                # Add to summary (for Flats, we count units)
                total_occupied += occupied
                total_vacant += vacant
                total_capacity += building.unit_count
            
            building_list.append(building)
        
        # Calculate average occupancy
        avg_occupancy = round((total_occupied / total_capacity * 100) if total_capacity > 0 else 0)
        
        context = {
            'buildings': building_list,
            'total_occupied': total_occupied,
            'total_vacant': total_vacant,
            'total_capacity': total_capacity,
            'avg_occupancy': avg_occupancy,
        }
        
        return render(request, 'properties/building_list.html', context)
        
    except Exception as e:
        logger.error(f"Error in building_list view: {str(e)}", exc_info=True)
        from django.contrib import messages
        messages.error(request, 'An error occurred while loading buildings.')
        return render(request, 'properties/building_list.html', {'buildings': []})


@login_required
@owner_or_manager_required
@handle_errors
def building_detail(request, building_id):
    """Building detail view - OPTIMIZED queries"""
    account = getattr(request, 'account', None)
    if not account and hasattr(request.user, 'account') and request.user.account:
        account = request.user.account
        request.account = account
    
    if not account:
        from django.contrib import messages
        messages.warning(request, 'Your account is not properly configured.')
        return redirect('accounts:profile')
    
    try:
        # OPTIMIZED: select_related for building
        building = Building.objects.select_related('account').get(id=building_id, account=account)
        
        # Validate account access
        is_valid, error_msg = validate_account_access(request.user, account)
        if not is_valid:
            logger.warning(f"Access denied for building {building_id}: {error_msg}")
            raise PermissionDenied(error_msg)
        
        # CRITICAL: Check building-level access for managers
        from buildings.access import can_access_building
        if not can_access_building(request.user, building):
            logger.warning(f"Manager {request.user.username} attempted to access building {building_id} without permission")
            raise PermissionDenied("You don't have access to this building.")
        
        # OPTIMIZED: Prefetch units with related data
        units = Unit.objects.filter(building=building).select_related(
            'building', 'account'
        ).prefetch_related(
            Prefetch(
                'pg_rooms',
                queryset=PGRoom.objects.select_related('unit').prefetch_related(
                    Prefetch(
                        'beds',
                        queryset=Bed.objects.select_related('room').prefetch_related(
                            Prefetch(
                                'occupancies',
                                queryset=Occupancy.objects.filter(is_active=True).select_related('tenant', 'tenant__account'),
                                to_attr='active_occupancies'
                            )
                        )
                    )
                )
            ),
            Prefetch(
                'occupancies',
                queryset=Occupancy.objects.filter(is_active=True).select_related('tenant', 'tenant__account'),
                to_attr='active_occupancies'
            )
        ).order_by('unit_number')
        
        # Get current month for rent check
        current_month = timezone.now().date().replace(day=1)
        
        # Get all occupancy IDs that have rent recorded for current month
        occupancies_with_rent = set(
            Rent.objects.filter(
                occupancy__unit__building=building,
                month=current_month
            ).values_list('occupancy_id', flat=True)
        )
        
        # Build units_with_details efficiently
        units_with_details = []
        for unit in units:
            active_occupancies = getattr(unit, 'active_occupancies', [])
            tenant_count = len(active_occupancies)
            
            # For FLAT: Use unit's expected_rent (one rent for whole flat)
            # For PG: Sum of individual bed rents
            if unit.unit_type == 'FLAT':
                total_rent = unit.expected_rent or Decimal('0')
            else:
                total_rent = sum(occ.rent for occ in active_occupancies) if active_occupancies else unit.expected_rent or Decimal('0')
            
            # Check if flat has rent for current month (check primary occupancy)
            flat_has_rent = False
            if unit.unit_type == 'FLAT' and active_occupancies:
                # Check if any occupancy in this flat has rent
                flat_has_rent = any(occ.id in occupancies_with_rent for occ in active_occupancies)
            
            unit_data = {
                'unit': unit,
                'pg_rooms': [],
                'all_occupancies': active_occupancies,
                'tenant_count': tenant_count,
                'total_rent': total_rent,
                'has_rent_this_month': flat_has_rent,
            }
            
            if unit.unit_type == 'PG':
                for room in unit.pg_rooms.all():
                    beds_with_tenants = []
                    room_all_have_rent = True
                    
                    for bed in room.beds.all():
                        bed_occupancy = bed.active_occupancies[0] if bed.active_occupancies else None
                        bed_has_rent = bed_occupancy.id in occupancies_with_rent if bed_occupancy else False
                        
                        # If any occupied bed doesn't have rent, room doesn't have all rent
                        if bed_occupancy and not bed_has_rent:
                            room_all_have_rent = False
                        
                        beds_with_tenants.append({
                            'bed': bed,
                            'occupancy': bed_occupancy,
                            'tenant': bed_occupancy.tenant if bed_occupancy else None,
                            'has_rent_this_month': bed_has_rent,
                        })
                    
                    occupied_count = sum(1 for b in beds_with_tenants if b['tenant'])
                    
                    unit_data['pg_rooms'].append({
                        'room': room,
                        'beds': beds_with_tenants,
                        'occupied_count': occupied_count,
                        'vacant_count': sum(1 for b in beds_with_tenants if not b['tenant']),
                        'all_have_rent': room_all_have_rent and occupied_count > 0,
                    })
            
            units_with_details.append(unit_data)
        
        # OPTIMIZED: Use aggregation for statistics
        stats = Unit.objects.filter(building=building).aggregate(
            total=Count('id'),
            occupied=Count('id', filter=Q(status='OCCUPIED')),
            vacant=Count('id', filter=Q(status='VACANT'))
        )
        total_units = stats['total']
        occupied = stats['occupied']
        vacant = stats['vacant']
        
        # OPTIMIZED: Single query for issues count
        open_issues = Issue.objects.filter(
            unit__building=building,
            status__in=['OPEN', 'ASSIGNED', 'IN_PROGRESS']
        ).count()
        
        # OPTIMIZED: Room statistics for PG buildings
        room_stats = PGRoom.objects.filter(unit__building=building).aggregate(
            total=Count('id')
        )
        total_rooms = room_stats['total']
        
        # Calculate occupied/vacant rooms (a room is occupied if it has at least 1 occupied bed)
        occupied_rooms = PGRoom.objects.filter(
            unit__building=building,
            beds__status='OCCUPIED'
        ).distinct().count()
        vacant_rooms = total_rooms - occupied_rooms
        
        # OPTIMIZED: Bed statistics with aggregation
        bed_stats = Bed.objects.filter(room__unit__building=building).aggregate(
            total=Count('id'),
            occupied=Count('id', filter=Q(status='OCCUPIED')),
            vacant=Count('id', filter=Q(status='VACANT'))
        )
        total_beds = bed_stats['total']
        occupied_beds = bed_stats['occupied']
        vacant_beds = bed_stats['vacant']
        
        # Determine if this is primarily a PG building (has more PG units than FLAT units)
        pg_unit_count = Unit.objects.filter(building=building, unit_type='PG').count()
        flat_unit_count = Unit.objects.filter(building=building, unit_type='FLAT').count()
        is_pg_building = pg_unit_count > flat_unit_count or (total_rooms > 0 and flat_unit_count == 0)
        
        # OPTIMIZED: Building revenue with aggregation
        building_expected_rent = Unit.objects.filter(
            building=building, 
            status='OCCUPIED'
        ).aggregate(total=Sum('expected_rent'))['total'] or Decimal('0')
        
        current_month = timezone.now().date().replace(day=1)
        building_collected = Rent.objects.filter(
            occupancy__unit__building=building,
            month=current_month
        ).aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')
        
        context = {
            'building': building,
            'units_with_details': units_with_details,
            'total_units': total_units,
            'occupied': occupied,
            'vacant': vacant,
            'open_issues': open_issues,
            'total_rooms': total_rooms,
            'occupied_rooms': occupied_rooms,
            'vacant_rooms': vacant_rooms,
            'total_beds': total_beds,
            'occupied_beds': occupied_beds,
            'vacant_beds': vacant_beds,
            'is_pg_building': is_pg_building,
            'building_expected_rent': building_expected_rent,
            'building_collected': building_collected,
        }
        
        return render(request, 'properties/building_detail.html', context)
        
    except Building.DoesNotExist:
        logger.warning(f"Building {building_id} not found or access denied for user {request.user.username}")
        raise Http404("Building not found or you don't have access to it")
    except PermissionDenied:
        raise
    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error in building_detail view: {str(e)}", exc_info=True)
        from django.contrib import messages
        messages.error(request, 'An error occurred while loading building details.')
        return redirect('properties:building_list')


@login_required
@owner_or_manager_required
@handle_errors
def delete_building(request, building_id):
    """Delete a building and all associated data"""
    account = getattr(request, 'account', None)
    if not account and hasattr(request.user, 'account') and request.user.account:
        account = request.user.account
        request.account = account
    
    if not account:
        from django.contrib import messages
        messages.warning(request, 'Your account is not properly configured.')
        return redirect('accounts:profile')
    
    # Only allow POST requests for delete
    if request.method != 'POST':
        from django.contrib import messages
        messages.error(request, 'Invalid request method.')
        return redirect('properties:building_list')
    
    try:
        building = get_object_or_404(Building, id=building_id, account=account)
        building_name = building.name
        
        # Check if user is owner (only owners can delete properties)
        if hasattr(request.user, 'role') and request.user.role != 'OWNER':
            from django.contrib import messages
            messages.error(request, 'Only property owners can delete properties.')
            return redirect('properties:building_list')
        
        # Delete the building (cascades to units, rooms, beds, issues, occupancies, etc.)
        building.delete()
        
        from django.contrib import messages
        messages.success(request, f'Property "{building_name}" and all its data have been permanently deleted.')
        return redirect('properties:building_list')
        
    except Http404:
        from django.contrib import messages
        messages.error(request, 'Property not found or you do not have permission to delete it.')
        return redirect('properties:building_list')
    except Exception as e:
        logger.error(f"Error deleting building {building_id}: {str(e)}", exc_info=True)
        from django.contrib import messages
        messages.error(request, 'An error occurred while deleting the property.')
        return redirect('properties:building_list')


@login_required
@owner_or_manager_required
@handle_errors
def unit_detail(request, unit_id):
    """Unit detail page - OPTIMIZED queries"""
    account = getattr(request, 'account', None)
    if not account and hasattr(request.user, 'account') and request.user.account:
        account = request.user.account
        request.account = account
    
    if not account:
        from django.contrib import messages
        messages.warning(request, 'Your account is not properly configured.')
        return redirect('accounts:profile')
    
    try:
        # OPTIMIZED: select_related for unit with building and account
        unit = Unit.objects.select_related('building', 'account').get(id=unit_id, account=account)
        
        # OPTIMIZED: Get all occupancies with select_related
        if unit.unit_type == 'FLAT':
            all_occupancies = Occupancy.objects.filter(
                unit=unit,
                is_active=True
            ).select_related('tenant', 'unit', 'unit__building').order_by('start_date')
        else:  # PG
            all_occupancies = Occupancy.objects.filter(
                bed__room__unit=unit,
                is_active=True
            ).select_related('tenant', 'bed', 'bed__room', 'bed__room__unit', 'bed__room__unit__building').order_by('bed__room__room_number', 'bed__bed_number')
        
        current_occupancy = all_occupancies.first() if all_occupancies.exists() else None
        current_tenant = current_occupancy.tenant if current_occupancy else None
        
        # OPTIMIZED: Rent history with select_related
        rent_history = []
        if all_occupancies.exists():
            rent_history = Rent.objects.filter(
                occupancy__in=all_occupancies
            ).select_related('occupancy', 'occupancy__tenant').order_by('-month')[:12]
        
        # OPTIMIZED: Issues - avoid select_related('tenant') to prevent FieldError
        issues = Issue.objects.filter(unit=unit).select_related(
            'unit', 'unit__building'
        ).order_by('-raised_date')
        
        # OPTIMIZED: Calculate statistics from rent_history
        total_rent_paid = sum(rent.paid_amount for rent in rent_history)
        pending_rent = sum(rent.pending_amount for rent in rent_history if rent.status != 'PAID')
        
        # OPTIMIZED: For PG units, prefetch rooms and beds
        pg_rooms_with_tenants = []
        if unit.unit_type == 'PG':
            pg_rooms = PGRoom.objects.filter(unit=unit).prefetch_related(
                Prefetch(
                    'beds',
                    queryset=Bed.objects.prefetch_related(
                        Prefetch(
                            'occupancies',
                            queryset=Occupancy.objects.filter(is_active=True).select_related('tenant'),
                            to_attr='active_occupancies'
                        )
                    )
                )
            ).order_by('room_number')
            
            for room in pg_rooms:
                beds_with_tenants = []
                for bed in room.beds.all():
                    bed_occupancy = bed.active_occupancies[0] if bed.active_occupancies else None
                    beds_with_tenants.append({
                        'bed': bed,
                        'occupancy': bed_occupancy,
                        'tenant': bed_occupancy.tenant if bed_occupancy else None
                    })
                pg_rooms_with_tenants.append({
                    'room': room,
                    'beds': beds_with_tenants
                })
        
        context = {
            'unit': unit,
            'current_tenant': current_tenant,
            'current_occupancy': current_occupancy,
            'all_occupancies': all_occupancies,
            'rent_history': rent_history,
            'issues': issues,
            'total_rent_paid': total_rent_paid,
            'pending_rent': pending_rent,
            'pg_rooms_with_tenants': pg_rooms_with_tenants,
            'tenant_count': all_occupancies.count(),
        }
        
        return render(request, 'properties/unit_detail.html', context)
        
    except Unit.DoesNotExist:
        logger.warning(f"Unit {unit_id} not found or access denied for user {request.user.username}")
        raise Http404("Unit not found or you don't have access to it")
    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error in unit_detail view: {str(e)}", exc_info=True)
        from django.contrib import messages
        messages.error(request, 'An error occurred while loading unit details.')
        return redirect('properties:building_list')


@login_required
@owner_or_manager_required
@handle_errors
def vacancy_view(request):
    """Vacancy Intelligence - OPTIMIZED queries"""
    from buildings.access import get_accessible_buildings, get_accessible_building_ids
    
    account = getattr(request, 'account', None)
    if not account and hasattr(request.user, 'account') and request.user.account:
        account = request.user.account
        request.account = account
    
    if not account:
        from django.contrib import messages
        messages.warning(request, 'Your account is not properly configured.')
        return redirect('accounts:profile')
    
    # Get accessible buildings for managers
    accessible_buildings = get_accessible_buildings(request.user)
    accessible_building_ids = get_accessible_building_ids(request.user)
    
    try:
        # Get building filter from request
        building_filter = request.GET.get('building', '')
        
        # OPTIMIZED: select_related for building - filter by accessible buildings
        vacant_units = Unit.objects.filter(
            account=account,
            status='VACANT',
            building_id__in=accessible_building_ids
        ).select_related('building', 'account')
        
        # Apply building filter if provided (ensure it's accessible)
        if building_filter and int(building_filter) in accessible_building_ids:
            vacant_units = vacant_units.filter(building_id=building_filter)
        elif building_filter:
            vacant_units = vacant_units.none()  # Building not accessible
        
        vacant_units = vacant_units.order_by('building__name', 'unit_number')
        
        # OPTIMIZED: Use aggregation for loss calculation
        loss_data = vacant_units.aggregate(
            monthly_loss=Sum('expected_rent')
        )
        monthly_loss = loss_data['monthly_loss'] or Decimal('0')
        yearly_loss = monthly_loss * 12
        
        # OPTIMIZED: Filter by type
        vacant_flats = vacant_units.filter(unit_type='FLAT')
        vacant_pgs = vacant_units.filter(unit_type='PG')
        
        # OPTIMIZED: Vacant beds with select_related - filter by accessible buildings
        vacant_beds_query = Bed.objects.filter(
            room__unit__account=account,
            status='VACANT',
            room__unit__building_id__in=accessible_building_ids
        ).select_related('room', 'room__unit', 'room__unit__building')
        
        # Apply building filter to beds if provided (ensure it's accessible)
        if building_filter and int(building_filter) in accessible_building_ids:
            vacant_beds_query = vacant_beds_query.filter(room__unit__building_id=building_filter)
        elif building_filter:
            vacant_beds_query = vacant_beds_query.none()  # Building not accessible
        
        vacant_beds = vacant_beds_query.order_by('room__unit__building__name', 'room__room_number', 'bed_number')
        
        # Calculate bed loss - estimate rent per bed based on occupancy rent or split
        bed_loss = Decimal('0')
        for bed in vacant_beds:
            # Try to get rent from other occupancies in same room
            from occupancy.models import Occupancy as OccModel
            other_occupancy = OccModel.objects.filter(
                bed__room=bed.room,
                is_active=True
            ).first()
            if other_occupancy:
                bed_loss += other_occupancy.rent
            elif bed.room.sharing_type > 0 and bed.room.unit.expected_rent:
                bed_loss += bed.room.unit.expected_rent / bed.room.sharing_type
        
        # Group vacant units by building (for FLAT display)
        # Only include buildings that are accessible
        from itertools import groupby
        from operator import attrgetter
        
        grouped_vacant_units = {}
        for building_name, units in groupby(vacant_units, key=attrgetter('building')):
            # Safety check: ensure building is accessible
            if building_name.id not in accessible_building_ids:
                continue
            units_list = list(units)
            building_loss = sum(unit.expected_rent for unit in units_list)
            grouped_vacant_units[building_name] = {
                'units': units_list,
                'count': len(units_list),
                'monthly_loss': building_loss
            }
        
        # Group vacant beds by building and room (for PG display)
        # Only include buildings that are accessible
        grouped_vacant_beds = {}
        for bed in vacant_beds:
            building = bed.room.unit.building
            room = bed.room
            
            # Safety check: ensure building is accessible
            if building.id not in accessible_building_ids:
                continue
            
            if building.id not in grouped_vacant_beds:
                grouped_vacant_beds[building.id] = {
                    'building': building,
                    'rooms': {},
                    'total_beds': 0
                }
            
            if room.id not in grouped_vacant_beds[building.id]['rooms']:
                # Get room occupancy info
                total_beds_in_room = room.beds.count()
                occupied_beds_in_room = room.beds.filter(status='OCCUPIED').count()
                
                grouped_vacant_beds[building.id]['rooms'][room.id] = {
                    'room': room,
                    'beds': [],
                    'total_beds': total_beds_in_room,
                    'occupied_beds': occupied_beds_in_room,
                    'vacant_beds': total_beds_in_room - occupied_beds_in_room
                }
            
            grouped_vacant_beds[building.id]['rooms'][room.id]['beds'].append(bed)
            grouped_vacant_beds[building.id]['total_beds'] += 1
        
        # Get accessible buildings for filter dropdown (managers only see accessible buildings)
        from buildings.access import get_accessible_buildings
        all_buildings = get_accessible_buildings(request.user).order_by('name')
        
        # Final safety check: Ensure all buildings in context are accessible
        # Filter grouped_vacant_units to only include accessible buildings
        filtered_grouped_units = {
            building: data for building, data in grouped_vacant_units.items()
            if building.id in accessible_building_ids
        }
        
        # Filter grouped_vacant_beds to only include accessible buildings
        filtered_grouped_beds = {
            bid: data for bid, data in grouped_vacant_beds.items()
            if bid in accessible_building_ids
        }
        
        # Check if there are any PG buildings/units at all (to show "Add PG Property" vs "All Beds Occupied")
        has_pg_buildings = Unit.objects.filter(
            account=account,
            unit_type='PG',
            building_id__in=accessible_building_ids
        ).exists()
        
        context = {
            'vacant_units': vacant_units,
            'grouped_vacant_units': filtered_grouped_units,
            'vacant_flats': vacant_flats,
            'vacant_pgs': vacant_pgs,
            'vacant_beds': vacant_beds,
            'grouped_vacant_beds': filtered_grouped_beds,
            'monthly_loss': monthly_loss,
            'yearly_loss': yearly_loss,
            'bed_loss': bed_loss,
            'total_loss': monthly_loss + bed_loss,
            'count': vacant_units.count(),
            'bed_count': vacant_beds.count(),
            'building_filter': building_filter,
            'all_buildings': all_buildings,  # Already filtered by get_accessible_buildings
            'has_pg_buildings': has_pg_buildings,  # Whether any PG buildings exist
        }
        
        return render(request, 'properties/vacancy.html', context)
        
    except Exception as e:
        logger.error(f"Error in vacancy_view: {str(e)}", exc_info=True)
        from django.contrib import messages
        messages.error(request, 'An error occurred while loading vacancy information.')
        return redirect('properties:dashboard')


@login_required
@owner_or_manager_required
@handle_errors
def rent_management(request):
    """Rent Management View - OPTIMIZED queries"""
    from buildings.access import get_accessible_buildings, get_accessible_building_ids
    
    account = getattr(request, 'account', None)
    if not account and hasattr(request.user, 'account') and request.user.account:
        account = request.user.account
        request.account = account
    
    if not account:
        from django.contrib import messages
        messages.warning(request, 'Your account is not properly configured.')
        return redirect('accounts:profile')
    
    # Get accessible buildings for managers
    accessible_buildings = get_accessible_buildings(request.user)
    accessible_building_ids = get_accessible_building_ids(request.user)
    
    try:
        # Handle export requests
        if request.GET.get('export') == 'csv':
            from rent.utils import export_rent_report
            current_month = timezone.now().date().replace(day=1)
            
            # Get filters for export
            month_filter = request.GET.get('month')
            if month_filter:
                try:
                    filter_date = datetime.strptime(month_filter, '%Y-%m').date()
                    current_month = filter_date.replace(day=1)
                except ValueError:
                    pass
            
            building_filter = request.GET.get('building', '')
            status_filter = request.GET.get('status', '')
            tenant_filter = request.GET.get('tenant', '').strip()
            unit_filter = request.GET.get('unit', '').strip()
            
            # Filter by accessible buildings
            rents = Rent.objects.filter(
                occupancy__tenant__account=account,
                month=current_month
            ).filter(
                Q(occupancy__unit__building_id__in=accessible_building_ids) |
                Q(occupancy__bed__room__unit__building_id__in=accessible_building_ids)
            ).select_related(
                'occupancy', 
                'occupancy__tenant', 
                'occupancy__unit',
                'occupancy__unit__building',
                'occupancy__bed',
                'occupancy__bed__room',
                'occupancy__bed__room__unit',
                'occupancy__bed__room__unit__building'
            )
            
            # Apply the same filters for export (ensure building is accessible)
            if building_filter and int(building_filter) in accessible_building_ids:
                rents = rents.filter(
                    Q(occupancy__unit__building_id=building_filter) |
                    Q(occupancy__bed__room__unit__building_id=building_filter)
                )
            elif building_filter:
                rents = rents.none()  # Building not accessible
            if status_filter:
                rents = rents.filter(status=status_filter)
            if tenant_filter:
                rents = rents.filter(occupancy__tenant__name__icontains=tenant_filter)
            if unit_filter:
                rents = rents.filter(
                    Q(occupancy__unit__unit_number__icontains=unit_filter) |
                    Q(occupancy__bed__room__unit__unit_number__icontains=unit_filter) |
                    Q(occupancy__bed__bed_number__icontains=unit_filter)
                )
            
            return export_rent_report(rents, format='csv')
        
        # Handle receipt generation
        if request.GET.get('receipt'):
            try:
                from rent.utils import generate_rent_receipt, WEASYPRINT_AVAILABLE
                if not WEASYPRINT_AVAILABLE:
                    from django.contrib import messages
                    messages.warning(request, 'PDF generation is not available. Please install weasyprint for PDF support.')
                    return redirect('properties:rent_management')
                
                rent_id = int(request.GET.get('receipt'))
                rent = Rent.objects.select_related(
                    'occupancy',
                    'occupancy__tenant',
                    'occupancy__unit',
                    'occupancy__unit__building',
                    'occupancy__bed',
                    'occupancy__bed__room',
                    'occupancy__bed__room__unit',
                    'occupancy__bed__room__unit__building'
                ).get(id=rent_id, occupancy__tenant__account=account)
                return generate_rent_receipt(rent, format='html')
            except (Rent.DoesNotExist, ValueError):
                from django.contrib import messages
                messages.error(request, 'Invalid rent receipt request.')
                return redirect('properties:rent_management')
            except ImportError:
                from django.contrib import messages
                messages.warning(request, 'Receipt generation is not available.')
                return redirect('properties:rent_management')
        
        current_month = timezone.now().date().replace(day=1)
        last_month = (current_month - timedelta(days=1)).replace(day=1)
        
        # Month filter
        month_filter = request.GET.get('month')
        if month_filter:
            try:
                filter_date = datetime.strptime(month_filter, '%Y-%m').date()
                filter_date = filter_date.replace(day=1)
                current_month = filter_date
            except ValueError:
                pass
        
        # AUTO-GENERATE rent entries for current month if viewing current month
        today = timezone.now().date()
        viewing_current_month = current_month == today.replace(day=1)
        if viewing_current_month:
            
            # Get all active occupancies that should have rent entries
            active_occupancies = Occupancy.objects.filter(
                tenant__account=account,
                is_active=True
            ).filter(
                Q(unit__building_id__in=accessible_building_ids) |
                Q(bed__room__unit__building_id__in=accessible_building_ids)
            ).select_related('unit', 'bed', 'bed__room', 'bed__room__unit')
            
            # Generate rent entries for missing occupancies
            generated_count = 0
            for occupancy in active_occupancies:
                # Skip non-primary tenants in flats
                if occupancy.unit and occupancy.unit.unit_type == 'FLAT':
                    # Check is_primary field (use getattr for safety during migration)
                    is_primary = getattr(occupancy, 'is_primary', True)  # Default to True for backward compatibility
                    if not is_primary:
                        continue
                
                if occupancy.rent <= 0:
                    continue
                    
                # Check if rent entry exists for current month
                exists = Rent.objects.filter(
                    occupancy=occupancy,
                    month=current_month
                ).exists()
                
                if not exists:
                    Rent.objects.create(
                        occupancy=occupancy,
                        month=current_month,
                        amount=occupancy.rent,
                        paid_amount=Decimal('0'),
                        status='PENDING',
                        notes=f"Auto-generated rent entry for {current_month.strftime('%B %Y')}"
                    )
                    generated_count += 1
            
            if generated_count > 0:
                logger.info(f"Auto-generated {generated_count} rent entries for {current_month.strftime('%B %Y')}")
        
        # Get additional filters
        building_filter = request.GET.get('building', '')
        status_filter = request.GET.get('status', '')
        tenant_filter = request.GET.get('tenant', '').strip()
        unit_filter = request.GET.get('unit', '').strip()
        
        # OPTIMIZED: Rent query with all necessary select_related - include both units and beds
        # Filter by accessible buildings for managers
        rents = Rent.objects.filter(
            Q(occupancy__unit__building__account=account) |
            Q(occupancy__bed__room__unit__building__account=account),
            month=current_month
        ).filter(
            Q(occupancy__unit__building_id__in=accessible_building_ids) |
            Q(occupancy__bed__room__unit__building_id__in=accessible_building_ids)
        ).select_related(
            'occupancy',
            'occupancy__tenant',
            'occupancy__unit',
            'occupancy__unit__building',
            'occupancy__bed',
            'occupancy__bed__room',
            'occupancy__bed__room__unit',
            'occupancy__bed__room__unit__building'
        )
        
        # Apply filters (ensure building is accessible)
        if building_filter and int(building_filter) in accessible_building_ids:
            # Filter by building for both flat units and PG beds
            rents = rents.filter(
                Q(occupancy__unit__building_id=building_filter) |
                Q(occupancy__bed__room__unit__building_id=building_filter)
            )
        elif building_filter:
            rents = rents.none()  # Building not accessible
        
        if status_filter:
            rents = rents.filter(status=status_filter)
        
        if tenant_filter:
            rents = rents.filter(occupancy__tenant__name__icontains=tenant_filter)
        
        if unit_filter:
            # Search in both unit number and bed number
            rents = rents.filter(
                Q(occupancy__unit__unit_number__icontains=unit_filter) |
                Q(occupancy__bed__room__unit__unit_number__icontains=unit_filter) |
                Q(occupancy__bed__bed_number__icontains=unit_filter)
            )
        
        rents = rents.order_by('-amount')
        
        # OPTIMIZED: Use aggregation for statistics
        stats = rents.aggregate(
            total_expected=Sum('amount'),
            total_paid=Sum('paid_amount'),
            paid_count=Count('id', filter=Q(status='PAID')),
            pending_count=Count('id', filter=Q(status='PENDING')),
            partial_count=Count('id', filter=Q(status='PARTIAL'))
        )
        total_expected = stats['total_expected'] or Decimal('0')
        total_paid = stats['total_paid'] or Decimal('0')
        total_pending = total_expected - total_paid
        paid_count = stats['paid_count']
        pending_count = stats['pending_count']
        partial_count = stats['partial_count']
        
        # OPTIMIZED: Pending rents
        pending_rents = rents.filter(status__in=['PENDING', 'PARTIAL']).order_by('occupancy__tenant__name')
        
        # OPTIMIZED: Last month with aggregation - include both units and beds (filter by accessible buildings)
        last_month_total = Rent.objects.filter(
            Q(occupancy__unit__building__account=account) |
            Q(occupancy__bed__room__unit__building__account=account),
            month=last_month
        ).filter(
            Q(occupancy__unit__building_id__in=accessible_building_ids) |
            Q(occupancy__bed__room__unit__building_id__in=accessible_building_ids)
        ).aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')
        
        # Get ALL available months (not just last 12) - include both units and beds (filter by accessible buildings)
        available_months = Rent.objects.filter(
            Q(occupancy__unit__building__account=account) |
            Q(occupancy__bed__room__unit__building__account=account)
        ).filter(
            Q(occupancy__unit__building_id__in=accessible_building_ids) |
            Q(occupancy__bed__room__unit__building_id__in=accessible_building_ids)
        ).values_list('month', flat=True).distinct().order_by('-month')
        
        # ===== MONTH-WISE SUMMARY (Expected vs Collected) =====
        from django.db.models.functions import TruncMonth
        month_wise_summary = Rent.objects.filter(
            Q(occupancy__unit__building__account=account) |
            Q(occupancy__bed__room__unit__building__account=account)
        ).filter(
            Q(occupancy__unit__building_id__in=accessible_building_ids) |
            Q(occupancy__bed__room__unit__building_id__in=accessible_building_ids)
        ).annotate(
            rent_month=TruncMonth('month')
        ).values('rent_month').annotate(
            expected=Sum('amount'),
            collected=Sum('paid_amount'),
            pending=Sum('amount') - Sum('paid_amount'),
            paid_count=Count('id', filter=Q(status='PAID')),
            partial_count=Count('id', filter=Q(status='PARTIAL')),
            pending_count=Count('id', filter=Q(status='PENDING'))
        ).order_by('-rent_month')[:12]  # Last 12 months
        
        # Format month-wise data
        month_summary_list = []
        for item in month_wise_summary:
            if item['rent_month']:
                month_summary_list.append({
                    'month': item['rent_month'],
                    'month_str': item['rent_month'].strftime('%b %Y'),
                    'expected': float(item['expected'] or 0),
                    'collected': float(item['collected'] or 0),
                    'pending': float(item['pending'] or 0),
                    'rate': round((float(item['collected'] or 0) / float(item['expected'] or 1) * 100), 1),
                    'paid_count': item['paid_count'],
                    'partial_count': item['partial_count'],
                    'pending_count': item['pending_count'],
                })
        
        # Get all buildings for filter dropdown
        from buildings.access import get_accessible_buildings
        buildings = get_accessible_buildings(request.user).order_by('name')
        
        # Calculate overdue (more than 5 days past month end)
        today = timezone.now().date()
        overdue_rents = []
        for rent in pending_rents:
            month_end = (rent.month + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            if today > month_end + timedelta(days=5):
                overdue_rents.append(rent)
        
        context = {
            'rents': rents,
            'current_month': current_month,
            'last_month': last_month,
            'total_expected': total_expected,
            'total_paid': total_paid,
            'total_pending': total_pending,
            'paid_count': paid_count,
            'pending_count': pending_count,
            'partial_count': partial_count,
            'pending_rents': pending_rents,
            'overdue_rents': overdue_rents,
            'last_month_total': last_month_total,
            'collection_rate': (total_paid / total_expected * 100) if total_expected > 0 else 0,
            'available_months': available_months,
            'month_wise_summary': month_summary_list,
            'buildings': buildings,
            'building_filter': building_filter,
            'status_filter': status_filter,
            'tenant_filter': tenant_filter,
            'unit_filter': unit_filter,
        }
        
        return render(request, 'properties/rent_management.html', context)
        
    except Exception as e:
        logger.error(f"Error in rent_management: {str(e)}", exc_info=True)
        from django.contrib import messages
        messages.error(request, 'An error occurred while loading rent information.')
        return redirect('properties:dashboard')


@login_required
@owner_or_manager_required
@handle_errors
def issue_list(request):
    """Issue/Complaint List - OPTIMIZED queries"""
    account = getattr(request, 'account', None)
    if not account and hasattr(request.user, 'account') and request.user.account:
        account = request.user.account
        request.account = account
    
    if not account:
        from django.contrib import messages
        messages.warning(request, 'Your account is not properly configured.')
        return redirect('accounts:profile')
    
    try:
        # Get accessible buildings for managers
        from buildings.access import get_accessible_building_ids
        accessible_building_ids = get_accessible_building_ids(request.user)
        
        # OPTIMIZED: select_related for all foreign keys - filter by accessible buildings
        issues_queryset = Issue.objects.filter(
            unit__account=account,
            unit__building_id__in=accessible_building_ids
        ).select_related('unit', 'unit__building', 'unit__account').order_by('-raised_date')
        
        # Filter by status if provided (BEFORE pagination)
        status_filter = request.GET.get('status', '')
        if status_filter:
            issues_queryset = issues_queryset.filter(status=status_filter)
        
        # Priority filter (BEFORE pagination)
        priority_filter = request.GET.get('priority', '')
        if priority_filter:
            issues_queryset = issues_queryset.filter(priority=priority_filter)
        
        # OPTIMIZED: Statistics using aggregation (BEFORE pagination)
        # Get stats from ALL issues (not filtered) for the stats cards - filter by accessible buildings
        all_issues_stats = Issue.objects.filter(
            unit__account=account,
            unit__building_id__in=accessible_building_ids
        ).aggregate(
            total=Count('id'),
            open=Count('id', filter=Q(status='OPEN')),
            in_progress=Count('id', filter=Q(status='IN_PROGRESS')),
            assigned=Count('id', filter=Q(status='ASSIGNED')),
            resolved=Count('id', filter=Q(status='RESOLVED')),
            urgent=Count('id', filter=Q(priority='URGENT', status__in=['OPEN', 'IN_PROGRESS', 'ASSIGNED']))
        )
        
        # Pagination for scalability (AFTER filtering and stats)
        paginator = Paginator(issues_queryset, 20)  # 20 items per page
        page = request.GET.get('page', 1)
        try:
            issues = paginator.page(page)
        except PageNotAnInteger:
            issues = paginator.page(1)
        except EmptyPage:
            issues = paginator.page(paginator.num_pages)
        
        context = {
            'issues': issues,
            'status_filter': status_filter,
            'priority_filter': priority_filter,
            'stats': all_issues_stats,
            'open_count': all_issues_stats['open'],
            'resolved_count': all_issues_stats['resolved'],
            'urgent_count': all_issues_stats['urgent'],
            'paginator': paginator if 'paginator' in locals() else None,
        }
        
        return render(request, 'properties/issue_list.html', context)
        
    except Exception as e:
        logger.error(f"Error in issue_list: {str(e)}", exc_info=True)
        from django.contrib import messages
        messages.error(request, 'An error occurred while loading issues.')
        return redirect('properties:dashboard')


@login_required
@owner_or_manager_required
@handle_errors
def issue_detail(request, issue_id):
    """Issue detail view - OPTIMIZED queries"""
    account = getattr(request, 'account', None)
    if not account and hasattr(request.user, 'account') and request.user.account:
        account = request.user.account
        request.account = account
    
    if not account:
        from django.contrib import messages
        messages.warning(request, 'Your account is not properly configured.')
        return redirect('accounts:profile')
    
    try:
        # OPTIMIZED: select_related for all related objects - avoid select_related('tenant') to prevent FieldError
        issue = Issue.objects.select_related(
            'unit',
            'unit__building',
            'unit__account'
        ).get(id=issue_id, unit__account=account)
        
        # CRITICAL: Check building access for managers
        from buildings.access import can_access_building
        if not can_access_building(request.user, issue.unit.building):
            from django.contrib import messages
            messages.error(request, 'You don\'t have access to this building.')
            raise PermissionDenied("You don't have access to this building.")
        
        if request.method == 'POST':
            new_status = request.POST.get('status')
            new_priority = request.POST.get('priority')
            assigned_to = request.POST.get('assigned_to', '')
            
            if new_status and new_status in dict(Issue.STATUS_CHOICES):
                issue.status = new_status
                if new_status == 'RESOLVED' and not issue.resolved_date:
                    issue.resolved_date = timezone.now()
            
            if new_priority and new_priority in dict(Issue.PRIORITY_CHOICES):
                issue.priority = new_priority
            
            if assigned_to:
                issue.assigned_to = assigned_to
            
            issue.save()
            from django.contrib import messages
            messages.success(request, 'Issue updated successfully.')
            return redirect('properties:issue_detail', issue_id=issue.id)
        
        return render(request, 'properties/issue_detail.html', {'issue': issue})
        
    except Issue.DoesNotExist:
        logger.warning(f"Issue {issue_id} not found or access denied for user {request.user.username}")
        raise Http404("Issue not found or you don't have access to it")
    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error in issue_detail: {str(e)}", exc_info=True)
        from django.contrib import messages
        messages.error(request, 'An error occurred while loading issue details.')
        return redirect('properties:issue_list')


@login_required
@owner_or_manager_required
@handle_errors
def tenant_history(request, tenant_id):
    """View tenant history - OPTIMIZED queries"""
    account = getattr(request, 'account', None)
    if not account and hasattr(request.user, 'account') and request.user.account:
        account = request.user.account
        request.account = account
    
    if not account:
        from django.contrib import messages
        messages.warning(request, 'Your account is not properly configured.')
        return redirect('accounts:profile')
    
    try:
        # OPTIMIZED: select_related for tenant
        tenant = Tenant.objects.select_related('account').get(id=tenant_id, account=account)
        
        # Get accessible buildings for managers
        from buildings.access import get_accessible_building_ids
        accessible_building_ids = get_accessible_building_ids(request.user)
        
        # OPTIMIZED: Occupancies with select_related - filter by accessible buildings
        occupancies = Occupancy.objects.filter(tenant=tenant).filter(
            Q(unit__building_id__in=accessible_building_ids) |
            Q(bed__room__unit__building_id__in=accessible_building_ids)
        ).select_related(
            'tenant',
            'unit',
            'unit__building',
            'bed',
            'bed__room',
            'bed__room__unit',
            'bed__room__unit__building'
        ).order_by('-start_date')
        
        # OPTIMIZED: Rent payments with select_related
        all_rents = Rent.objects.filter(
            occupancy__tenant=tenant
        ).select_related(
            'occupancy',
            'occupancy__tenant',
            'occupancy__unit',
            'occupancy__bed'
        ).order_by('-month')
        
        # OPTIMIZED: Issues - avoid select_related('tenant') to prevent FieldError
        issues = Issue.objects.filter(tenant=tenant).select_related(
            'unit',
            'unit__building'
        ).order_by('-raised_date')
        
        # OPTIMIZED: Statistics using aggregation
        # Note: pending_amount is a property, not a field, so we calculate it manually
        rent_stats = all_rents.aggregate(
            total_paid=Sum('paid_amount', filter=Q(status='PAID')),
            total_expected=Sum('amount', filter=Q(status__in=['PENDING', 'PARTIAL'])),
            total_paid_for_pending=Sum('paid_amount', filter=Q(status__in=['PENDING', 'PARTIAL']))
        )
        total_rent_paid = rent_stats['total_paid'] or Decimal('0')
        # Calculate pending: expected - paid for pending/partial rents
        total_pending = (rent_stats['total_expected'] or Decimal('0')) - (rent_stats['total_paid_for_pending'] or Decimal('0'))
        
        context = {
            'tenant': tenant,
            'occupancies': occupancies,
            'all_rents': all_rents,
            'issues': issues,
            'total_rent_paid': total_rent_paid,
            'total_pending': total_pending,
        }
        
        return render(request, 'properties/tenant_history.html', context)
        
    except Tenant.DoesNotExist:
        raise Http404("Tenant not found")
    except Exception as e:
        logger.error(f"Error in tenant_history: {str(e)}", exc_info=True)
        from django.contrib import messages
        messages.error(request, 'An error occurred while loading tenant history.')
        return redirect('properties:dashboard')


def generate_monthly_rent_records(occupancy):
    """
    Generate PENDING rent records for all months from move-in to current month.
    This ensures every month has a rent entry that can be tracked and paid.
    Returns the number of records created.
    
    NOTE: For flats, only the primary tenant gets rent records.
    For PG beds, each bed gets its own rent record.
    """
    # For flats: only generate rent for primary tenant
    if occupancy.unit and occupancy.unit.unit_type == 'FLAT':
        # Use getattr for safety during migration
        is_primary = getattr(occupancy, 'is_primary', True)  # Default to True for backward compatibility
        if not is_primary:
            return 0  # Skip non-primary tenants in flats
    
    monthly_rent = occupancy.rent or Decimal('0')
    
    # Skip if rent is 0
    if monthly_rent <= 0:
        return 0
    
    move_in_date = occupancy.start_date
    current_date = timezone.now().date()
    current_month = current_date.replace(day=1)
    move_in_month = move_in_date.replace(day=1)
    
    # Generate list of all months from move-in to current
    all_required_months = []
    month_iter = move_in_month
    while month_iter <= current_month:
        all_required_months.append(month_iter)
        if month_iter.month == 12:
            month_iter = month_iter.replace(year=month_iter.year + 1, month=1)
        else:
            month_iter = month_iter.replace(month=month_iter.month + 1)
    
    # Get existing rent records
    existing_months = set(Rent.objects.filter(
        occupancy=occupancy
    ).values_list('month', flat=True))
    
    # Create PENDING records for missing months
    created_count = 0
    for month in all_required_months:
        if month not in existing_months:
            Rent.objects.create(
                occupancy=occupancy,
                month=month,
                amount=monthly_rent,
                paid_amount=Decimal('0'),
                status='PENDING',
                notes=f"Auto-generated rent entry for {month.strftime('%B %Y')}"
            )
            created_count += 1
    
    return created_count


@login_required
@owner_or_manager_required
@handle_errors
def tenant_checkout(request, tenant_id):
    """Tenant checkout - Review history and process checkout with month-wise rent validation"""
    account = getattr(request, 'account', None)
    if not account and hasattr(request.user, 'account') and request.user.account:
        account = request.user.account
        request.account = account
    
    if not account:
        from django.contrib import messages
        messages.warning(request, 'Your account is not properly configured.')
        return redirect('accounts:profile')
    
    try:
        # Get tenant with all related data
        tenant = Tenant.objects.select_related('account').get(id=tenant_id, account=account)
        
        # Get current active occupancy
        current_occupancy = Occupancy.objects.filter(
            tenant=tenant,
            is_active=True
        ).select_related(
            'unit', 'unit__building',
            'bed', 'bed__room', 'bed__room__unit', 'bed__room__unit__building'
        ).first()
        
        if not current_occupancy:
            from django.contrib import messages
            messages.warning(request, f'{tenant.name} does not have an active occupancy.')
            return redirect('properties:tenant_history', tenant_id=tenant_id)
        
        # CRITICAL: Check building access for managers
        from buildings.access import can_access_building
        building_to_check = current_occupancy.unit.building if current_occupancy.unit else current_occupancy.bed.room.unit.building
        if not can_access_building(request.user, building_to_check):
            from django.contrib import messages
            messages.error(request, 'You don\'t have access to this building.')
            raise PermissionDenied("You don't have access to this building.")
        
        # AUTO-GENERATE rent records for all months (ensures every month has an entry)
        records_created = generate_monthly_rent_records(current_occupancy)
        if records_created > 0:
            logger.info(f"Auto-generated {records_created} rent records for tenant {tenant.name}")
        
        # Get monthly rent for this occupancy
        monthly_rent = current_occupancy.rent or Decimal('0')
        
        # Calculate all months tenant should have paid rent for
        # From move-in date to current month
        move_in_date = current_occupancy.start_date
        current_date = timezone.now().date()
        current_month = current_date.replace(day=1)
        move_in_month = move_in_date.replace(day=1)
        
        # Generate list of all months from move-in to current
        all_required_months = []
        month_iter = move_in_month
        while month_iter <= current_month:
            all_required_months.append(month_iter)
            # Move to next month
            if month_iter.month == 12:
                month_iter = month_iter.replace(year=month_iter.year + 1, month=1)
            else:
                month_iter = month_iter.replace(month=month_iter.month + 1)
        
        # Get all rent records for this occupancy (now includes auto-generated ones)
        occupancy_rents = Rent.objects.filter(
            occupancy=current_occupancy
        ).select_related('occupancy').order_by('-month')
        
        # Create a dict of existing rent records by month
        rent_by_month = {rent.month: rent for rent in occupancy_rents}
        
        # Get pending/partial rents (existing records that are not fully paid)
        pending_rents = occupancy_rents.filter(status__in=['PENDING', 'PARTIAL'])
        
        # Calculate total dues from pending/partial rents
        total_dues = Decimal('0')
        for rent in pending_rents:
            total_dues += rent.pending_amount
        
        # Get all rent records for this tenant (for history display)
        all_rents = Rent.objects.filter(
            occupancy__tenant=tenant
        ).select_related('occupancy').order_by('-month')
        
        # Get all issues for this tenant
        all_issues = Issue.objects.filter(tenant=tenant).select_related(
            'unit', 'unit__building'
        ).order_by('-raised_date')
        
        # Get open/unresolved issues
        open_issues = all_issues.filter(status__in=['OPEN', 'IN_PROGRESS', 'ASSIGNED'])
        
        # Calculate stats
        total_rent_paid = all_rents.aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')
        total_months_stayed = len(all_required_months)
        
        # Determine current location
        if current_occupancy.unit:
            location_type = 'FLAT'
            building = current_occupancy.unit.building
            location_detail = f"Unit {current_occupancy.unit.unit_number}"
        else:
            location_type = 'PG'
            building = current_occupancy.bed.room.unit.building
            location_detail = f"Room {current_occupancy.bed.room.room_number}, Bed {current_occupancy.bed.bed_number}"
        
        # Build month-wise rent status for display (all months now have records)
        month_wise_status = []
        for month in reversed(all_required_months):  # Show oldest first
            rent = rent_by_month.get(month)
            if rent:
                month_wise_status.append({
                    'month': month,
                    'rent_id': rent.id,
                    'amount': rent.amount,
                    'paid_amount': rent.paid_amount,
                    'pending_amount': rent.pending_amount,
                    'status': rent.status,
                    'paid_date': rent.paid_date,
                })
        
        # Count pending months
        pending_months_count = pending_rents.count()
        
        # Notice Period Information
        notice_date = current_occupancy.notice_date
        has_given_notice = current_occupancy.has_given_notice
        required_notice_days = current_occupancy.required_notice_days
        days_since_notice = current_occupancy.days_since_notice
        days_until_eligible = current_occupancy.days_until_eligible
        is_eligible_for_checkout = current_occupancy.is_eligible_for_checkout
        expected_checkout_date = current_occupancy.expected_checkout_date or current_occupancy.calculate_expected_checkout()
        notice_reason = current_occupancy.notice_reason
        
        # Check if checkout is allowed (no pending dues, no open issues, AND notice period completed)
        can_checkout = total_dues == 0 and open_issues.count() == 0 and is_eligible_for_checkout
        checkout_warnings = []
        
        if not has_given_notice:
            checkout_warnings.append(f'Tenant has not given notice. {required_notice_days} days notice required.')
        elif not is_eligible_for_checkout:
            checkout_warnings.append(f'Notice period not completed. {days_until_eligible} day(s) remaining.')
        
        if total_dues > 0:
            checkout_warnings.append(f'₹{total_dues:.0f} pending rent from {pending_months_count} month(s)')
        if open_issues.count() > 0:
            checkout_warnings.append(f'{open_issues.count()} unresolved issue(s)')
        
        # Process checkout if POST
        if request.method == 'POST':
            force_checkout = request.POST.get('force_checkout') == 'true'
            
            if can_checkout or force_checkout:
                with transaction.atomic():
                    # Mark occupancy as inactive
                    current_occupancy.is_active = False
                    current_occupancy.end_date = timezone.now().date()
                    current_occupancy.save()
                    
                    # Update unit/bed status to VACANT
                    if current_occupancy.unit:
                        # Check if any other active occupancies exist for this unit
                        other_occupancies = Occupancy.objects.filter(
                            unit=current_occupancy.unit,
                            is_active=True
                        ).exclude(id=current_occupancy.id).exists()
                        
                        if not other_occupancies:
                            current_occupancy.unit.status = 'VACANT'
                            current_occupancy.unit.save()
                    
                    if current_occupancy.bed:
                        current_occupancy.bed.status = 'VACANT'
                        current_occupancy.bed.save()
                    
                    from django.contrib import messages
                    if force_checkout:
                        messages.warning(request, f'{tenant.name} has been checked out with ₹{total_dues:.0f} pending dues. Please follow up.')
                    else:
                        messages.success(request, f'{tenant.name} has been successfully checked out from {building.name}.')
                    
                    return redirect('properties:tenant_history', tenant_id=tenant_id)
            else:
                from django.contrib import messages
                messages.error(request, 'Cannot checkout: Please clear pending dues and resolve issues first.')
        
        context = {
            'tenant': tenant,
            'current_occupancy': current_occupancy,
            'building': building,
            'location_type': location_type,
            'location_detail': location_detail,
            'monthly_rent': monthly_rent,
            'all_rents': all_rents[:12],  # Last 12 months
            'pending_rents': pending_rents,
            'pending_months_count': pending_months_count,
            'total_dues': total_dues,
            'month_wise_status': month_wise_status,
            'all_issues': all_issues,
            'open_issues': open_issues,
            'total_rent_paid': total_rent_paid,
            'total_months_stayed': total_months_stayed,
            'months_with_rent': occupancy_rents.count(),
            'can_checkout': can_checkout,
            'checkout_warnings': checkout_warnings,
            'move_in_date': current_occupancy.start_date,
            'records_created': records_created,  # Show if auto-generated
            # Notice Period Information
            'notice_date': notice_date,
            'has_given_notice': has_given_notice,
            'required_notice_days': required_notice_days,
            'days_since_notice': days_since_notice,
            'days_until_eligible': days_until_eligible,
            'is_eligible_for_checkout': is_eligible_for_checkout,
            'expected_checkout_date': expected_checkout_date,
            'notice_reason': notice_reason,
        }
        
        return render(request, 'properties/tenant_checkout.html', context)
        
    except Tenant.DoesNotExist:
        raise Http404("Tenant not found")
    except Exception as e:
        logger.error(f"Error in tenant_checkout: {str(e)}", exc_info=True)
        from django.contrib import messages
        messages.error(request, 'An error occurred while loading checkout page.')
        return redirect('properties:dashboard')


@login_required
@owner_or_manager_required
@handle_errors
def tenant_list(request):
    """Tenant List View - Shows all tenants with their details, location, and rent status"""
    from buildings.access import get_accessible_buildings, get_accessible_building_ids
    
    account = getattr(request, 'account', None)
    if not account and hasattr(request.user, 'account') and request.user.account:
        account = request.user.account
        request.account = account
    
    if not account:
        from django.contrib import messages
        messages.warning(request, 'Your account is not properly configured.')
        return redirect('accounts:profile')
    
    try:
        current_month = timezone.now().date().replace(day=1)
        
        # Get accessible buildings for managers (owners see all)
        accessible_buildings = get_accessible_buildings(request.user)
        accessible_building_ids = get_accessible_building_ids(request.user)
        
        # Get filter parameters
        search_query = request.GET.get('search', '').strip()
        building_filter = request.GET.get('building', '')
        room_filter = request.GET.get('room', '').strip()
        status_filter = request.GET.get('status', '')
        
        # Get accessible buildings for filter dropdown (managers only see accessible buildings)
        all_buildings = accessible_buildings.order_by('name')
        
        # Get all rooms/units for filter dropdown (filtered by building if selected)
        # Ensure building_filter is in accessible buildings
        all_rooms = []
        if building_filter and int(building_filter) in accessible_building_ids:
            # Get rooms from PG units in this building
            pg_rooms = PGRoom.objects.filter(
                unit__building_id=building_filter,
                unit__account=account,
                unit__building_id__in=accessible_building_ids
            ).select_related('unit').order_by('room_number')
            for room in pg_rooms:
                all_rooms.append({
                    'id': f'room_{room.id}',
                    'name': f"Room {room.room_number} ({room.sharing_type}-sharing)",
                    'type': 'PG'
                })
            
            # Get flat units in this building (ensure accessible)
            flat_units = Unit.objects.filter(
                building_id=building_filter,
                account=account,
                unit_type='FLAT',
                building_id__in=accessible_building_ids
            ).order_by('unit_number')
            for unit in flat_units:
                all_rooms.append({
                    'id': f'unit_{unit.id}',
                    'name': f"Unit {unit.unit_number}" + (f" ({unit.bhk_type})" if unit.bhk_type else ""),
                    'type': 'FLAT'
                })
        
        # OPTIMIZED: Get all tenants with their active occupancies
        # Filter by accessible buildings for managers
        # Use a two-step approach to avoid duplicates:
        # 1. First get unique tenant IDs that have active occupancies in accessible buildings
        # 2. Then fetch those tenants with prefetch_related
        
        # Get tenant IDs that have active occupancies in accessible buildings
        accessible_tenant_ids = Tenant.objects.filter(
            account=account
        ).filter(
            Q(occupancies__unit__building_id__in=accessible_building_ids, occupancies__is_active=True) |
            Q(occupancies__bed__room__unit__building_id__in=accessible_building_ids, occupancies__is_active=True)
        ).distinct().values_list('id', flat=True)
        
        # Now get tenants with prefetch - this ensures no duplicates
        tenants_queryset = Tenant.objects.filter(
            account=account,
            id__in=accessible_tenant_ids
        ).prefetch_related(
            Prefetch(
                'occupancies',
                queryset=Occupancy.objects.filter(
                    is_active=True
                ).filter(
                    Q(unit__building_id__in=accessible_building_ids) |
                    Q(bed__room__unit__building_id__in=accessible_building_ids)
                ).select_related(
                    'unit',
                    'unit__building',
                    'bed',
                    'bed__room',
                    'bed__room__unit',
                    'bed__room__unit__building'
                ).order_by('-start_date'),  # Get most recent first
                to_attr='active_occupancies'
            )
        ).order_by('name')
        
        # Apply search filter at database level
        if search_query:
            tenants_queryset = tenants_queryset.filter(
                Q(name__icontains=search_query) |
                Q(phone__icontains=search_query) |
                Q(email__icontains=search_query)
            )
        
        # Apply building filter at database level (ensure it's accessible)
        if building_filter and int(building_filter) in accessible_building_ids:
            # Filter tenant IDs by building
            building_tenant_ids = Tenant.objects.filter(
                account=account
            ).filter(
                Q(occupancies__unit__building_id=building_filter, occupancies__is_active=True) |
                Q(occupancies__bed__room__unit__building_id=building_filter, occupancies__is_active=True)
            ).distinct().values_list('id', flat=True)
            
            tenants_queryset = tenants_queryset.filter(id__in=building_tenant_ids)
        elif building_filter:
            # Building filter provided but not accessible - return empty
            tenants_queryset = tenants_queryset.none()
        
        # Get total count before pagination - filter by accessible buildings
        # Count unique tenants with active occupancies in accessible buildings
        total_tenants_count = Tenant.objects.filter(
            account=account
        ).filter(
            Q(occupancies__unit__building_id__in=accessible_building_ids, occupancies__is_active=True) |
            Q(occupancies__bed__room__unit__building_id__in=accessible_building_ids, occupancies__is_active=True)
        ).distinct().count()
        filtered_count = tenants_queryset.count()
        
        # Pagination for scalability
        paginator = Paginator(tenants_queryset, 20)  # 20 tenants per page
        page = request.GET.get('page', 1)
        try:
            tenants = paginator.page(page)
        except PageNotAnInteger:
            tenants = paginator.page(1)
        except EmptyPage:
            tenants = paginator.page(paginator.num_pages)
        
        # Build tenant data with location and rent info
        # ONLY SHOW TENANTS WITH ACTIVE OCCUPANCIES (currently living)
        # Use a set to track tenant IDs to prevent duplicates
        seen_tenant_ids = set()
        tenants_with_details = []
        
        for tenant in tenants:  # tenants is now a paginated page object
            # Skip if we've already processed this tenant (safety check)
            if tenant.id in seen_tenant_ids:
                continue
            seen_tenant_ids.add(tenant.id)
            
            # Skip tenants without active occupancies
            if not tenant.active_occupancies:
                continue
            
            # Get the most recent active occupancy (first in list since we ordered by -start_date)
            occupancy = tenant.active_occupancies[0]
                
            tenant_data = {
                'tenant': tenant,
                'current_occupancy': None,
                'location': 'Not Assigned',
                'location_type': None,
                'building_id': None,
                'building_name': None,
                'unit_id': None,
                'unit_number': None,
                'room_id': None,
                'room_number': None,
                'bed_number': None,
                'monthly_rent': Decimal('0'),  # Per month rent
                'current_month_rent': None,
                'rent_status': None,
                'rent_paid': Decimal('0'),
                'rent_pending': Decimal('0'),
                'move_in_date': None,
                'has_notice': False,
                'notice_date': None,
            }
            
            # Set current occupancy (already got above)
            tenant_data['current_occupancy'] = occupancy
            tenant_data['move_in_date'] = occupancy.start_date
            tenant_data['monthly_rent'] = occupancy.rent or Decimal('0')
            tenant_data['has_notice'] = occupancy.has_given_notice
            tenant_data['notice_date'] = occupancy.notice_date
                
            # Determine location
            if occupancy.unit:
                # Flat
                tenant_data['location_type'] = 'FLAT'
                tenant_data['building_id'] = occupancy.unit.building.id
                tenant_data['building_name'] = occupancy.unit.building.name
                tenant_data['unit_id'] = occupancy.unit.id
                tenant_data['unit_number'] = occupancy.unit.unit_number
                if occupancy.unit.bhk_type:
                    tenant_data['location'] = f"{occupancy.unit.building.name} - {occupancy.unit.unit_number} ({occupancy.unit.bhk_type})"
                else:
                    tenant_data['location'] = f"{occupancy.unit.building.name} - {occupancy.unit.unit_number}"
            elif occupancy.bed:
                # PG
                tenant_data['location_type'] = 'PG'
                tenant_data['building_id'] = occupancy.bed.room.unit.building.id
                tenant_data['building_name'] = occupancy.bed.room.unit.building.name
                tenant_data['unit_id'] = occupancy.bed.room.unit.id
                tenant_data['unit_number'] = occupancy.bed.room.unit.unit_number
                tenant_data['room_id'] = occupancy.bed.room.id
                tenant_data['room_number'] = occupancy.bed.room.room_number
                tenant_data['bed_number'] = occupancy.bed.bed_number
                tenant_data['location'] = f"{occupancy.bed.room.unit.building.name} - Room {occupancy.bed.room.room_number}, Bed {occupancy.bed.bed_number}"
                
            # Check if this is a secondary tenant in a shared flat (₹0 rent)
            # Check if secondary tenant (co-occupant in flat who is not primary)
            # Use getattr for safety during migration
            is_primary = getattr(occupancy, 'is_primary', True) if (occupancy.unit and occupancy.unit.unit_type == 'FLAT') else False
            is_secondary_tenant = occupancy.unit and not is_primary
            tenant_data['is_secondary_tenant'] = is_secondary_tenant
            tenant_data['is_primary'] = is_primary
            
            if is_secondary_tenant:
                # Secondary tenant in shared flat - doesn't pay separately
                tenant_data['rent_status'] = 'CO_OCCUPANT'
                tenant_data['rent_paid'] = Decimal('0')
                tenant_data['rent_pending'] = Decimal('0')
            else:
                # Get current month rent
                current_rent = Rent.objects.filter(
                    occupancy=occupancy,
                    month=current_month
                ).first()
                
                if current_rent:
                    tenant_data['current_month_rent'] = current_rent
                    tenant_data['rent_paid'] = current_rent.paid_amount
                    tenant_data['rent_pending'] = current_rent.pending_amount
                    tenant_data['rent_status'] = current_rent.status
                else:
                    # No rent record for current month
                    tenant_data['rent_status'] = 'NOT_GENERATED'
                    tenant_data['rent_pending'] = occupancy.rent
            
            # Apply room/unit filter (client-side since it's complex)
            if room_filter:
                if room_filter.startswith('room_'):
                    room_id = int(room_filter.replace('room_', ''))
                    if tenant_data['room_id'] != room_id:
                        continue
                elif room_filter.startswith('unit_'):
                    unit_id = int(room_filter.replace('unit_', ''))
                    if tenant_data['unit_id'] != unit_id or tenant_data['location_type'] != 'FLAT':
                        continue
            
            tenants_with_details.append(tenant_data)
        
        # Statistics (all tenants in list are active now)
        active_tenants = len(tenants_with_details)
        tenants_with_rent_paid = sum(1 for t in tenants_with_details if t['rent_status'] == 'PAID')
        # Exclude CO_OCCUPANT from pending count (they don't pay separately)
        tenants_with_pending_rent = sum(1 for t in tenants_with_details if t['rent_status'] in ['PENDING', 'PARTIAL', 'NOT_GENERATED'])
        
        # Filter by status if provided
        if status_filter:
            if status_filter == 'paid':
                tenants_with_details = [t for t in tenants_with_details if t['rent_status'] == 'PAID']
            elif status_filter == 'pending':
                tenants_with_details = [t for t in tenants_with_details if t['rent_status'] in ['PENDING', 'PARTIAL', 'NOT_GENERATED']]
            elif status_filter == 'active':
                # All are active, but keep for compatibility
                pass
            elif status_filter == 'inactive':
                # No inactive tenants shown anymore
                tenants_with_details = []
        
        context = {
            'tenants_with_details': tenants_with_details,
            'total_tenants': total_tenants_count,
            'filtered_count': filtered_count,
            'active_tenants': active_tenants,
            'tenants_with_rent_paid': tenants_with_rent_paid,
            'tenants_with_pending_rent': tenants_with_pending_rent,
            'current_month': current_month,
            'status_filter': status_filter,
            'search_query': search_query,
            'building_filter': building_filter,
            'room_filter': room_filter,
            'all_buildings': all_buildings,
            'all_rooms': all_rooms,
            'tenants': tenants,  # Paginated queryset
            'paginator': paginator,
        }
        
        return render(request, 'properties/tenant_list.html', context)
        
    except Exception as e:
        logger.error(f"Error in tenant_list view: {str(e)}", exc_info=True)
        from django.contrib import messages
        messages.error(request, 'An error occurred while loading tenants.')
        return redirect('properties:dashboard')


@login_required
@owner_or_manager_required
@handle_errors
def search(request):
    """Global search - OPTIMIZED queries"""
    account = getattr(request, 'account', None)
    if not account and hasattr(request.user, 'account') and request.user.account:
        account = request.user.account
        request.account = account
    
    if not account:
        from django.contrib import messages
        messages.warning(request, 'Your account is not properly configured.')
        return redirect('accounts:profile')
    
    query = request.GET.get('q', '').strip()
    results = {
        'buildings': [],
        'units': [],
        'tenants': [],
        'issues': [],
    }
    
    if query:
        # Get accessible buildings for managers
        from buildings.access import get_accessible_building_ids
        accessible_building_ids = get_accessible_building_ids(request.user)
        
        # OPTIMIZED: Search buildings with select_related - filter by accessible buildings
        results['buildings'] = list(Building.objects.filter(
            account=account,
            id__in=accessible_building_ids,
            name__icontains=query
        ).select_related('account')[:10])
        
        # OPTIMIZED: Search units with select_related - filter by accessible buildings
        results['units'] = list(Unit.objects.filter(
            account=account,
            building_id__in=accessible_building_ids,
            unit_number__icontains=query
        ).select_related('building', 'account')[:10])
        
        # OPTIMIZED: Search tenants with select_related - filter by accessible buildings
        # Only show tenants who have occupancies in accessible buildings
        results['tenants'] = list(Tenant.objects.filter(
            account=account
        ).filter(
            Q(name__icontains=query) | Q(phone__icontains=query) | Q(email__icontains=query)
        ).filter(
            Q(occupancies__unit__building_id__in=accessible_building_ids) |
            Q(occupancies__bed__room__unit__building_id__in=accessible_building_ids)
        ).distinct().select_related('account')[:10])
        
        # OPTIMIZED: Search issues - filter by accessible buildings
        results['issues'] = list(Issue.objects.filter(
            unit__account=account,
            unit__building_id__in=accessible_building_ids
        ).filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )[:10])
    
    context = {
        'query': query,
        'results': results,
        'has_results': any(results.values()),
    }
    
    return render(request, 'properties/search.html', context)


# ==================== FORM VIEWS (Custom Forms instead of Admin) ====================

@login_required
@owner_required
@handle_errors
def add_building(request):
    """Add building form with inline units/rooms (Owner only)"""
    account = getattr(request, 'account', None)
    if not account and hasattr(request.user, 'account') and request.user.account:
        account = request.user.account
        request.account = account
    
    if not account:
        from django.contrib import messages
        messages.warning(request, 'Your account is not properly configured.')
        return redirect('accounts:profile')
    
    # Check property limit before allowing creation
    from common.utils import get_site_settings
    site_settings = get_site_settings()
    max_properties = site_settings.max_properties_per_owner
    
    if max_properties > 0:  # 0 means unlimited
        current_property_count = Building.objects.filter(account=account).count()
        if current_property_count >= max_properties:
            from django.contrib import messages
            messages.error(
                request, 
                f'You have reached the maximum limit of {max_properties} properties. '
                f'Please contact administrator to increase your limit.'
            )
            return redirect('properties:building_list')
    
    if request.method == 'POST':
        form = BuildingForm(request.POST)
        if form.is_valid():
            # Double-check limit before saving (in case of race condition)
            if max_properties > 0:
                current_property_count = Building.objects.filter(account=account).count()
                if current_property_count >= max_properties:
                    from django.contrib import messages
                    messages.error(
                        request, 
                        f'You have reached the maximum limit of {max_properties} properties. '
                        f'Please contact administrator to increase your limit.'
                    )
                    return redirect('properties:building_list')
            
            building = form.save(commit=False)
            building.account = account
            building.save()
            
            from django.contrib import messages
            units_created = 0
            rooms_created = 0
            beds_created = 0
            
            # Create Flat Units
            flat_unit_numbers = request.POST.getlist('flat_unit_number[]')
            flat_bhk_types = request.POST.getlist('flat_bhk_type[]')
            flat_floors = request.POST.getlist('flat_floor[]')
            flat_rents = request.POST.getlist('flat_rent[]')
            flat_deposits = request.POST.getlist('flat_deposit[]')
            
            for i in range(len(flat_unit_numbers)):
                if flat_unit_numbers[i].strip():
                    from units.models import Unit
                    Unit.objects.create(
                        building=building,
                        account=account,
                        unit_number=flat_unit_numbers[i].strip(),
                        bhk_type=flat_bhk_types[i] if i < len(flat_bhk_types) else '1BHK',
                        floor=int(flat_floors[i]) if i < len(flat_floors) and flat_floors[i] else 0,
                        expected_rent=float(flat_rents[i]) if i < len(flat_rents) and flat_rents[i] else 0,
                        deposit=float(flat_deposits[i]) if i < len(flat_deposits) and flat_deposits[i] else 0,
                        status='VACANT'
                    )
                    units_created += 1
            
            # Create PG Units, Rooms, and Beds
            # Each PG row creates: 1 PG Unit + 1 Room + N Beds (based on sharing)
            pg_unit_numbers = request.POST.getlist('pg_unit_number[]')
            pg_floors = request.POST.getlist('pg_floor[]')
            room_numbers = request.POST.getlist('room_number[]')
            sharing_types = request.POST.getlist('sharing_type[]')
            bed_rents = request.POST.getlist('bed_rent[]')
            
            from units.models import Unit as UnitModel, PGRoom, Bed
            
            # Track created PG units to avoid duplicates
            created_pg_units = {}
            
            for i in range(len(pg_unit_numbers)):
                pg_unit_num = pg_unit_numbers[i].strip() if i < len(pg_unit_numbers) else ''
                room_num = room_numbers[i].strip() if i < len(room_numbers) else ''
                
                # Skip if no room number provided
                if not room_num:
                    continue
                
                # Use default PG unit name if not provided
                if not pg_unit_num:
                    pg_unit_num = f"PG-{i+1}"
                
                # Create or get PG Unit
                if pg_unit_num not in created_pg_units:
                    pg_unit = UnitModel.objects.create(
                        building=building,
                        account=account,
                        unit_number=pg_unit_num,
                        unit_type='PG',
                        floor=int(pg_floors[i]) if i < len(pg_floors) and pg_floors[i] else 1,
                        status='VACANT'
                    )
                    created_pg_units[pg_unit_num] = pg_unit
                    units_created += 1
                else:
                    pg_unit = created_pg_units[pg_unit_num]
                
                # Create Room
                sharing = int(sharing_types[i]) if i < len(sharing_types) and sharing_types[i] else 2
                rent_per_bed = float(bed_rents[i]) if i < len(bed_rents) and bed_rents[i] else 0
                
                pg_room = PGRoom.objects.create(
                    unit=pg_unit,
                    room_number=room_num,
                    sharing_type=sharing
                )
                rooms_created += 1
                
                # Create beds based on sharing type (Bed model only has room, bed_number, status)
                for bed_num in range(1, sharing + 1):
                    Bed.objects.create(
                        room=pg_room,
                        bed_number=f"Bed {bed_num}",
                        status='VACANT'
                    )
                    beds_created += 1
                
                # Store expected rent on the PG unit (sum of all bed rents)
                pg_unit.expected_rent = (pg_unit.expected_rent or 0) + (rent_per_bed * sharing)
                pg_unit.save()
            
            # Success message with summary
            if units_created > 0 or rooms_created > 0:
                messages.success(
                    request,
                    f'Property "{building.name}" created successfully! '
                    f'Added {units_created} units, {rooms_created} rooms, {beds_created} beds.'
                )
            else:
                messages.success(request, f'Property "{building.name}" created! You can add units from the property detail page.')
            
            return redirect('properties:building_detail', building_id=building.id)
    else:
        form = BuildingForm()
    
    return render(request, 'properties/forms/building_form.html', {
        'form': form,
        'title': 'Add Property',
        'action': 'Add'
    })


@login_required
@owner_or_manager_required
@handle_errors
def add_unit(request, building_id=None):
    """Add unit form"""
    account = getattr(request, 'account', None)
    if not account and hasattr(request.user, 'account') and request.user.account:
        account = request.user.account
        request.account = account
    
    if not account:
        from django.contrib import messages
        messages.warning(request, 'Your account is not properly configured.')
        return redirect('accounts:profile')
    
    if request.method == 'POST':
        form = UnitForm(request.POST, account=account)
        if form.is_valid():
            unit = form.save(commit=False)
            unit.account = account
            # CRITICAL: Check building access for managers
            from buildings.access import can_access_building
            if not can_access_building(request.user, unit.building):
                from django.contrib import messages
                messages.error(request, 'You don\'t have access to this building.')
                raise PermissionDenied("You don't have access to this building.")
            unit.save()
            from django.contrib import messages
            messages.success(request, f'Unit "{unit.unit_number}" added successfully!')
            if building_id:
                return redirect('properties:building_detail', building_id=building_id)
            return redirect('properties:unit_detail', unit_id=unit.id)
    else:
        form = UnitForm(account=account)
        if building_id:
            try:
                from buildings.access import can_access_building
                building = Building.objects.get(id=building_id, account=account)
                # CRITICAL: Check building access for managers
                if not can_access_building(request.user, building):
                    from django.contrib import messages
                    messages.error(request, 'You don\'t have access to this building.')
                    raise PermissionDenied("You don't have access to this building.")
                form.fields['building'].initial = building
            except Building.DoesNotExist:
                pass
    
    return render(request, 'properties/forms/unit_form.html', {
        'form': form,
        'title': 'Add Unit',
        'action': 'Add',
        'building_id': building_id
    })


@login_required
@owner_or_manager_required
@handle_errors
def add_tenant(request):
    """Add tenant form"""
    account = getattr(request, 'account', None)
    if not account and hasattr(request.user, 'account') and request.user.account:
        account = request.user.account
        request.account = account
    
    if not account:
        from django.contrib import messages
        messages.warning(request, 'Your account is not properly configured.')
        return redirect('accounts:profile')
    
    if request.method == 'POST':
        form = TenantForm(request.POST)
        if form.is_valid():
            tenant = form.save(commit=False)
            tenant.account = account
            tenant.save()
            from django.contrib import messages
            messages.success(request, f'Tenant "{tenant.name}" added successfully!')
            # Check if we should redirect to occupancy form
            if request.GET.get('assign'):
                return redirect('properties:add_occupancy', tenant_id=tenant.id)
            return redirect('properties:tenant_list')
    else:
        form = TenantForm()
    
    return render(request, 'properties/forms/tenant_form.html', {
        'form': form,
        'title': 'Add Tenant',
        'action': 'Add'
    })


@login_required
@owner_or_manager_required
@handle_errors
def add_occupancy(request, tenant_id=None, unit_id=None, bed_id=None):
    """
    Add occupancy form (Assign tenant to unit/bed)
    Uses database-level locking to prevent race conditions
    """
    account = getattr(request, 'account', None)
    if not account and hasattr(request.user, 'account') and request.user.account:
        account = request.user.account
        request.account = account
    
    if not account:
        from django.contrib import messages
        messages.warning(request, 'Your account is not properly configured.')
        return redirect('accounts:profile')
    
    if request.method == 'POST':
        # Check for concurrent editing before processing
        from common.editing_utils import check_editing_session, start_editing_session, end_editing_session
        from django.contrib import messages
        
        resource_id = unit_id or bed_id
        resource_type = 'unit' if unit_id else 'bed'
        
        if resource_id:
            is_being_edited, _, warning_msg = check_editing_session(resource_type, resource_id, request.user)
            if is_being_edited:
                messages.warning(request, warning_msg or 'This resource is currently being edited by another user. Please wait and try again.')
                form = OccupancyForm(account=account, unit_id=unit_id, bed_id=bed_id)
                if tenant_id:
                    try:
                        tenant = Tenant.objects.get(id=tenant_id, account=account)
                        form.fields['tenant'].initial = tenant
                    except Tenant.DoesNotExist:
                        pass
                return render(request, 'properties/forms/occupancy_form.html', {
                    'form': form,
                    'title': 'Assign Tenant',
                    'action': 'Assign',
                    'tenant_id': tenant_id,
                    'unit_id': unit_id,
                    'bed_id': bed_id,
                    'editing_warning': warning_msg,
                })
        
        form = OccupancyForm(request.POST, account=account, unit_id=unit_id, bed_id=bed_id)
        if form.is_valid():
            from django.db import transaction
            
            try:
                # Start editing session
                if resource_id:
                    start_editing_session(request.user, resource_type, resource_id, 'assign', 
                                        ip_address=get_client_ip(request))
                
                # Use atomic transaction with row-level locking
                with transaction.atomic():
                    occupancy = form.save(commit=False)
                    
                    # Validate tenant belongs to account
                    if occupancy.tenant.account != account:
                        messages.error(request, 'Invalid tenant selected.')
                        return render(request, 'properties/forms/occupancy_form.html', {
                            'form': form,
                            'title': 'Assign Tenant',
                            'action': 'Assign',
                            'tenant_id': tenant_id,
                            'unit_id': unit_id,
                            'bed_id': bed_id
                        })
                    
                    # Ensure unit or bed is set based on URL params
                    from buildings.access import can_access_building
                    if unit_id:
                        try:
                            # Lock the unit row to prevent concurrent assignments
                            occupancy.unit = Unit.objects.select_for_update().get(id=unit_id, account=account)
                            # CRITICAL: Check building access for managers
                            if not can_access_building(request.user, occupancy.unit.building):
                                messages.error(request, 'You don\'t have access to this building.')
                                raise PermissionDenied("You don't have access to this building.")
                            occupancy.bed = None
                        except Unit.DoesNotExist:
                            messages.error(request, 'Invalid unit selected.')
                            return render(request, 'properties/forms/occupancy_form.html', {
                                'form': form,
                                'title': 'Assign Tenant',
                                'action': 'Assign',
                                'tenant_id': tenant_id,
                                'unit_id': unit_id,
                                'bed_id': bed_id
                            })
                    elif bed_id:
                        try:
                            # Lock the bed row to prevent concurrent assignments
                            occupancy.bed = Bed.objects.select_for_update().get(id=bed_id, room__unit__account=account)
                            # CRITICAL: Check building access for managers
                            if not can_access_building(request.user, occupancy.bed.room.unit.building):
                                messages.error(request, 'You don\'t have access to this building.')
                                raise PermissionDenied("You don't have access to this building.")
                            occupancy.unit = None
                        except Bed.DoesNotExist:
                            messages.error(request, 'Invalid bed selected.')
                            return render(request, 'properties/forms/occupancy_form.html', {
                                'form': form,
                                'title': 'Assign Tenant',
                                'action': 'Assign',
                                'tenant_id': tenant_id,
                                'unit_id': unit_id,
                                'bed_id': bed_id
                            })
                    
                    # Validate that either unit or bed is set
                    if not occupancy.unit and not occupancy.bed:
                        messages.error(request, 'Please select either a unit (for flat) or bed (for PG).')
                        return render(request, 'properties/forms/occupancy_form.html', {
                            'form': form,
                            'title': 'Assign Tenant',
                            'action': 'Assign',
                            'tenant_id': tenant_id,
                            'unit_id': unit_id,
                            'bed_id': bed_id
                        })
                    
                    # Check for existing active occupancy with row-level locking
                    if occupancy.unit:
                        existing = Occupancy.objects.select_for_update().filter(
                            unit=occupancy.unit, 
                            is_active=True
                        ).exclude(id=occupancy.id if occupancy.id else None).first()
                        if existing:
                            messages.error(
                                request, 
                                f'Unit {occupancy.unit.unit_number} is currently being edited or already occupied. Please retry.'
                            )
                            return render(request, 'properties/forms/occupancy_form.html', {
                                'form': form,
                                'title': 'Assign Tenant',
                                'action': 'Assign',
                                'tenant_id': tenant_id,
                                'unit_id': unit_id,
                                'bed_id': bed_id
                            })
                    elif occupancy.bed:
                        existing = Occupancy.objects.select_for_update().filter(
                            bed=occupancy.bed, 
                            is_active=True
                        ).exclude(id=occupancy.id if occupancy.id else None).first()
                        if existing:
                            messages.error(
                                request, 
                                f'Bed {occupancy.bed.bed_number} is currently being edited or already occupied. Please retry.'
                            )
                            return render(request, 'properties/forms/occupancy_form.html', {
                                'form': form,
                                'title': 'Assign Tenant',
                                'action': 'Assign',
                                'tenant_id': tenant_id,
                                'unit_id': unit_id,
                                'bed_id': bed_id
                            })
                    
                    # For flats: Set is_primary if this is the first occupant
                    if occupancy.unit and occupancy.unit.unit_type == 'FLAT':
                        # Check if there's already a primary occupant
                        existing_primary = Occupancy.objects.filter(
                            unit=occupancy.unit,
                            is_active=True,
                            is_primary=True
                        ).exists()
                        
                        if not existing_primary:
                            # First occupant becomes primary
                            occupancy.is_primary = True
                            # Set rent to flat's expected rent
                            occupancy.rent = occupancy.unit.expected_rent or Decimal('0')
                        else:
                            # Additional occupant is not primary, rent is 0
                            occupancy.is_primary = False
                            occupancy.rent = Decimal('0')
                    
                    # Save occupancy within the transaction
                    occupancy.save()
                    
                    # End editing session
                    if resource_id:
                        end_editing_session(resource_type, resource_id, request.user)
                    
                    messages.success(request, 'Tenant assigned successfully!')
                    
                    # Redirect based on what was assigned
                    if occupancy.unit:
                        return redirect('properties:building_detail', building_id=occupancy.unit.building.id)
                    elif occupancy.bed:
                        return redirect('properties:building_detail', building_id=occupancy.bed.room.unit.building.id)
                    return redirect('properties:tenant_list')
                    
            except Exception as e:
                # End editing session on error
                if resource_id:
                    end_editing_session(resource_type, resource_id, request.user)
                messages.error(request, f'An error occurred while assigning tenant: {str(e)}')
                return render(request, 'properties/forms/occupancy_form.html', {
                    'form': form,
                    'title': 'Assign Tenant',
                    'action': 'Assign',
                    'tenant_id': tenant_id,
                    'unit_id': unit_id,
                    'bed_id': bed_id
                })
    else:
        # Check for concurrent editing on GET request
        from common.editing_utils import check_editing_session
        editing_warning = None
        resource_id = unit_id or bed_id
        resource_type = 'unit' if unit_id else 'bed'
        
        if resource_id:
            is_being_edited, _, warning_msg = check_editing_session(resource_type, resource_id, request.user)
            if is_being_edited:
                editing_warning = warning_msg
        
        form = OccupancyForm(account=account, unit_id=unit_id, bed_id=bed_id)
        if tenant_id:
            try:
                tenant = Tenant.objects.get(id=tenant_id, account=account)
                form.fields['tenant'].initial = tenant
            except Tenant.DoesNotExist:
                pass
    
    return render(request, 'properties/forms/occupancy_form.html', {
        'form': form,
        'title': 'Assign Tenant',
        'action': 'Assign',
        'tenant_id': tenant_id,
        'unit_id': unit_id,
        'bed_id': bed_id,
        'editing_warning': editing_warning,
    })


@login_required
@owner_or_manager_required
@handle_errors
def add_rent(request, occupancy_id=None, unit_id=None, room_id=None):
    """
    Add rent record form
    Supports:
    - Individual occupancy rent
    - Bulk rent for shared flats (splits among multiple occupants)
    - Bulk rent for PG rooms (splits among all beds in room)
    """
    from units.models import PGRoom
    
    account = getattr(request, 'account', None)
    if not account and hasattr(request.user, 'account') and request.user.account:
        account = request.user.account
        request.account = account
    
    if not account:
        from django.contrib import messages
        messages.warning(request, 'Your account is not properly configured.')
        return redirect('accounts:profile')
    
    # Initialize variables
    unit = None
    pg_room = None
    is_pg = False
    shared_occupants = []
    primary_occupancy = None
    building = None
    flat_rent = Decimal('0')
    single_occupancy = None  # For individual bed rent collection
    
    # Check for individual occupancy via query param (for PG bed rent collection)
    occupancy_id_param = request.GET.get('occupancy')
    if occupancy_id_param:
        from buildings.access import can_access_building
        single_occupancy = get_object_or_404(
            Occupancy, 
            id=occupancy_id_param, 
            tenant__account=account,
            is_active=True
        )
        if single_occupancy.bed:
            building = single_occupancy.bed.room.unit.building
            # CRITICAL: Check building access for managers
            if not can_access_building(request.user, building):
                from django.contrib import messages
                messages.error(request, 'You don\'t have access to this building.')
                raise PermissionDenied("You don't have access to this building.")
            is_pg = True
        elif single_occupancy.unit:
            building = single_occupancy.unit.building
            # CRITICAL: Check building access for managers
            if not can_access_building(request.user, building):
                from django.contrib import messages
                messages.error(request, 'You don\'t have access to this building.')
                raise PermissionDenied("You don't have access to this building.")
    
    # FLAT: One rent for whole flat, assigned to primary occupant
    elif unit_id:
        from buildings.access import can_access_building
        unit = get_object_or_404(Unit, id=unit_id, account=account)
        building = unit.building
        # CRITICAL: Check building access for managers
        if not can_access_building(request.user, building):
            from django.contrib import messages
            messages.error(request, 'You don\'t have access to this building.')
            raise PermissionDenied("You don't have access to this building.")
        flat_rent = unit.expected_rent or Decimal('0')
        
        # Get all occupants - find primary or use first one
        # Get all occupants, then sort in Python to avoid SQL issues
        shared_occupants = list(Occupancy.objects.filter(
            unit=unit,
            is_active=True
        ).select_related('tenant').order_by('start_date'))
        
        # Sort by is_primary in Python (primary first)
        try:
            shared_occupants.sort(key=lambda x: (not getattr(x, 'is_primary', False), x.start_date))
        except:
            pass  # If is_primary doesn't exist yet, just use start_date order
        
        if shared_occupants:
            # Find primary occupant, or use first one if none marked as primary
            primary_occupancy = next((occ for occ in shared_occupants if getattr(occ, 'is_primary', False)), None)
            if not primary_occupancy:
                # No primary set, make first one primary
                primary_occupancy = shared_occupants[0]
                primary_occupancy.is_primary = True
                primary_occupancy.rent = flat_rent
                primary_occupancy.save()
                # Set others to 0 rent
                for occ in shared_occupants[1:]:
                    occ.rent = Decimal('0')
                    occ.save()
    
    # PG ROOM: Split rent among beds
    elif room_id:
        from buildings.access import can_access_building
        pg_room = get_object_or_404(PGRoom, id=room_id, unit__account=account)
        building = pg_room.unit.building
        # CRITICAL: Check building access for managers
        if not can_access_building(request.user, building):
            from django.contrib import messages
            messages.error(request, 'You don\'t have access to this building.')
            raise PermissionDenied("You don't have access to this building.")
        is_pg = True
        
        shared_occupants = list(Occupancy.objects.filter(
            bed__room=pg_room,
            is_active=True
        ).select_related('tenant', 'bed'))
    
    if request.method == 'POST':
        if unit_id and request.POST.get('flat_rent_entry') == 'true':
            # FLAT: Create ONE rent record for the primary occupant (whole flat rent)
            try:
                flat_rent_amount = Decimal(request.POST.get('flat_rent', 0))
                month = request.POST.get('month')
                paid_amount = Decimal(request.POST.get('paid_amount', 0))
                paid_date = request.POST.get('paid_date') or None
                notes = request.POST.get('notes', '')
                
                if not primary_occupancy:
                    raise ValueError("No active occupant found in this flat")
                
                # Check if rent already exists for this month
                existing = Rent.objects.filter(
                    occupancy=primary_occupancy,
                    month=month
                ).first()
                
                if existing:
                    from django.contrib import messages
                    messages.warning(request, f'Rent record already exists for {primary_occupancy.tenant.name} for this month.')
                    return redirect('properties:rent_management')
                
                # Ensure we have a primary occupancy
                if not primary_occupancy:
                    # Try to find or create primary
                    try:
                        # Get primary occupant safely
                        try:
                            primary_occupancy = Occupancy.objects.filter(unit=unit, is_active=True, is_primary=True).first()
                        except:
                            # Fallback if is_primary field not available
                            primary_occupancy = Occupancy.objects.filter(unit=unit, is_active=True).first()
                    except Exception:
                        # Fallback if is_primary field not available
                        primary_occupancy = Occupancy.objects.filter(unit=unit, is_active=True).first()
                    if not primary_occupancy:
                        # Make first occupant primary
                        primary_occupancy = shared_occupants[0]
                        try:
                            primary_occupancy.is_primary = True
                        except Exception:
                            pass
                        primary_occupancy.rent = flat_rent_amount
                        primary_occupancy.save()
                
                # Create single rent record for the flat (only for primary tenant)
                Rent.objects.create(
                    occupancy=primary_occupancy,
                    month=month,
                    amount=flat_rent_amount,
                    paid_amount=paid_amount,
                    paid_date=paid_date,
                    status='PAID' if paid_amount >= flat_rent_amount else ('PARTIAL' if paid_amount > 0 else 'PENDING'),
                    notes=f"Flat rent for {unit.unit_number}. {notes}".strip()
                )
                
                from django.contrib import messages
                messages.success(request, f'Rent recorded: ₹{flat_rent_amount} for {unit.unit_number} ({primary_occupancy.tenant.name})')
                return redirect('properties:rent_management')
                
            except Exception as e:
                from django.contrib import messages
                messages.error(request, f'Error creating rent record: {str(e)}')
        
        elif is_pg and request.POST.get('bulk_entry') == 'true':
            # PG: Create rent record for each bed using their stored rent amount
            try:
                month = request.POST.get('month')
                payment_status = request.POST.get('payment_status', 'full')
                paid_date = request.POST.get('paid_date') or None
                notes = request.POST.get('notes', '')
                
                if not shared_occupants:
                    raise ValueError("No occupants in this room")
                
                created_count = 0
                total_amount = Decimal('0')
                
                for occupancy in shared_occupants:
                    existing = Rent.objects.filter(occupancy=occupancy, month=month).first()
                    if not existing:
                        # Use each bed's stored rent amount (from occupancy.rent)
                        bed_rent = occupancy.rent or Decimal('0')
                        
                        # Determine paid amount based on payment status
                        if payment_status == 'full':
                            paid_amount = bed_rent
                            status = 'PAID'
                        elif payment_status == 'pending':
                            paid_amount = Decimal('0')
                            status = 'PENDING'
                            paid_date = None
                        else:  # partial
                            paid_amount = Decimal(request.POST.get('paid_per_person', 0))
                            status = 'PARTIAL' if paid_amount > 0 else 'PENDING'
                        
                        Rent.objects.create(
                            occupancy=occupancy,
                            month=month,
                            amount=bed_rent,
                            paid_amount=paid_amount,
                            paid_date=paid_date if paid_amount > 0 else None,
                            status=status,
                            notes=f"PG Room {pg_room.room_number} - {occupancy.bed.bed_number}. {notes}".strip()
                        )
                        created_count += 1
                        total_amount += bed_rent
                
                from django.contrib import messages
                messages.success(request, f'Rent records created for {created_count} beds! Total: ₹{total_amount:.0f}')
                return redirect('properties:rent_management')
                
            except Exception as e:
                from django.contrib import messages
                messages.error(request, f'Error creating rent records: {str(e)}')
        elif single_occupancy and request.POST.get('single_bed_rent') == 'true':
            # INDIVIDUAL BED: Create rent for single bed occupancy
            try:
                month = request.POST.get('month')
                paid_amount = Decimal(request.POST.get('paid_amount', 0))
                paid_date = request.POST.get('paid_date') or None
                notes = request.POST.get('notes', '')
                payment_proof = request.FILES.get('payment_proof')
                
                # Check if rent already exists for this month
                existing = Rent.objects.filter(
                    occupancy=single_occupancy,
                    month=month
                ).first()
                
                if existing:
                    from django.contrib import messages
                    messages.warning(request, f'Rent record already exists for {single_occupancy.tenant.name} for this month.')
                    return redirect('properties:rent_management')
                
                bed_rent = single_occupancy.rent or Decimal('0')
                
                rent = Rent.objects.create(
                    occupancy=single_occupancy,
                    month=month,
                    amount=bed_rent,
                    paid_amount=paid_amount,
                    paid_date=paid_date if paid_amount > 0 else None,
                    status='PAID' if paid_amount >= bed_rent else ('PARTIAL' if paid_amount > 0 else 'PENDING'),
                    notes=f"PG Bed {single_occupancy.bed.bed_number}. {notes}".strip()
                )
                
                # Handle payment proof upload
                if payment_proof:
                    rent.payment_proof = payment_proof
                    rent.save()
                
                from django.contrib import messages
                messages.success(request, f'Rent recorded: ₹{bed_rent} for {single_occupancy.tenant.name}')
                return redirect('properties:rent_management')
                
            except Exception as e:
                from django.contrib import messages
                messages.error(request, f'Error creating rent record: {str(e)}')
        else:
            # Regular single occupancy rent entry
            form = RentForm(request.POST, request.FILES, account=account, occupancy_id=occupancy_id)
            if form.is_valid():
                rent = form.save()
                from django.contrib import messages
                messages.success(request, 'Rent record added successfully!')
                return redirect('properties:rent_management')
    else:
        form = RentForm(account=account, occupancy_id=occupancy_id)
        form.fields['month'].initial = timezone.now().replace(day=1).date()
    
    # Calculate totals for PG
    total_rent = Decimal('0')
    per_person_rent = Decimal('0')
    
    if is_pg and shared_occupants:
        total_rent = sum(occ.rent for occ in shared_occupants)
        per_person_rent = total_rent / len(shared_occupants) if shared_occupants else Decimal('0')
    
    # Determine form type
    is_flat_rent = unit_id is not None and shared_occupants
    is_single_bed = single_occupancy is not None
    
    # Title based on context
    if is_single_bed:
        title = f'Collect Rent - {single_occupancy.tenant.name}'
    elif is_flat_rent:
        title = 'Collect Flat Rent'
    elif is_pg:
        title = 'Collect Room Rent'
    else:
        title = 'Record Payment'
    
    context = {
        'form': form,
        'title': title,
        'action': 'Add',
        'is_flat_rent': is_flat_rent,  # FLAT: One rent for whole flat
        'is_pg_room': is_pg and not is_single_bed,  # PG Room: Split among beds
        'is_single_bed': is_single_bed,  # Single bed rent
        'single_occupancy': single_occupancy,
        'shared_occupants': shared_occupants,
        'primary_occupancy': primary_occupancy,
        'unit': unit,
        'pg_room': pg_room,
        'building': building,
        'flat_rent': flat_rent,        # For flats: expected rent of unit
        'total_rent': total_rent,      # For PG: sum of bed rents
        'per_person_rent': per_person_rent,
        'occupant_count': len(shared_occupants) if shared_occupants else 0,
    }
    
    return render(request, 'properties/forms/rent_form.html', context)


@login_required
@owner_or_manager_required
@handle_errors
def edit_rent(request, rent_id):
    """Edit rent record form"""
    account = getattr(request, 'account', None)
    if not account and hasattr(request.user, 'account') and request.user.account:
        account = request.user.account
        request.account = account
    
    if not account:
        from django.contrib import messages
        messages.warning(request, 'Your account is not properly configured.')
        return redirect('accounts:profile')
    
    try:
        # Get rent record and validate it belongs to user's account
        rent = Rent.objects.select_related(
            'occupancy',
            'occupancy__tenant',
            'occupancy__unit',
            'occupancy__unit__building',
            'occupancy__bed',
            'occupancy__bed__room',
            'occupancy__bed__room__unit',
            'occupancy__bed__room__unit__building'
        ).get(id=rent_id, occupancy__tenant__account=account)
        
        # CRITICAL: Check building access for managers
        from buildings.access import can_access_building
        building_to_check = rent.occupancy.unit.building if rent.occupancy.unit else rent.occupancy.bed.room.unit.building
        if not can_access_building(request.user, building_to_check):
            from django.contrib import messages
            messages.error(request, 'You don\'t have access to this building.')
            raise PermissionDenied("You don't have access to this building.")
        
        if request.method == 'POST':
            form = RentForm(request.POST, request.FILES, account=account, instance=rent)
            if form.is_valid():
                rent = form.save()
                from django.contrib import messages
                messages.success(request, f'Rent record updated successfully for {rent.occupancy.tenant.name}!')
                return redirect('properties:rent_management')
        else:
            form = RentForm(account=account, instance=rent)
        
        # Prepare context with rent details
        context = {
            'form': form,
            'title': 'Edit Payment Record',
            'action': 'Update',
            'rent': rent,
            'tenant': rent.occupancy.tenant,
            'building': rent.occupancy.unit.building if rent.occupancy.unit else rent.occupancy.bed.room.unit.building,
            'unit_number': rent.occupancy.unit.unit_number if rent.occupancy.unit else rent.occupancy.bed.room.unit.unit_number,
            'is_edit': True,
            'is_shared_flat': False,  # Never show shared flat form when editing
        }
        
        return render(request, 'properties/forms/rent_form.html', context)
        
    except Rent.DoesNotExist:
        from django.contrib import messages
        messages.error(request, 'Rent record not found or you do not have permission to edit it.')
        return redirect('properties:rent_management')


@login_required
@owner_or_manager_required
@handle_errors
def add_issue(request, unit_id=None):
    """Add issue form"""
    account = getattr(request, 'account', None)
    if not account and hasattr(request.user, 'account') and request.user.account:
        account = request.user.account
        request.account = account
    
    if not account:
        from django.contrib import messages
        messages.warning(request, 'Your account is not properly configured.')
        return redirect('accounts:profile')
    
    if request.method == 'POST':
        form = IssueForm(request.POST, account=account, unit_id=unit_id)
        if form.is_valid():
            issue = form.save(commit=False)
            # Validate unit belongs to account
            if issue.unit.account != account:
                from django.contrib import messages
                messages.error(request, 'Invalid unit selected.')
                return redirect('properties:add_issue', unit_id=unit_id)
            issue.save()
            from django.contrib import messages
            messages.success(request, 'Issue reported successfully!')
            if unit_id:
                return redirect('properties:unit_detail', unit_id=unit_id)
            return redirect('properties:issue_list')
    else:
        form = IssueForm(account=account, unit_id=unit_id)
    
    return render(request, 'properties/forms/issue_form.html', {
        'form': form,
        'title': 'Report Issue',
        'action': 'Report',
        'unit_id': unit_id
    })


# ============================================================================
# TEAM MANAGEMENT (OWNER ONLY)
# ============================================================================

@login_required
@owner_required
@handle_errors
def team_management(request):
    """Team management dashboard - List all managers (Owner only)"""
    from users.models import User
    
    account = request.user.account
    
    # Get all managers for this account
    managers = User.objects.filter(
        account=account,
        role='MANAGER'
    ).prefetch_related('building_accesses__building').order_by('username')
    
    # Get all buildings for this account
    all_buildings = Building.objects.filter(account=account).order_by('name')
    
    # Build manager data with access info
    manager_list = []
    for manager in managers:
        accesses = list(manager.building_accesses.all())
        manager_list.append({
            'user': manager,
            'building_accesses': accesses,
            'access_count': len(accesses),
            'total_buildings': all_buildings.count(),
        })
    
    context = {
        'managers': manager_list,
        'total_managers': managers.count(),
        'all_buildings': all_buildings,
        'owner': request.user,
    }
    
    return render(request, 'properties/team_management.html', context)


@login_required
@owner_required
@handle_errors
def add_manager(request):
    """Add a new manager (Owner only)"""
    from users.models import User
    from django.contrib.auth.hashers import make_password
    from common.utils import get_site_settings
    
    account = request.user.account
    all_buildings = Building.objects.filter(account=account).order_by('name')
    
    # Check manager limit before allowing creation
    site_settings = get_site_settings()
    max_managers = site_settings.max_managers_per_owner
    
    if max_managers > 0:  # 0 means unlimited
        current_manager_count = User.objects.filter(account=account, role='MANAGER').count()
        if current_manager_count >= max_managers:
            messages.error(
                request, 
                f'You have reached the maximum limit of {max_managers} managers. '
                f'Please contact administrator to increase your limit.'
            )
            return redirect('properties:team_management')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        selected_buildings = request.POST.getlist('buildings')
        
        errors = []
        
        # Validation
        if not username:
            errors.append('Username is required')
        elif User.objects.filter(username=username).exists():
            errors.append('Username already exists')
        
        if not password:
            errors.append('Password is required')
        elif len(password) < 6:
            errors.append('Password must be at least 6 characters')
        elif password != confirm_password:
            errors.append('Passwords do not match')
        
        # Double-check manager limit before creating (prevent race condition)
        if max_managers > 0:
            current_manager_count = User.objects.filter(account=account, role='MANAGER').count()
            if current_manager_count >= max_managers:
                errors.append(f'You have reached the maximum limit of {max_managers} managers.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                with transaction.atomic():
                    # Create the manager user
                    manager = User.objects.create(
                        username=username,
                        password=make_password(password),
                        account=account,
                        role='MANAGER',
                        phone=phone,
                        email=email,
                    )
                    
                    # Grant building access
                    from buildings.models import BuildingAccess
                    for building_id in selected_buildings:
                        try:
                            building = Building.objects.get(id=building_id, account=account)
                            BuildingAccess.objects.create(
                                user=manager,
                                building=building,
                                created_by=request.user
                            )
                        except Building.DoesNotExist:
                            pass
                    
                    messages.success(request, f'Manager "{username}" created successfully with access to {len(selected_buildings)} building(s)!')
                    return redirect('properties:team_management')
                    
            except Exception as e:
                logger.error(f"Error creating manager: {str(e)}", exc_info=True)
                messages.error(request, f'Error creating manager: {str(e)}')
    
    context = {
        'all_buildings': all_buildings,
        'title': 'Add Manager',
    }
    
    return render(request, 'properties/forms/manager_form.html', context)


@login_required
@owner_required
@handle_errors
def manager_detail(request, manager_id):
    """View manager details and their building access"""
    from users.models import User
    from buildings.models import BuildingAccess
    
    account = request.user.account
    
    try:
        manager = User.objects.get(id=manager_id, account=account, role='MANAGER')
    except User.DoesNotExist:
        messages.error(request, 'Manager not found.')
        return redirect('properties:team_management')
    
    # Get buildings with access status
    all_buildings = Building.objects.filter(account=account).order_by('name')
    access_ids = set(BuildingAccess.objects.filter(user=manager).values_list('building_id', flat=True))
    
    buildings_with_access = []
    for building in all_buildings:
        buildings_with_access.append({
            'building': building,
            'has_access': building.id in access_ids
        })
    
    # Get activity stats (rent collections, issues resolved, etc.)
    # This could be expanded based on audit logging
    
    context = {
        'manager': manager,
        'buildings_with_access': buildings_with_access,
        'access_count': len(access_ids),
        'total_buildings': all_buildings.count(),
    }
    
    return render(request, 'properties/manager_detail.html', context)


@login_required
@owner_required
@handle_errors
def remove_manager(request, manager_id):
    """Remove a manager (Owner only)"""
    from users.models import User
    
    account = request.user.account
    
    try:
        manager = User.objects.get(id=manager_id, account=account, role='MANAGER')
    except User.DoesNotExist:
        messages.error(request, 'Manager not found.')
        return redirect('properties:team_management')
    
    if request.method == 'POST':
        confirm = request.POST.get('confirm')
        if confirm == 'yes':
            username = manager.username
            manager.delete()
            messages.success(request, f'Manager "{username}" has been removed.')
            return redirect('properties:team_management')
    
    context = {
        'manager': manager,
    }
    
    return render(request, 'properties/confirm_remove_manager.html', context)


@login_required
@owner_required
@handle_errors
def manage_building_access(request, manager_id):
    """Manage building access for a manager (Owner only)"""
    from users.models import User
    from buildings.models import BuildingAccess
    
    account = request.user.account
    
    try:
        manager = User.objects.get(id=manager_id, account=account, role='MANAGER')
    except User.DoesNotExist:
        messages.error(request, 'Manager not found.')
        return redirect('properties:team_management')
    
    all_buildings = Building.objects.filter(account=account).order_by('name')
    current_access = set(BuildingAccess.objects.filter(user=manager).values_list('building_id', flat=True))
    
    if request.method == 'POST':
        selected_buildings = set(int(b) for b in request.POST.getlist('buildings'))
        
        with transaction.atomic():
            # Revoke access for unselected buildings
            to_revoke = current_access - selected_buildings
            BuildingAccess.objects.filter(user=manager, building_id__in=to_revoke).delete()
            
            # Grant access for newly selected buildings
            to_grant = selected_buildings - current_access
            for building_id in to_grant:
                try:
                    building = Building.objects.get(id=building_id, account=account)
                    BuildingAccess.objects.create(
                        user=manager,
                        building=building,
                        created_by=request.user
                    )
                except Building.DoesNotExist:
                    pass
                except Exception:
                    pass  # Ignore if already exists
            
            messages.success(request, f'Building access updated for {manager.username}!')
            return redirect('properties:manager_detail', manager_id=manager_id)
    
    buildings_with_access = []
    for building in all_buildings:
        buildings_with_access.append({
            'building': building,
            'has_access': building.id in current_access
        })
    
    context = {
        'manager': manager,
        'buildings_with_access': buildings_with_access,
    }
    
    return render(request, 'properties/forms/building_access_form.html', context)


@login_required
@owner_or_manager_required
@handle_errors
def revenue_dashboard(request):
    """Revenue Analytics Dashboard - Shows financial insights"""
    from buildings.access import get_accessible_buildings, get_accessible_building_ids
    from django.db.models.functions import TruncMonth, ExtractYear, ExtractMonth
    from collections import defaultdict
    import json
    
    accessible_building_ids = get_accessible_building_ids(request.user)
    accessible_buildings = get_accessible_buildings(request.user)
    
    today = timezone.now().date()
    current_month = today.replace(day=1)
    
    # Calculate date ranges
    # Last 12 months for monthly trend
    twelve_months_ago = (current_month - timedelta(days=365)).replace(day=1)
    # Current year and last year for comparison
    current_year = today.year
    last_year = current_year - 1
    
    # ===== MONTHLY REVENUE TREND (Last 12 Months) =====
    # Include both unit-based and bed-based occupancies
    monthly_data = Rent.objects.filter(
        Q(occupancy__unit__building_id__in=accessible_building_ids) |
        Q(occupancy__bed__room__unit__building_id__in=accessible_building_ids),
        month__gte=twelve_months_ago,
        month__lte=current_month
    ).annotate(
        rent_month=TruncMonth('month')
    ).values('rent_month').annotate(
        total_expected=Sum('amount'),
        total_collected=Sum('paid_amount'),
        paid_count=Count('id', filter=Q(status='PAID')),
        partial_count=Count('id', filter=Q(status='PARTIAL')),
        pending_count=Count('id', filter=Q(status='PENDING')),
        total_count=Count('id')
    ).order_by('rent_month')
    
    # Format for chart
    month_labels = []
    expected_data = []
    collected_data = []
    collection_rates = []
    
    for item in monthly_data:
        if item['rent_month']:
            month_labels.append(item['rent_month'].strftime('%b %Y'))
            expected = float(item['total_expected'] or 0)
            collected = float(item['total_collected'] or 0)
            expected_data.append(expected)
            collected_data.append(collected)
            rate = round((collected / expected * 100) if expected > 0 else 0, 1)
            collection_rates.append(rate)
    
    # ===== YEAR-OVER-YEAR COMPARISON =====
    # Include both unit-based and bed-based occupancies
    yearly_stats = Rent.objects.filter(
        Q(occupancy__unit__building_id__in=accessible_building_ids) |
        Q(occupancy__bed__room__unit__building_id__in=accessible_building_ids),
        month__year__in=[current_year, last_year]
    ).annotate(
        year=ExtractYear('month')
    ).values('year').annotate(
        total_expected=Sum('amount'),
        total_collected=Sum('paid_amount'),
        total_records=Count('id')
    ).order_by('year')
    
    yearly_comparison = {last_year: {'expected': 0, 'collected': 0}, current_year: {'expected': 0, 'collected': 0}}
    for item in yearly_stats:
        year = item['year']
        if year in yearly_comparison:
            yearly_comparison[year]['expected'] = float(item['total_expected'] or 0)
            yearly_comparison[year]['collected'] = float(item['total_collected'] or 0)
    
    # Calculate YoY growth
    last_year_collected = yearly_comparison[last_year]['collected']
    current_year_collected = yearly_comparison[current_year]['collected']
    yoy_growth = round(((current_year_collected - last_year_collected) / last_year_collected * 100) if last_year_collected > 0 else 0, 1)
    
    # ===== PROPERTY-WISE REVENUE =====
    # Get revenue from unit-based occupancies
    unit_revenue = Rent.objects.filter(
        occupancy__unit__building_id__in=accessible_building_ids,
        month__year=current_year
    ).values(
        'occupancy__unit__building__id',
        'occupancy__unit__building__name',
        'occupancy__unit__unit_type'
    ).annotate(
        total_expected=Sum('amount'),
        total_collected=Sum('paid_amount'),
        pending_amount=Sum('amount') - Sum('paid_amount'),
        total_tenants=Count('occupancy__tenant', distinct=True)
    ).order_by('-total_collected')
    
    # Get revenue from bed-based occupancies (PG)
    bed_revenue = Rent.objects.filter(
        occupancy__bed__room__unit__building_id__in=accessible_building_ids,
        month__year=current_year
    ).values(
        'occupancy__bed__room__unit__building__id',
        'occupancy__bed__room__unit__building__name'
    ).annotate(
        total_expected=Sum('amount'),
        total_collected=Sum('paid_amount'),
        pending_amount=Sum('amount') - Sum('paid_amount'),
        total_tenants=Count('occupancy__tenant', distinct=True)
    ).order_by('-total_collected')
    
    # Combine both revenue sources
    property_data = []
    property_labels = []
    property_collected = []
    property_pending = []
    
    # Track buildings already processed
    processed_buildings = set()
    
    for item in unit_revenue:
        building_id = item['occupancy__unit__building__id']
        if building_id in processed_buildings:
            continue
        processed_buildings.add(building_id)
        
        expected = float(item['total_expected'] or 0)
        collected = float(item['total_collected'] or 0)
        pending = float(item['pending_amount'] or 0)
        rate = round((collected / expected * 100) if expected > 0 else 0, 1)
        unit_type = item.get('occupancy__unit__unit_type', 'FLAT')
        
        property_data.append({
            'id': building_id,
            'name': item['occupancy__unit__building__name'],
            'type': 'PG' if unit_type == 'PG' else 'Flat',
            'expected': expected,
            'collected': collected,
            'pending': pending,
            'rate': rate,
            'tenants': item['total_tenants']
        })
        property_labels.append(item['occupancy__unit__building__name'][:15])
        property_collected.append(collected)
        property_pending.append(pending)
    
    for item in bed_revenue:
        building_id = item['occupancy__bed__room__unit__building__id']
        if building_id in processed_buildings:
            continue
        processed_buildings.add(building_id)
        
        expected = float(item['total_expected'] or 0)
        collected = float(item['total_collected'] or 0)
        pending = float(item['pending_amount'] or 0)
        rate = round((collected / expected * 100) if expected > 0 else 0, 1)
        
        property_data.append({
            'id': building_id,
            'name': item['occupancy__bed__room__unit__building__name'],
            'type': 'PG',
            'expected': expected,
            'collected': collected,
            'pending': pending,
            'rate': rate,
            'tenants': item['total_tenants']
        })
        property_labels.append(item['occupancy__bed__room__unit__building__name'][:15])
        property_collected.append(collected)
        property_pending.append(pending)
    
    # Sort by collected amount
    property_data.sort(key=lambda x: x['collected'], reverse=True)
    
    # ===== CURRENT MONTH STATS =====
    # Include both unit-based and bed-based occupancies
    current_month_stats = Rent.objects.filter(
        Q(occupancy__unit__building_id__in=accessible_building_ids) |
        Q(occupancy__bed__room__unit__building_id__in=accessible_building_ids),
        month=current_month
    ).aggregate(
        total_expected=Sum('amount'),
        total_collected=Sum('paid_amount'),
        paid_count=Count('id', filter=Q(status='PAID')),
        partial_count=Count('id', filter=Q(status='PARTIAL')),
        pending_count=Count('id', filter=Q(status='PENDING')),
        total_count=Count('id')
    )
    
    current_expected = float(current_month_stats['total_expected'] or 0)
    current_collected = float(current_month_stats['total_collected'] or 0)
    current_pending = current_expected - current_collected
    current_rate = round((current_collected / current_expected * 100) if current_expected > 0 else 0, 1)
    
    # ===== OVERALL STATS =====
    # Include both unit-based and bed-based occupancies
    overall_stats = Rent.objects.filter(
        Q(occupancy__unit__building_id__in=accessible_building_ids) |
        Q(occupancy__bed__room__unit__building_id__in=accessible_building_ids)
    ).aggregate(
        total_expected=Sum('amount'),
        total_collected=Sum('paid_amount'),
        total_records=Count('id')
    )
    
    total_revenue = float(overall_stats['total_collected'] or 0)
    total_pending = float((overall_stats['total_expected'] or 0) - (overall_stats['total_collected'] or 0))
    overall_rate = round((total_revenue / float(overall_stats['total_expected'] or 1) * 100), 1)
    
    # ===== TOP PERFORMING PROPERTIES (by collection rate) =====
    top_properties = sorted(property_data, key=lambda x: x['rate'], reverse=True)[:5]
    
    # ===== PENDING DUES BY TENANT =====
    # Include both unit-based and bed-based occupancies
    # Get unit-based pending dues
    unit_pending = Rent.objects.filter(
        occupancy__unit__building_id__in=accessible_building_ids,
        status__in=['PENDING', 'PARTIAL']
    ).values(
        'occupancy__tenant__id',
        'occupancy__tenant__name',
        'occupancy__unit__building__name'
    ).annotate(
        total_due=Sum('amount') - Sum('paid_amount'),
        months_pending=Count('id')
    )
    
    # Get bed-based pending dues
    bed_pending = Rent.objects.filter(
        occupancy__bed__room__unit__building_id__in=accessible_building_ids,
        status__in=['PENDING', 'PARTIAL']
    ).values(
        'occupancy__tenant__id',
        'occupancy__tenant__name',
        'occupancy__bed__room__unit__building__name'
    ).annotate(
        total_due=Sum('amount') - Sum('paid_amount'),
        months_pending=Count('id')
    )
    
    # Combine and aggregate by tenant
    tenant_dues = defaultdict(lambda: {'name': '', 'building': '', 'total_due': 0, 'months_pending': 0})
    
    for item in unit_pending:
        tenant_id = item['occupancy__tenant__id']
        tenant_dues[tenant_id]['name'] = item['occupancy__tenant__name']
        tenant_dues[tenant_id]['building'] = item['occupancy__unit__building__name']
        tenant_dues[tenant_id]['total_due'] += float(item['total_due'] or 0)
        tenant_dues[tenant_id]['months_pending'] += item['months_pending']
    
    for item in bed_pending:
        tenant_id = item['occupancy__tenant__id']
        if tenant_id not in tenant_dues:
            tenant_dues[tenant_id]['name'] = item['occupancy__tenant__name']
            tenant_dues[tenant_id]['building'] = item['occupancy__bed__room__unit__building__name']
        tenant_dues[tenant_id]['total_due'] += float(item['total_due'] or 0)
        tenant_dues[tenant_id]['months_pending'] += item['months_pending']
    
    # Convert to list and sort
    pending_dues = [
        {
            'occupancy__tenant__id': tid,
            'occupancy__tenant__name': data['name'],
            'occupancy__unit__building__name': data['building'],
            'total_due': data['total_due'],
            'months_pending': data['months_pending']
        }
        for tid, data in tenant_dues.items()
    ]
    pending_dues.sort(key=lambda x: x['total_due'], reverse=True)
    pending_dues = pending_dues[:10]
    
    # ===== MONTHLY BREAKDOWN FOR CURRENT YEAR =====
    # Include both unit-based and bed-based occupancies
    monthly_breakdown = Rent.objects.filter(
        Q(occupancy__unit__building_id__in=accessible_building_ids) |
        Q(occupancy__bed__room__unit__building_id__in=accessible_building_ids),
        month__year=current_year
    ).annotate(
        month_num=ExtractMonth('month')
    ).values('month_num').annotate(
        expected=Sum('amount'),
        collected=Sum('paid_amount')
    ).order_by('month_num')
    
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    breakdown_labels = []
    breakdown_expected = []
    breakdown_collected = []
    
    # Initialize all months with 0
    monthly_dict = {i: {'expected': 0, 'collected': 0} for i in range(1, 13)}
    for item in monthly_breakdown:
        month_num = item['month_num']
        if month_num:
            monthly_dict[month_num]['expected'] = float(item['expected'] or 0)
            monthly_dict[month_num]['collected'] = float(item['collected'] or 0)
    
    for i in range(1, 13):
        breakdown_labels.append(month_names[i-1])
        breakdown_expected.append(monthly_dict[i]['expected'])
        breakdown_collected.append(monthly_dict[i]['collected'])
    
    context = {
        'page_title': 'Revenue Dashboard',
        
        # Summary stats
        'total_revenue': total_revenue,
        'total_pending': total_pending,
        'overall_collection_rate': overall_rate,
        'yoy_growth': yoy_growth,
        
        # Current month
        'current_month': current_month,
        'current_expected': current_expected,
        'current_collected': current_collected,
        'current_pending': current_pending,
        'current_rate': current_rate,
        'current_paid_count': current_month_stats['paid_count'] or 0,
        'current_partial_count': current_month_stats['partial_count'] or 0,
        'current_pending_count': current_month_stats['pending_count'] or 0,
        
        # Charts data (JSON)
        'month_labels': json.dumps(month_labels),
        'expected_data': json.dumps(expected_data),
        'collected_data': json.dumps(collected_data),
        'collection_rates': json.dumps(collection_rates),
        
        'property_labels': json.dumps(property_labels),
        'property_collected': json.dumps(property_collected),
        'property_pending': json.dumps(property_pending),
        
        'breakdown_labels': json.dumps(breakdown_labels),
        'breakdown_expected': json.dumps(breakdown_expected),
        'breakdown_collected': json.dumps(breakdown_collected),
        
        # Yearly comparison
        'current_year': current_year,
        'last_year': last_year,
        'yearly_comparison': yearly_comparison,
        
        # Property data
        'property_data': property_data,
        'top_properties': top_properties,
        
        # Pending dues
        'pending_dues': list(pending_dues),
        
        # Total buildings
        'total_buildings': accessible_buildings.count(),
    }
    
    return render(request, 'properties/revenue_dashboard.html', context)


@login_required
@owner_or_manager_required
@handle_errors
def give_notice(request, tenant_id):
    """Record when a tenant gives notice to vacate"""
    account = request.user.account
    
    try:
        tenant = Tenant.objects.get(id=tenant_id, account=account)
        
        # Get current active occupancy
        current_occupancy = Occupancy.objects.filter(
            tenant=tenant,
            is_active=True
        ).select_related(
            'unit', 'unit__building',
            'bed', 'bed__room', 'bed__room__unit', 'bed__room__unit__building'
        ).first()
        
        if not current_occupancy:
            messages.warning(request, f'{tenant.name} does not have an active occupancy.')
            return redirect('properties:tenant_list')
        
        # Get building info
        if current_occupancy.unit:
            building = current_occupancy.unit.building
            location_detail = f"Unit {current_occupancy.unit.unit_number}"
        else:
            building = current_occupancy.bed.room.unit.building
            location_detail = f"Room {current_occupancy.bed.room.room_number}, Bed {current_occupancy.bed.bed_number}"
        
        required_notice_days = building.notice_period_days
        
        if request.method == 'POST':
            notice_date_str = request.POST.get('notice_date')
            notice_reason = request.POST.get('notice_reason', '').strip()
            
            if notice_date_str:
                from datetime import datetime
                notice_date = datetime.strptime(notice_date_str, '%Y-%m-%d').date()
                
                # Calculate expected checkout date
                expected_checkout = notice_date + timedelta(days=required_notice_days)
                
                # Update occupancy
                current_occupancy.notice_date = notice_date
                current_occupancy.expected_checkout_date = expected_checkout
                current_occupancy.notice_reason = notice_reason
                current_occupancy.save()
                
                messages.success(
                    request, 
                    f'Notice recorded for {tenant.name}. Expected checkout: {expected_checkout.strftime("%d %b %Y")}'
                )
                return redirect('properties:tenant_checkout', tenant_id=tenant_id)
            else:
                messages.error(request, 'Please select a notice date.')
        
        # Check if already given notice
        if current_occupancy.notice_date:
            messages.info(request, f'{tenant.name} has already given notice on {current_occupancy.notice_date.strftime("%d %b %Y")}.')
            return redirect('properties:tenant_checkout', tenant_id=tenant_id)
        
        context = {
            'tenant': tenant,
            'current_occupancy': current_occupancy,
            'building': building,
            'location_detail': location_detail,
            'required_notice_days': required_notice_days,
            'today': timezone.now().date(),
        }
        
        return render(request, 'properties/forms/give_notice_form.html', context)
        
    except Tenant.DoesNotExist:
        raise Http404("Tenant not found")


@login_required
@owner_or_manager_required
@handle_errors
def cancel_notice(request, tenant_id):
    """Cancel a previously given notice"""
    account = request.user.account
    
    try:
        tenant = Tenant.objects.get(id=tenant_id, account=account)
        
        current_occupancy = Occupancy.objects.filter(
            tenant=tenant,
            is_active=True
        ).first()
        
        if not current_occupancy:
            messages.warning(request, f'{tenant.name} does not have an active occupancy.')
            return redirect('properties:tenant_list')
        
        if not current_occupancy.notice_date:
            messages.info(request, f'{tenant.name} has not given notice.')
            return redirect('properties:tenant_history', tenant_id=tenant_id)
        
        if request.method == 'POST':
            # Clear notice information
            current_occupancy.notice_date = None
            current_occupancy.expected_checkout_date = None
            current_occupancy.notice_reason = ''
            current_occupancy.save()
            
            messages.success(request, f'Notice cancelled for {tenant.name}.')
            return redirect('properties:tenant_history', tenant_id=tenant_id)
        
        context = {
            'tenant': tenant,
            'current_occupancy': current_occupancy,
        }
        
        return render(request, 'properties/forms/cancel_notice_form.html', context)
        
    except Tenant.DoesNotExist:
        raise Http404("Tenant not found")


@login_required
@owner_or_manager_required
@handle_errors
def notice_list(request):
    """View all tenants who have given notice"""
    from buildings.access import get_accessible_building_ids
    
    account = request.user.account
    accessible_building_ids = get_accessible_building_ids(request.user)
    
    today = timezone.now().date()
    
    # Get all active occupancies with notice
    occupancies_with_notice = Occupancy.objects.filter(
        tenant__account=account,
        is_active=True,
        notice_date__isnull=False
    ).filter(
        Q(unit__building_id__in=accessible_building_ids) |
        Q(bed__room__unit__building_id__in=accessible_building_ids)
    ).select_related(
        'tenant',
        'unit', 'unit__building',
        'bed', 'bed__room', 'bed__room__unit', 'bed__room__unit__building'
    ).order_by('expected_checkout_date')
    
    # Categorize by status
    eligible_for_checkout = []
    in_notice_period = []
    overdue_checkout = []
    
    for occ in occupancies_with_notice:
        # Get building info
        if occ.unit:
            building = occ.unit.building
            location = f"{building.name} - Unit {occ.unit.unit_number}"
        else:
            building = occ.bed.room.unit.building
            location = f"{building.name} - Room {occ.bed.room.room_number}, Bed {occ.bed.bed_number}"
        
        entry = {
            'occupancy': occ,
            'tenant': occ.tenant,
            'building': building,
            'location': location,
            'notice_date': occ.notice_date,
            'expected_checkout_date': occ.expected_checkout_date,
            'days_since_notice': occ.days_since_notice,
            'days_until_eligible': occ.days_until_eligible,
            'notice_reason': occ.notice_reason,
        }
        
        if occ.expected_checkout_date and occ.expected_checkout_date < today:
            entry['days_overdue'] = (today - occ.expected_checkout_date).days
            overdue_checkout.append(entry)
        elif occ.is_eligible_for_checkout:
            eligible_for_checkout.append(entry)
        else:
            in_notice_period.append(entry)
    
    # Stats
    total_notices = len(occupancies_with_notice)
    
    # Get tenants who can be given notice (active tenants without notice)
    tenants_without_notice = Tenant.objects.filter(
        account=account,
        occupancies__is_active=True,
        occupancies__notice_date__isnull=True
    ).filter(
        Q(occupancies__unit__building_id__in=accessible_building_ids) |
        Q(occupancies__bed__room__unit__building_id__in=accessible_building_ids)
    ).select_related().distinct().order_by('name')
    
    # Get their occupancies for display
    tenants_for_notice = []
    for tenant in tenants_without_notice:
        occupancy = Occupancy.objects.filter(
            tenant=tenant,
            is_active=True,
            notice_date__isnull=True
        ).filter(
            Q(unit__building_id__in=accessible_building_ids) |
            Q(bed__room__unit__building_id__in=accessible_building_ids)
        ).select_related(
            'unit', 'unit__building',
            'bed', 'bed__room', 'bed__room__unit', 'bed__room__unit__building'
        ).first()
        
        if occupancy:
            if occupancy.unit:
                building_name = occupancy.unit.building.name
                location = f"{building_name} - Unit {occupancy.unit.unit_number}"
                unit_number = occupancy.unit.unit_number
                room_number = None
                bed_number = None
            else:
                building_name = occupancy.bed.room.unit.building.name
                location = f"{building_name} - Room {occupancy.bed.room.room_number}, Bed {occupancy.bed.bed_number}"
                unit_number = occupancy.bed.room.unit.unit_number
                room_number = occupancy.bed.room.room_number
                bed_number = occupancy.bed.bed_number
            
            tenants_for_notice.append({
                'tenant': tenant,
                'occupancy': occupancy,
                'location': location,
                'building_name': building_name,
                'unit_number': unit_number,
                'room_number': room_number,
                'bed_number': bed_number,
            })
    
    context = {
        'page_title': 'Notice Period Management',
        'eligible_for_checkout': eligible_for_checkout,
        'in_notice_period': in_notice_period,
        'overdue_checkout': overdue_checkout,
        'total_notices': total_notices,
        'eligible_count': len(eligible_for_checkout),
        'pending_count': len(in_notice_period),
        'overdue_count': len(overdue_checkout),
        'tenants_for_notice': tenants_for_notice,
        'today': today,
    }
    
    return render(request, 'properties/notice_list.html', context)


@login_required
@owner_or_manager_required
@handle_errors
def update_building_notice_period(request, building_id):
    """Update notice period days for a building"""
    from buildings.access import get_accessible_buildings
    
    account = request.user.account
    
    try:
        building = Building.objects.get(id=building_id, account=account)
        
        # Check access
        accessible_buildings = get_accessible_buildings(request.user)
        if building not in accessible_buildings:
            messages.error(request, 'You do not have access to this building.')
            return redirect('properties:building_list')
        
        if request.method == 'POST':
            notice_period_days = request.POST.get('notice_period_days', 30)
            try:
                notice_period_days = int(notice_period_days)
                if notice_period_days < 0:
                    notice_period_days = 0
                elif notice_period_days > 365:
                    notice_period_days = 365
                    
                building.notice_period_days = notice_period_days
                building.save()
                
                messages.success(request, f'Notice period updated to {notice_period_days} days for {building.name}.')
            except ValueError:
                messages.error(request, 'Invalid notice period value.')
            
            return redirect('properties:building_detail', building_id=building_id)
        
        context = {
            'building': building,
        }
        
        return render(request, 'properties/forms/update_notice_period_form.html', context)
        
    except Building.DoesNotExist:
        raise Http404("Building not found")


# ============== DOCUMENT MANAGEMENT ==============

@login_required
@owner_or_manager_required
@handle_errors
def tenant_documents(request, tenant_id):
    """View all documents for a tenant"""
    from tenants.models import TenantDocument
    
    account = request.user.account
    
    try:
        tenant = Tenant.objects.get(id=tenant_id, account=account)
        
        documents = TenantDocument.objects.filter(tenant=tenant).order_by('-created_at')
        
        # Group documents by type
        doc_by_type = {}
        for doc in documents:
            doc_type = doc.document_type
            if doc_type not in doc_by_type:
                doc_by_type[doc_type] = []
            doc_by_type[doc_type].append(doc)
        
        # Stats
        total_docs = documents.count()
        verified_count = documents.filter(verification_status='VERIFIED').count()
        pending_count = documents.filter(verification_status='PENDING').count()
        expired_count = sum(1 for d in documents if d.is_expired)
        
        # Get available document types for upload
        existing_types = set(documents.values_list('document_type', flat=True))
        available_types = [dt for dt in TenantDocument.DOCUMENT_TYPES if dt[0] not in existing_types or dt[0] == 'OTHER']
        
        context = {
            'tenant': tenant,
            'documents': documents,
            'doc_by_type': doc_by_type,
            'total_docs': total_docs,
            'verified_count': verified_count,
            'pending_count': pending_count,
            'expired_count': expired_count,
            'available_types': available_types,
            'document_types': TenantDocument.DOCUMENT_TYPES,
        }
        
        return render(request, 'properties/tenant_documents.html', context)
        
    except Tenant.DoesNotExist:
        raise Http404("Tenant not found")


@login_required
@owner_or_manager_required
@handle_errors
def upload_document(request, tenant_id):
    """Upload a new document for a tenant"""
    from tenants.models import TenantDocument
    
    account = request.user.account
    
    try:
        tenant = Tenant.objects.get(id=tenant_id, account=account)
        
        if request.method == 'POST':
            document_type = request.POST.get('document_type')
            document_number = request.POST.get('document_number', '').strip()
            issue_date = request.POST.get('issue_date')
            expiry_date = request.POST.get('expiry_date')
            notes = request.POST.get('notes', '').strip()
            file = request.FILES.get('file')
            
            if not document_type:
                messages.error(request, 'Please select a document type.')
                return redirect('properties:upload_document', tenant_id=tenant_id)
            
            if not file:
                messages.error(request, 'Please select a file to upload.')
                return redirect('properties:upload_document', tenant_id=tenant_id)
            
            # Validate file size (max 10MB)
            if file.size > 10 * 1024 * 1024:
                messages.error(request, 'File size must be less than 10MB.')
                return redirect('properties:upload_document', tenant_id=tenant_id)
            
            # Validate file type
            allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.pdf', '.doc', '.docx']
            ext = file.name.split('.')[-1].lower()
            if f'.{ext}' not in allowed_extensions:
                messages.error(request, f'Invalid file type. Allowed: {", ".join(allowed_extensions)}')
                return redirect('properties:upload_document', tenant_id=tenant_id)
            
            # Create document
            doc = TenantDocument(
                tenant=tenant,
                document_type=document_type,
                document_number=document_number,
                file=file,
                original_filename=file.name,
                notes=notes,
                uploaded_by=request.user,
            )
            
            if issue_date:
                from datetime import datetime
                doc.issue_date = datetime.strptime(issue_date, '%Y-%m-%d').date()
            
            if expiry_date:
                from datetime import datetime
                doc.expiry_date = datetime.strptime(expiry_date, '%Y-%m-%d').date()
            
            doc.save()
            
            messages.success(request, f'{doc.get_document_type_display()} uploaded successfully!')
            return redirect('properties:tenant_documents', tenant_id=tenant_id)
        
        # Get available document types
        existing_types = set(TenantDocument.objects.filter(tenant=tenant).values_list('document_type', flat=True))
        available_types = [dt for dt in TenantDocument.DOCUMENT_TYPES if dt[0] not in existing_types or dt[0] == 'OTHER']
        
        context = {
            'tenant': tenant,
            'available_types': available_types,
            'document_types': TenantDocument.DOCUMENT_TYPES,
        }
        
        return render(request, 'properties/forms/upload_document_form.html', context)
        
    except Tenant.DoesNotExist:
        raise Http404("Tenant not found")


@login_required
@owner_or_manager_required
@handle_errors
def view_document(request, document_id):
    """View/Download a specific document"""
    from tenants.models import TenantDocument
    from django.http import FileResponse
    
    account = request.user.account
    
    try:
        doc = TenantDocument.objects.select_related('tenant').get(
            id=document_id,
            tenant__account=account
        )
        
        # Return file for download/view
        if request.GET.get('download'):
            response = FileResponse(doc.file.open('rb'), as_attachment=True)
            response['Content-Disposition'] = f'attachment; filename="{doc.original_filename}"'
            return response
        
        context = {
            'document': doc,
            'tenant': doc.tenant,
        }
        
        return render(request, 'properties/view_document.html', context)
        
    except TenantDocument.DoesNotExist:
        raise Http404("Document not found")


@login_required
@owner_or_manager_required
@handle_errors
def verify_document(request, document_id):
    """Verify or reject a document"""
    from tenants.models import TenantDocument
    
    account = request.user.account
    
    try:
        doc = TenantDocument.objects.select_related('tenant').get(
            id=document_id,
            tenant__account=account
        )
        
        if request.method == 'POST':
            action = request.POST.get('action')
            verification_notes = request.POST.get('verification_notes', '').strip()
            
            if action == 'verify':
                doc.verification_status = 'VERIFIED'
                doc.verified_by = request.user
                doc.verified_at = timezone.now()
                doc.verification_notes = verification_notes
                doc.save()
                messages.success(request, f'{doc.get_document_type_display()} has been verified.')
                
            elif action == 'reject':
                doc.verification_status = 'REJECTED'
                doc.verified_by = request.user
                doc.verified_at = timezone.now()
                doc.verification_notes = verification_notes
                doc.save()
                messages.warning(request, f'{doc.get_document_type_display()} has been rejected.')
            
            return redirect('properties:tenant_documents', tenant_id=doc.tenant.id)
        
        context = {
            'document': doc,
            'tenant': doc.tenant,
        }
        
        return render(request, 'properties/forms/verify_document_form.html', context)
        
    except TenantDocument.DoesNotExist:
        raise Http404("Document not found")


@login_required
@owner_or_manager_required
@handle_errors
def delete_document(request, document_id):
    """Delete a document"""
    from tenants.models import TenantDocument
    
    account = request.user.account
    
    try:
        doc = TenantDocument.objects.select_related('tenant').get(
            id=document_id,
            tenant__account=account
        )
        
        tenant_id = doc.tenant.id
        doc_name = doc.get_document_type_display()
        
        if request.method == 'POST':
            # Delete the file from storage
            if doc.file:
                doc.file.delete(save=False)
            doc.delete()
            
            messages.success(request, f'{doc_name} has been deleted.')
            return redirect('properties:tenant_documents', tenant_id=tenant_id)
        
        context = {
            'document': doc,
            'tenant': doc.tenant,
        }
        
        return render(request, 'properties/forms/delete_document_form.html', context)
        
    except TenantDocument.DoesNotExist:
        raise Http404("Document not found")


# ============== RENT RECEIPT PDF ==============

@login_required
@owner_or_manager_required
@handle_errors
def download_rent_receipt(request, rent_id):
    """Download rent receipt as PDF"""
    from common.pdf_utils import generate_rent_receipt_pdf, REPORTLAB_AVAILABLE
    from django.http import HttpResponse
    from django.contrib import messages
    
    account = request.user.account
    
    # Check if reportlab is available
    if not REPORTLAB_AVAILABLE:
        messages.error(request, 'PDF generation is not available. Please install reportlab: pip install reportlab==3.6.13')
        return redirect('properties:rent_management')
    
    try:
        rent = Rent.objects.select_related(
            'occupancy__tenant',
            'occupancy__unit__building__account',
            'occupancy__bed__room__unit__building__account'
        ).get(id=rent_id)
        
        # Verify access
        if rent.occupancy.unit:
            if rent.occupancy.unit.building.account != account:
                raise Http404("Rent record not found")
        elif rent.occupancy.bed:
            if rent.occupancy.bed.room.unit.building.account != account:
                raise Http404("Rent record not found")
        
        # Generate PDF with logged-in user's name and tenant's name
        pdf_buffer = generate_rent_receipt_pdf(
            rent, 
            account.name,
            signed_by_user=request.user,
            tenant_name=rent.occupancy.tenant.name
        )
        
        # Create response
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        
        # Generate filename
        tenant_name = rent.occupancy.tenant.name.replace(' ', '_')
        month_str = rent.month.strftime('%b_%Y')
        filename = f"Rent_Receipt_{tenant_name}_{month_str}.pdf"
        
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Rent.DoesNotExist:
        raise Http404("Rent record not found")
    except ImportError as e:
        messages.error(request, f'PDF generation error: {str(e)}')
        return redirect('properties:rent_management')


@login_required
@owner_or_manager_required
@handle_errors
def view_rent_receipt(request, rent_id):
    """View rent receipt in browser (inline PDF)"""
    from common.pdf_utils import generate_rent_receipt_pdf
    from django.http import HttpResponse
    
    account = request.user.account
    
    try:
        rent = Rent.objects.select_related(
            'occupancy__tenant',
            'occupancy__unit__building__account',
            'occupancy__bed__room__unit__building__account'
        ).get(id=rent_id)
        
        # Verify access
        if rent.occupancy.unit:
            if rent.occupancy.unit.building.account != account:
                raise Http404("Rent record not found")
        elif rent.occupancy.bed:
            if rent.occupancy.bed.room.unit.building.account != account:
                raise Http404("Rent record not found")
        
        # Generate PDF with logged-in user's name and tenant's name
        pdf_buffer = generate_rent_receipt_pdf(
            rent, 
            account.name,
            signed_by_user=request.user,
            tenant_name=rent.occupancy.tenant.name
        )
        
        # Create response (inline to view in browser)
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        
        # Generate filename
        tenant_name = rent.occupancy.tenant.name.replace(' ', '_')
        month_str = rent.month.strftime('%b_%Y')
        filename = f"Rent_Receipt_{tenant_name}_{month_str}.pdf"
        
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        
        return response
        
    except Rent.DoesNotExist:
        raise Http404("Rent record not found")


@login_required
@owner_or_manager_required
@handle_errors
def print_rent_receipt(request, rent_id):
    """Show printable HTML receipt (fallback for PDF issues)"""
    account = request.user.account
    
    try:
        rent = Rent.objects.select_related(
            'occupancy__tenant',
            'occupancy__unit__building__account',
            'occupancy__bed__room__unit__building__account'
        ).get(id=rent_id)
        
        # Verify access
        occupancy = rent.occupancy
        if occupancy.unit:
            if occupancy.unit.building.account != account:
                raise Http404("Rent record not found")
            building = occupancy.unit.building
            location = f"Unit {occupancy.unit.unit_number}"
            property_type = "Flat"
        elif occupancy.bed:
            if occupancy.bed.room.unit.building.account != account:
                raise Http404("Rent record not found")
            building = occupancy.bed.room.unit.building
            location = f"Room {occupancy.bed.room.room_number}, Bed {occupancy.bed.bed_number}"
            property_type = "PG"
        
        tenant = occupancy.tenant
        
        context = {
            'rent': rent,
            'occupancy': occupancy,
            'tenant': tenant,
            'building': building,
            'location': location,
            'property_type': property_type,
            'account': account,
            'receipt_number': f'RR-{rent.id:06d}',
            'generated_at': timezone.now(),
        }
        
        return render(request, 'properties/rent_receipt_print.html', context)
        
    except Rent.DoesNotExist:
        raise Http404("Rent record not found")


@login_required
@owner_or_manager_required
@handle_errors
def manage_flat_occupants(request, unit_id):
    """Manage occupants of a flat - add, remove, set primary"""
    account = getattr(request, 'account', None)
    if not account and hasattr(request.user, 'account') and request.user.account:
        account = request.user.account
        request.account = account
    
    if not account:
        messages.warning(request, 'Your account is not properly configured.')
        return redirect('accounts:profile')
    
    try:
        unit = get_object_or_404(Unit, id=unit_id, account=account, unit_type='FLAT')
        building = unit.building
        
        # CRITICAL: Check building access for managers
        from buildings.access import can_access_building
        if not can_access_building(request.user, building):
            messages.error(request, 'You don\'t have access to this building.')
            raise PermissionDenied("You don't have access to this building.")
        
        # Get all active occupants
        # Get all occupants, then sort in Python to avoid SQL issues with is_primary
        occupants = Occupancy.objects.filter(
            unit=unit,
            is_active=True
        ).select_related('tenant').order_by('start_date')
        
        # Convert to list and sort by is_primary in Python
        occupants_list = list(occupants)
        try:
            occupants_list.sort(key=lambda x: (not getattr(x, 'is_primary', False), x.start_date))
        except:
            pass  # If is_primary doesn't exist yet, just use start_date order
        
        # Get primary occupant (safely check is_primary)
        primary_occupancy = None
        for occ in occupants_list:
            try:
                if getattr(occ, 'is_primary', False):
                    primary_occupancy = occ
                    break
            except:
                pass
        if not primary_occupancy and occupants_list:
            primary_occupancy = occupants_list[0]
        
        # Get all tenants in account for adding
        all_tenants = Tenant.objects.filter(account=account).order_by('name')
        
        # Get tenants already in this flat
        existing_tenant_ids = set(occupants.values_list('tenant_id', flat=True))
        available_tenants = [t for t in all_tenants if t.id not in existing_tenant_ids]
        
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'set_primary':
                # Set a tenant as primary
                occupancy_id = request.POST.get('occupancy_id')
                try:
                    occupancy = Occupancy.objects.get(id=occupancy_id, unit=unit, is_active=True)
                    
                    # Unset other primary occupants
                    try:
                        Occupancy.objects.filter(unit=unit, is_active=True, is_primary=True).update(is_primary=False)
                    except Exception:
                        # Field not available yet - skip
                        pass
                    
                    # Set this one as primary
                    try:
                        occupancy.is_primary = True
                    except Exception:
                        pass
                    occupancy.rent = unit.expected_rent or Decimal('0')  # Set rent to flat rent
                    occupancy.save()
                    
                    # Set other occupants' rent to 0
                    try:
                        Occupancy.objects.filter(unit=unit, is_active=True, is_primary=False).update(rent=Decimal('0'))
                    except Exception:
                        # Field not available yet - set all others to 0
                        Occupancy.objects.filter(unit=unit, is_active=True).exclude(id=occupancy.id).update(rent=Decimal('0'))
                    
                    messages.success(request, f'{occupancy.tenant.name} is now the primary tenant.')
                    return redirect('properties:manage_flat_occupants', unit_id=unit_id)
                except Occupancy.DoesNotExist:
                    messages.error(request, 'Occupancy not found.')
            
            elif action == 'remove_occupant':
                # Remove tenant from flat (checkout)
                occupancy_id = request.POST.get('occupancy_id')
                try:
                    occupancy = Occupancy.objects.get(id=occupancy_id, unit=unit, is_active=True)
                    tenant_name = occupancy.tenant.name
                    
                    # Deactivate occupancy
                    occupancy.is_active = False
                    occupancy.end_date = timezone.now().date()
                    occupancy.save()
                    
                    # If this was primary, make another one primary
                    if getattr(occupancy, 'is_primary', False):
                        remaining = Occupancy.objects.filter(unit=unit, is_active=True).first()
                        if remaining:
                            try:
                                remaining.is_primary = True
                            except Exception:
                                pass
                            remaining.rent = unit.expected_rent or Decimal('0')
                            remaining.save()
                    
                    messages.success(request, f'{tenant_name} has been removed from {unit.unit_number}.')
                    return redirect('properties:manage_flat_occupants', unit_id=unit_id)
                except Occupancy.DoesNotExist:
                    messages.error(request, 'Occupancy not found.')
            
            elif action == 'add_occupant':
                # Add existing tenant to flat
                tenant_id = request.POST.get('tenant_id')
                try:
                    tenant = Tenant.objects.get(id=tenant_id, account=account)
                    
                    # Check if already in this flat
                    existing = Occupancy.objects.filter(tenant=tenant, unit=unit, is_active=True).first()
                    if existing:
                        messages.warning(request, f'{tenant.name} is already in this flat.')
                        return redirect('properties:manage_flat_occupants', unit_id=unit_id)
                    
                    # Check if tenant has another active occupancy
                    other_occupancy = Occupancy.objects.filter(tenant=tenant, is_active=True).exclude(unit=unit).first()
                    if other_occupancy:
                        messages.warning(request, f'{tenant.name} is already assigned to another unit/bed. Please checkout first.')
                        return redirect('properties:manage_flat_occupants', unit_id=unit_id)
                    
                    # Determine if this should be primary
                    is_primary = not primary_occupancy  # First occupant is primary
                    rent_amount = unit.expected_rent if is_primary else Decimal('0')
                    
                    # If setting as primary, unset others
                    if is_primary:
                        try:
                            Occupancy.objects.filter(unit=unit, is_active=True, is_primary=True).update(is_primary=False, rent=Decimal('0'))
                        except Exception:
                            # Field not available yet - just set rent to 0
                            Occupancy.objects.filter(unit=unit, is_active=True).exclude(id=tenant.id).update(rent=Decimal('0'))
                    
                    # Create occupancy
                    occupancy_data = {
                        'tenant': tenant,
                        'unit': unit,
                        'rent': rent_amount,
                        'start_date': timezone.now().date(),
                        'is_active': True,
                    }
                    # Add is_primary if field exists
                    try:
                        occupancy_data['is_primary'] = is_primary
                    except Exception:
                        pass
                    Occupancy.objects.create(**occupancy_data)
                    
                    messages.success(request, f'{tenant.name} has been added to {unit.unit_number}.')
                    return redirect('properties:manage_flat_occupants', unit_id=unit_id)
                except Tenant.DoesNotExist:
                    messages.error(request, 'Tenant not found.')
        
        context = {
            'unit': unit,
            'building': building,
            'occupants': occupants,
            'primary_occupancy': primary_occupancy,
            'available_tenants': available_tenants,
        }
        
        return render(request, 'properties/manage_flat_occupants.html', context)
        
    except Unit.DoesNotExist:
        messages.error(request, 'Unit not found.')
        return redirect('properties:building_list')
