"""
Repository pattern implementation.
Abstracts data access and provides a clean interface for domain services.
"""
from typing import Generic, TypeVar, Optional, List, Dict, Any
from django.db.models import QuerySet, Model
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=Model)


class BaseRepository(Generic[T]):
    """
    Base repository providing common CRUD operations.
    Follows Repository pattern for data access abstraction.
    """
    
    def __init__(self, model: type[T]):
        self.model = model
    
    def get_by_id(self, id: int, **filters) -> Optional[T]:
        """Get a single instance by ID"""
        try:
            return self.model.objects.filter(id=id, **filters).first()
        except Exception as e:
            logger.error(f"Error getting {self.model.__name__} by id {id}: {str(e)}")
            return None
    
    def get_by_id_or_404(self, id: int, **filters) -> T:
        """Get a single instance by ID or raise 404"""
        from django.shortcuts import get_object_or_404
        return get_object_or_404(self.model, id=id, **filters)
    
    def get_all(self, **filters) -> QuerySet[T]:
        """Get all instances matching filters"""
        return self.model.objects.filter(**filters)
    
    def create(self, **kwargs) -> T:
        """Create a new instance"""
        return self.model.objects.create(**kwargs)
    
    def update(self, instance: T, **kwargs) -> T:
        """Update an existing instance"""
        for key, value in kwargs.items():
            setattr(instance, key, value)
        instance.save()
        return instance
    
    def delete(self, instance: T) -> bool:
        """Delete an instance"""
        try:
            instance.delete()
            return True
        except Exception as e:
            logger.error(f"Error deleting {self.model.__name__}: {str(e)}")
            return False
    
    def exists(self, **filters) -> bool:
        """Check if instance exists"""
        return self.model.objects.filter(**filters).exists()
    
    def count(self, **filters) -> int:
        """Count instances matching filters"""
        return self.model.objects.filter(**filters).count()
    
    @transaction.atomic
    def bulk_create(self, instances: List[T]) -> List[T]:
        """Bulk create instances"""
        return self.model.objects.bulk_create(instances)
    
    def get_queryset(self) -> QuerySet[T]:
        """Get base queryset for custom queries"""
        return self.model.objects.all()
