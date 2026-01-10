"""
Data Transfer Objects (DTOs).
Used for passing data between layers without exposing domain models.
"""
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import date, datetime


@dataclass
class BuildingDTO:
    """Data Transfer Object for Building"""
    id: Optional[int] = None
    name: str = ""
    address: str = ""
    account_id: int = None
    total_floors: int = 1
    notice_period_days: int = 30


@dataclass
class TenantDTO:
    """Data Transfer Object for Tenant"""
    id: Optional[int] = None
    name: str = ""
    phone: str = ""
    email: str = ""
    account_id: int = None
    aadhar: Optional[str] = None
    pan: Optional[str] = None


@dataclass
class OccupancyDTO:
    """Data Transfer Object for Occupancy"""
    id: Optional[int] = None
    tenant_id: int = None
    unit_id: Optional[int] = None
    bed_id: Optional[int] = None
    start_date: date = None
    end_date: Optional[date] = None
    rent: Decimal = Decimal('0')
    is_active: bool = True
    is_primary: bool = False


@dataclass
class RentDTO:
    """Data Transfer Object for Rent"""
    id: Optional[int] = None
    occupancy_id: int = None
    month: date = None
    amount: Decimal = Decimal('0')
    paid_amount: Decimal = Decimal('0')
    status: str = "PENDING"
    notes: str = ""


@dataclass
class ManagerDTO:
    """Data Transfer Object for Manager"""
    id: Optional[int] = None
    username: str = ""
    email: str = ""
    phone: str = ""
    account_id: int = None
    building_ids: List[int] = None
