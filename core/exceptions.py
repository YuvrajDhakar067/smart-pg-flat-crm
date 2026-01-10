"""
Custom exceptions for the application.
Following domain-driven design principles with specific exception types.
"""


class BaseApplicationException(Exception):
    """Base exception for all application-specific exceptions"""
    default_message = "An application error occurred"
    
    def __init__(self, message=None, code=None, details=None):
        self.message = message or self.default_message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(BaseApplicationException):
    """Raised when validation fails"""
    default_message = "Validation failed"


class NotFoundError(BaseApplicationException):
    """Raised when a resource is not found"""
    default_message = "Resource not found"
    
    def __init__(self, resource_type=None, resource_id=None, **kwargs):
        self.resource_type = resource_type
        self.resource_id = resource_id
        super().__init__(**kwargs)


class PermissionDeniedError(BaseApplicationException):
    """Raised when user doesn't have permission"""
    default_message = "Permission denied"


class BusinessLogicError(BaseApplicationException):
    """Raised when business rule is violated"""
    default_message = "Business rule violation"


class LimitExceededError(BusinessLogicError):
    """Raised when a limit is exceeded (properties, managers, etc.)"""
    default_message = "Limit exceeded"


class ConcurrentModificationError(BusinessLogicError):
    """Raised when concurrent modification is detected"""
    default_message = "Resource is being modified by another user"


class AccountError(BaseApplicationException):
    """Raised for account-related errors"""
    default_message = "Account error"
