"""
Base service classes.
Services contain business logic and orchestrate between repositories.
"""
from typing import Optional, List, Dict, Any
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


class BaseService:
    """
    Base service class providing common functionality.
    Services should contain business logic and use repositories for data access.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @transaction.atomic
    def execute_in_transaction(self, func, *args, **kwargs):
        """Execute a function within a database transaction"""
        return func(*args, **kwargs)
    
    def log_info(self, message: str, **context):
        """Log info message with context"""
        self.logger.info(f"{message} | Context: {context}")
    
    def log_error(self, message: str, error: Exception = None, **context):
        """Log error message with context"""
        if error:
            self.logger.error(f"{message} | Context: {context}", exc_info=error)
        else:
            self.logger.error(f"{message} | Context: {context}")
