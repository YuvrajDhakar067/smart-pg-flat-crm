from django.db import models
from django.conf import settings
from accounts.models import Account


class Building(models.Model):
    """Building owned by an account"""
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='buildings')
    name = models.CharField(max_length=255)
    address = models.TextField()
    total_floors = models.IntegerField(default=1, help_text="Number of floors")
    notice_period_days = models.IntegerField(
        default=30, 
        help_text="Number of days notice required before checkout"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "Building"
        verbose_name_plural = "Buildings"
        indexes = [
            models.Index(fields=['account', 'name']),
            models.Index(fields=['account', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.account.name})"
    
    @property
    def total_units(self):
        """Total units in this building - CACHED for performance"""
        if not hasattr(self, '_total_units_cache'):
            self._total_units_cache = self.units.count()
        return self._total_units_cache
    
    @property
    def occupied_units(self):
        """Occupied units count - CACHED for performance"""
        if not hasattr(self, '_occupied_units_cache'):
            self._occupied_units_cache = self.units.filter(status='OCCUPIED').count()
        return self._occupied_units_cache
    
    @property
    def vacant_units(self):
        """Vacant units count - CACHED for performance"""
        if not hasattr(self, '_vacant_units_cache'):
            self._vacant_units_cache = self.units.filter(status='VACANT').count()
        return self._vacant_units_cache


class BuildingAccess(models.Model):
    """
    Tracks which managers have access to which buildings.
    
    - Owners automatically have access to all buildings (no entries needed)
    - Managers only have access to buildings listed here
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='building_accesses',
        help_text="Manager who has access"
    )
    building = models.ForeignKey(
        Building,
        on_delete=models.CASCADE,
        related_name='access_grants',
        help_text="Building the manager can access"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='granted_accesses',
        help_text="Owner who granted this access"
    )
    
    class Meta:
        verbose_name = "Building Access"
        verbose_name_plural = "Building Accesses"
        unique_together = ['user', 'building']
        indexes = [
            models.Index(fields=['user', 'building']),
            models.Index(fields=['building']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} → {self.building.name}"
    
    def clean(self):
        """Validate access grant"""
        from django.core.exceptions import ValidationError
        
        # Ensure user and building belong to the same account
        if self.user.account != self.building.account:
            raise ValidationError(
                "User and building must belong to the same account"
            )
        
        # Warn if granting access to an owner (they already have access)
        if self.user.role == 'OWNER':
            raise ValidationError(
                "Owners automatically have access to all buildings. "
                "BuildingAccess entries are only for managers."
            )
    
    def save(self, *args, **kwargs):
        """Override save to run validation"""
        self.full_clean()
        super().save(*args, **kwargs)

