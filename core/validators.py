"""
Validation utilities and validators.
Centralized validation logic following single responsibility principle.
"""
from typing import Optional, List
from decimal import Decimal
from django.core.exceptions import ValidationError
from core.exceptions import ValidationError as AppValidationError


class PropertyLimitValidator:
    """Validates property limits"""
    
    @staticmethod
    def validate_property_limit(current_count: int, max_allowed: int, resource_name: str = "properties"):
        """Validate if property limit is exceeded"""
        if max_allowed > 0 and current_count >= max_allowed:
            raise AppValidationError(
                message=f"You have reached the maximum limit of {max_allowed} {resource_name}.",
                code="LIMIT_EXCEEDED",
                details={
                    "current": current_count,
                    "max": max_allowed,
                    "resource": resource_name
                }
            )


class ManagerLimitValidator:
    """Validates manager limits"""
    
    @staticmethod
    def validate_manager_limit(current_count: int, max_allowed: int):
        """Validate if manager limit is exceeded"""
        if max_allowed > 0 and current_count >= max_allowed:
            raise AppValidationError(
                message=f"You have reached the maximum limit of {max_allowed} managers.",
                code="MANAGER_LIMIT_EXCEEDED",
                details={
                    "current": current_count,
                    "max": max_allowed
                }
            )


class RentValidator:
    """Validates rent-related operations"""
    
    @staticmethod
    def validate_rent_amount(amount: Decimal):
        """Validate rent amount"""
        if amount < 0:
            raise AppValidationError(
                message="Rent amount cannot be negative",
                code="INVALID_RENT_AMOUNT"
            )
        if amount > Decimal('9999999.99'):
            raise AppValidationError(
                message="Rent amount exceeds maximum allowed",
                code="RENT_AMOUNT_TOO_LARGE"
            )
    
    @staticmethod
    def validate_payment_amount(paid_amount: Decimal, total_amount: Decimal):
        """Validate payment amount doesn't exceed total"""
        if paid_amount < 0:
            raise AppValidationError(
                message="Payment amount cannot be negative",
                code="INVALID_PAYMENT_AMOUNT"
            )
        if paid_amount > total_amount:
            raise AppValidationError(
                message="Payment amount cannot exceed total rent",
                code="PAYMENT_EXCEEDS_TOTAL"
            )


class OccupancyValidator:
    """Validates occupancy operations"""
    
    @staticmethod
    def validate_dates(start_date, end_date=None):
        """Validate occupancy dates"""
        from django.utils import timezone
        today = timezone.now().date()
        
        if start_date > today:
            raise AppValidationError(
                message="Start date cannot be in the future",
                code="INVALID_START_DATE"
            )
        
        if end_date and end_date < start_date:
            raise AppValidationError(
                message="End date cannot be before start date",
                code="INVALID_END_DATE"
            )
