"""
Application-wide constants.
Centralized constants following DRY principle.
"""

# User Roles
class UserRole:
    OWNER = 'OWNER'
    MANAGER = 'MANAGER'
    
    CHOICES = [
        (OWNER, 'Owner'),
        (MANAGER, 'Manager'),
    ]


# Account Plans
class AccountPlan:
    FREE = 'FREE'
    BASIC = 'BASIC'
    PRO = 'PRO'
    ENTERPRISE = 'ENTERPRISE'
    
    CHOICES = [
        (FREE, 'Free'),
        (BASIC, 'Basic'),
        (PRO, 'Pro'),
        (ENTERPRISE, 'Enterprise'),
    ]


# Unit Types
class UnitType:
    FLAT = 'FLAT'
    PG = 'PG'
    
    CHOICES = [
        (FLAT, 'Flat'),
        (PG, 'PG'),
    ]


# Unit Status
class UnitStatus:
    OCCUPIED = 'OCCUPIED'
    VACANT = 'VACANT'
    MAINTENANCE = 'MAINTENANCE'
    
    CHOICES = [
        (OCCUPIED, 'Occupied'),
        (VACANT, 'Vacant'),
        (MAINTENANCE, 'Maintenance'),
    ]


# Rent Status
class RentStatus:
    PENDING = 'PENDING'
    PAID = 'PAID'
    PARTIAL = 'PARTIAL'
    OVERDUE = 'OVERDUE'
    
    CHOICES = [
        (PENDING, 'Pending'),
        (PAID, 'Paid'),
        (PARTIAL, 'Partial'),
        (OVERDUE, 'Overdue'),
    ]


# Issue Status
class IssueStatus:
    OPEN = 'OPEN'
    IN_PROGRESS = 'IN_PROGRESS'
    RESOLVED = 'RESOLVED'
    CLOSED = 'CLOSED'
    
    CHOICES = [
        (OPEN, 'Open'),
        (IN_PROGRESS, 'In Progress'),
        (RESOLVED, 'Resolved'),
        (CLOSED, 'Closed'),
    ]


# Default Limits
class DefaultLimits:
    MAX_PROPERTIES_PER_OWNER = 10
    MAX_MANAGERS_PER_OWNER = 5
    RENT_DUE_DAY = 5


# Pagination
class Pagination:
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
