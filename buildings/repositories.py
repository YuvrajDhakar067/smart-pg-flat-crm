"""
Building repository - Data access layer for Building domain.
Follows Repository pattern for clean separation of concerns.
"""
from typing import Optional, List
from django.db.models import QuerySet, Q
from core.repositories import BaseRepository
from .models import Building, BuildingAccess


class BuildingRepository(BaseRepository[Building]):
    """Repository for Building model"""
    
    def get_by_account(self, account_id: int) -> QuerySet[Building]:
        """Get all buildings for an account"""
        return self.get_all(account_id=account_id)
    
    def get_accessible_buildings(self, user) -> QuerySet[Building]:
        """Get buildings accessible to a user (owner or manager)"""
        if user.role == 'OWNER':
            return self.get_by_account(user.account_id)
        elif user.role == 'MANAGER':
            # Get buildings through BuildingAccess
            building_ids = BuildingAccess.objects.filter(
                user=user
            ).values_list('building_id', flat=True)
            return self.get_all(id__in=building_ids)
        return self.model.objects.none()
    
    def get_accessible_building_ids(self, user) -> List[int]:
        """Get list of accessible building IDs"""
        return list(self.get_accessible_buildings(user).values_list('id', flat=True))
    
    def can_access(self, user, building_id: int) -> bool:
        """Check if user can access a specific building"""
        if user.role == 'OWNER':
            return self.exists(id=building_id, account_id=user.account_id)
        elif user.role == 'MANAGER':
            return BuildingAccess.objects.filter(
                user=user,
                building_id=building_id
            ).exists()
        return False
    
    def get_with_stats(self, account_id: int) -> QuerySet[Building]:
        """Get buildings with aggregated statistics"""
        from django.db.models import Count, Sum
        from units.models import Unit
        
        return self.get_by_account(account_id).annotate(
            total_units=Count('units'),
            occupied_units=Count('units', filter=Q(units__status='OCCUPIED')),
            vacant_units=Count('units', filter=Q(units__status='VACANT')),
        )


class BuildingAccessRepository(BaseRepository[BuildingAccess]):
    """Repository for BuildingAccess model"""
    
    def get_by_user(self, user_id: int) -> QuerySet[BuildingAccess]:
        """Get all building accesses for a user"""
        return self.get_all(user_id=user_id)
    
    def get_by_building(self, building_id: int) -> QuerySet[BuildingAccess]:
        """Get all accesses for a building"""
        return self.get_all(building_id=building_id)
    
    def grant_access(self, user_id: int, building_id: int, created_by_id: int) -> BuildingAccess:
        """Grant building access to a user"""
        return self.create(
            user_id=user_id,
            building_id=building_id,
            created_by_id=created_by_id
        )
    
    def revoke_access(self, user_id: int, building_id: int) -> bool:
        """Revoke building access from a user"""
        access = self.get_all(user_id=user_id, building_id=building_id).first()
        if access:
            return self.delete(access)
        return False
