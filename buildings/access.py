"""
Building Access Control Models and Helper Functions

This module provides multi-tenant access control with building-level permissions.

Access Rules:
- Account-level isolation: Users can ONLY access data in their own account
- Building-level permissions:
  - OWNER: Has access to ALL buildings in their account
  - MANAGER: Has access ONLY to buildings explicitly assigned via BuildingAccess
"""

from django.db import models
from buildings.models import Building, BuildingAccess


# ============================================================================
# ACCESS CONTROL HELPER FUNCTIONS
# ============================================================================

def get_accessible_buildings(user):
    """
    Get all buildings accessible to the user.
    
    Args:
        user: User instance
    
    Returns:
        QuerySet of Building objects the user can access
    
    Rules:
        - OWNER: All buildings in their account
        - MANAGER: Only buildings granted via BuildingAccess
    
    Usage:
        buildings = get_accessible_buildings(request.user)
    """
    if not user or not user.is_authenticated:
        return Building.objects.none()
    
    if not hasattr(user, 'account') or not user.account:
        return Building.objects.none()
    
    # OWNERS have access to ALL buildings in their account
    if user.role == 'OWNER':
        return Building.objects.filter(account=user.account)
    
    # MANAGERS only have access to explicitly granted buildings
    elif user.role == 'MANAGER':
        # Get building IDs the manager has access to
        accessible_building_ids = BuildingAccess.objects.filter(
            user=user
        ).values_list('building_id', flat=True)
        
        # Return buildings in their account that they have access to
        return Building.objects.filter(
            account=user.account,
            id__in=accessible_building_ids
        )
    
    # Unknown role - no access
    return Building.objects.none()


def get_accessible_building_ids(user):
    """
    Get IDs of all buildings accessible to the user.
    
    Args:
        user: User instance
    
    Returns:
        List of building IDs (integers)
    
    Usage:
        building_ids = get_accessible_building_ids(request.user)
        units = Unit.objects.filter(building_id__in=building_ids)
    """
    return list(get_accessible_buildings(user).values_list('id', flat=True))


def can_access_building(user, building):
    """
    Check if user can access a specific building.
    
    Args:
        user: User instance
        building: Building instance or building ID
    
    Returns:
        Boolean - True if user can access the building
    
    Usage:
        if can_access_building(request.user, building):
            # Allow access
        else:
            # Return 403
    """
    if not user or not user.is_authenticated:
        return False
    
    if not hasattr(user, 'account') or not user.account:
        return False
    
    # Get building instance if ID provided
    if isinstance(building, int):
        try:
            building = Building.objects.get(id=building)
        except Building.DoesNotExist:
            return False
    
    # Must be in same account
    if building.account != user.account:
        return False
    
    # OWNERS have access to all buildings
    if user.role == 'OWNER':
        return True
    
    # MANAGERS need explicit access
    elif user.role == 'MANAGER':
        return BuildingAccess.objects.filter(
            user=user,
            building=building
        ).exists()
    
    return False


def filter_by_accessible_buildings(queryset, user, building_field='building'):
    """
    Filter a queryset to only include items from accessible buildings.
    
    Args:
        queryset: Django QuerySet to filter
        user: User instance
        building_field: Name of the field that links to Building
                       (e.g., 'building', 'unit__building', 'occupancy__unit__building')
    
    Returns:
        Filtered QuerySet
    
    Usage:
        # For Units
        units = filter_by_accessible_buildings(
            Unit.objects.filter(account=user.account),
            user,
            building_field='building'
        )
        
        # For Issues (nested relationship)
        issues = filter_by_accessible_buildings(
            Issue.objects.filter(unit__account=user.account),
            user,
            building_field='unit__building'
        )
    """
    accessible_building_ids = get_accessible_building_ids(user)
    
    # Build the filter dynamically
    filter_kwargs = {f'{building_field}_id__in': accessible_building_ids}
    
    return queryset.filter(**filter_kwargs)


def enforce_account_isolation(queryset, user, account_field='account'):
    """
    Enforce account-level isolation - MANDATORY for all queries.
    
    Args:
        queryset: Django QuerySet to filter
        user: User instance
        account_field: Name of the field that links to Account
    
    Returns:
        Filtered QuerySet (only items in user's account)
    
    Usage:
        buildings = enforce_account_isolation(
            Building.objects.all(),
            request.user
        )
    """
    if not user or not user.is_authenticated:
        return queryset.none()
    
    if not hasattr(user, 'account') or not user.account:
        return queryset.none()
    
    # Filter by account
    filter_kwargs = {account_field: user.account}
    return queryset.filter(**filter_kwargs)


def get_accessible_queryset(model_class, user):
    """
    Get a fully filtered queryset for a model with both account and building-level access.
    
    Args:
        model_class: Model class (Building, Unit, Tenant, etc.)
        user: User instance
    
    Returns:
        Filtered QuerySet with both account isolation and building-level permissions
    
    Usage:
        # Get accessible buildings
        buildings = get_accessible_queryset(Building, request.user)
        
        # Get accessible units
        units = get_accessible_queryset(Unit, request.user)
    """
    from units.models import Unit, PGRoom, Bed
    from tenants.models import Tenant
    from occupancy.models import Occupancy
    from rent.models import Rent
    from issues.models import Issue
    
    if not user or not user.is_authenticated:
        return model_class.objects.none()
    
    if not hasattr(user, 'account') or not user.account:
        return model_class.objects.none()
    
    # Start with account isolation
    queryset = model_class.objects.filter(account=user.account)
    
    # For models that don't directly have an 'account' field, handle differently
    if model_class == Building:
        # Buildings: Use get_accessible_buildings
        return get_accessible_buildings(user)
    
    elif model_class == Unit:
        # Units: Filter by accessible buildings
        return filter_by_accessible_buildings(queryset, user, 'building')
    
    elif model_class == PGRoom:
        # PGRooms: Filter by unit's building
        return filter_by_accessible_buildings(queryset, user, 'unit__building')
    
    elif model_class == Bed:
        # Beds: Filter by room's unit's building
        return filter_by_accessible_buildings(queryset, user, 'room__unit__building')
    
    elif model_class == Tenant:
        # Tenants: Filter by account (tenants aren't building-specific)
        return queryset
    
    elif model_class == Occupancy:
        # Occupancy: Filter by unit's building (if flat) or bed's building (if PG)
        # This is more complex - get accessible building IDs and filter
        accessible_building_ids = get_accessible_building_ids(user)
        
        return queryset.filter(
            models.Q(unit__building_id__in=accessible_building_ids) |
            models.Q(bed__room__unit__building_id__in=accessible_building_ids)
        )
    
    elif model_class == Rent:
        # Rent: Filter by occupancy's building
        accessible_building_ids = get_accessible_building_ids(user)
        
        return queryset.filter(
            models.Q(occupancy__unit__building_id__in=accessible_building_ids) |
            models.Q(occupancy__bed__room__unit__building_id__in=accessible_building_ids)
        )
    
    elif model_class == Issue:
        # Issues: Filter by unit's building
        return filter_by_accessible_buildings(queryset, user, 'unit__building')
    
    else:
        # Default: just return account-filtered queryset
        return queryset

