"""
Building service - Business logic layer for Building domain.
Services orchestrate repositories and contain business rules.
"""
from typing import Optional, List
from django.db import transaction
from core.services import BaseService
from core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from core.validators import PropertyLimitValidator
from core.dto import BuildingDTO
from .repositories import BuildingRepository, BuildingAccessRepository
from .models import Building
from accounts.models import Account
from common.utils import get_site_settings


class BuildingService(BaseService):
    """Service for building-related business logic"""
    
    def __init__(self):
        super().__init__()
        self.building_repo = BuildingRepository(Building)
        self.access_repo = BuildingAccessRepository()
    
    def create_building(self, account_id: int, building_data: BuildingDTO, user) -> Building:
        """
        Create a new building with validation and business rules.
        
        Args:
            account_id: Account ID
            building_data: Building data
            user: User creating the building (must be OWNER)
        
        Returns:
            Created Building instance
        
        Raises:
            PermissionDeniedError: If user is not owner
            ValidationError: If limit exceeded
        """
        # Validate user is owner
        if user.role != 'OWNER':
            raise PermissionDeniedError("Only owners can create buildings")
        
        # Check property limit
        site_settings = get_site_settings()
        current_count = self.building_repo.count(account_id=account_id)
        PropertyLimitValidator.validate_property_limit(
            current_count,
            site_settings.max_properties_per_owner,
            "properties"
        )
        
        # Create building
        with transaction.atomic():
            building = self.building_repo.create(
                account_id=account_id,
                name=building_data.name,
                address=building_data.address,
                total_floors=building_data.total_floors,
                notice_period_days=building_data.notice_period_days
            )
            
            self.log_info(f"Building created: {building.name}", building_id=building.id, account_id=account_id)
            return building
    
    def get_building(self, building_id: int, user) -> Building:
        """
        Get a building with access control.
        
        Args:
            building_id: Building ID
            user: User requesting the building
        
        Returns:
            Building instance
        
        Raises:
            NotFoundError: If building doesn't exist
            PermissionDeniedError: If user doesn't have access
        """
        building = self.building_repo.get_by_id(building_id)
        if not building:
            raise NotFoundError(resource_type="Building", resource_id=building_id)
        
        if not self.building_repo.can_access(user, building_id):
            raise PermissionDeniedError("You don't have access to this building")
        
        return building
    
    def get_accessible_buildings(self, user) -> List[Building]:
        """Get all buildings accessible to user"""
        return list(self.building_repo.get_accessible_buildings(user))
    
    def update_building(self, building_id: int, building_data: BuildingDTO, user) -> Building:
        """
        Update a building with access control.
        
        Args:
            building_id: Building ID
            building_data: Updated building data
            user: User updating the building
        
        Returns:
            Updated Building instance
        """
        building = self.get_building(building_id, user)
        
        with transaction.atomic():
            self.building_repo.update(
                building,
                name=building_data.name,
                address=building_data.address,
                total_floors=building_data.total_floors,
                notice_period_days=building_data.notice_period_days
            )
            
            self.log_info(f"Building updated: {building.name}", building_id=building.id)
            return building
    
    def delete_building(self, building_id: int, user) -> bool:
        """
        Delete a building with access control.
        
        Args:
            building_id: Building ID
            user: User deleting the building (must be owner)
        
        Returns:
            True if deleted successfully
        """
        if user.role != 'OWNER':
            raise PermissionDeniedError("Only owners can delete buildings")
        
        building = self.get_building(building_id, user)
        
        with transaction.atomic():
            result = self.building_repo.delete(building)
            if result:
                self.log_info(f"Building deleted: {building.name}", building_id=building_id)
            return result
