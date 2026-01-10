"""
Account Service Layer
Handles business logic for account-related operations including limit management.
Follows Service Layer pattern for separation of concerns.
"""
from typing import Optional, Tuple
from core.services import BaseService
from core.exceptions import LimitExceededError
from .models import Account
from buildings.models import Building
from users.models import User
import logging

logger = logging.getLogger(__name__)


class AccountLimitService(BaseService):
    """
    Service for managing account limits (properties and managers).
    Handles limit checking, validation, and provides clean interface for views.
    """
    
    def __init__(self):
        super().__init__()
    
    def get_property_limit(self, account: Account) -> int:
        """
        Get the maximum property limit for an account.
        
        Args:
            account: Account instance
            
        Returns:
            Maximum number of properties allowed (0 = unlimited)
        """
        return account.get_max_properties()
    
    def get_manager_limit(self, account: Account) -> int:
        """
        Get the maximum manager limit for an account.
        
        Args:
            account: Account instance
            
        Returns:
            Maximum number of managers allowed (0 = unlimited)
        """
        return account.get_max_managers()
    
    def get_current_property_count(self, account: Account) -> int:
        """
        Get current number of properties for an account.
        
        Args:
            account: Account instance
            
        Returns:
            Current property count
        """
        return Building.objects.filter(account=account).count()
    
    def get_current_manager_count(self, account: Account) -> int:
        """
        Get current number of managers for an account.
        
        Args:
            account: Account instance
            
        Returns:
            Current manager count
        """
        return User.objects.filter(account=account, role='MANAGER').count()
    
    def can_add_property(self, account: Account) -> Tuple[bool, Optional[str]]:
        """
        Check if account can add a new property.
        
        Args:
            account: Account instance
            
        Returns:
            Tuple of (can_add: bool, error_message: Optional[str])
        """
        max_properties = self.get_property_limit(account)
        
        # Unlimited (0) means always allowed
        if max_properties == 0:
            return True, None
        
        current_count = self.get_current_property_count(account)
        
        if current_count >= max_properties:
            return False, (
                f'You have reached the maximum limit of {max_properties} properties. '
                f'Please contact administrator to increase your limit.'
            )
        
        return True, None
    
    def can_add_manager(self, account: Account) -> Tuple[bool, Optional[str]]:
        """
        Check if account can add a new manager.
        
        Args:
            account: Account instance
            
        Returns:
            Tuple of (can_add: bool, error_message: Optional[str])
        """
        max_managers = self.get_manager_limit(account)
        
        # Unlimited (0) means always allowed
        if max_managers == 0:
            return True, None
        
        current_count = self.get_current_manager_count(account)
        
        if current_count >= max_managers:
            return False, (
                f'You have reached the maximum limit of {max_managers} managers. '
                f'Please contact administrator to increase your limit.'
            )
        
        return True, None
    
    def validate_property_limit(self, account: Account) -> None:
        """
        Validate property limit and raise exception if exceeded.
        
        Args:
            account: Account instance
            
        Raises:
            LimitExceededError: If limit is exceeded
        """
        can_add, error_message = self.can_add_property(account)
        if not can_add:
            max_limit = self.get_property_limit(account)
            current = self.get_current_property_count(account)
            raise LimitExceededError(
                message=error_message,
                code="PROPERTY_LIMIT_EXCEEDED",
                details={
                    "current": current,
                    "max": max_limit,
                    "resource": "properties"
                }
            )
    
    def validate_manager_limit(self, account: Account) -> None:
        """
        Validate manager limit and raise exception if exceeded.
        
        Args:
            account: Account instance
            
        Raises:
            LimitExceededError: If limit is exceeded
        """
        can_add, error_message = self.can_add_manager(account)
        if not can_add:
            max_limit = self.get_manager_limit(account)
            current = self.get_current_manager_count(account)
            raise LimitExceededError(
                message=error_message,
                code="MANAGER_LIMIT_EXCEEDED",
                details={
                    "current": current,
                    "max": max_limit,
                    "resource": "managers"
                }
            )
    
    def get_limit_info(self, account: Account) -> dict:
        """
        Get comprehensive limit information for an account.
        
        Args:
            account: Account instance
            
        Returns:
            Dictionary with limit information
        """
        return {
            'properties': {
                'current': self.get_current_property_count(account),
                'max': self.get_property_limit(account),
                'unlimited': self.get_property_limit(account) == 0,
                'can_add': self.can_add_property(account)[0],
            },
            'managers': {
                'current': self.get_current_manager_count(account),
                'max': self.get_manager_limit(account),
                'unlimited': self.get_manager_limit(account) == 0,
                'can_add': self.can_add_manager(account)[0],
            }
        }
