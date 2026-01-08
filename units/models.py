from django.db import models
from django.core.validators import MinValueValidator
from accounts.models import Account
from buildings.models import Building


class Unit(models.Model):
    """Unit - Can be Flat or PG"""
    UNIT_TYPE_CHOICES = [
        ('FLAT', 'Flat'),
        ('PG', 'PG'),
    ]
    
    STATUS_CHOICES = [
        ('VACANT', 'Vacant'),
        ('OCCUPIED', 'Occupied'),
    ]
    
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='units')
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='units')
    unit_number = models.CharField(max_length=50, help_text="e.g., '203', 'PG-3'")
    
    unit_type = models.CharField(max_length=10, choices=UNIT_TYPE_CHOICES)
    bhk_type = models.CharField(max_length=10, null=True, blank=True, help_text="e.g., '1BHK', '2BHK' (for flats)")
    
    expected_rent = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    deposit = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='VACANT')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['unit_number']
        unique_together = ['building', 'unit_number']
        verbose_name = "Unit"
        verbose_name_plural = "Units"
        indexes = [
            models.Index(fields=['account', 'status']),
            models.Index(fields=['account', 'unit_type']),
            models.Index(fields=['building', 'status']),
            models.Index(fields=['account', 'building', 'status']),
        ]
    
    def __str__(self):
        return f"{self.building.name} - {self.unit_number} ({self.get_unit_type_display()})"
    
    @property
    def current_occupancy(self):
        """Get current active occupancy"""
        return self.occupancies.filter(is_active=True).first()
    
    def update_status(self):
        """Update status based on occupancy"""
        if self.current_occupancy:
            self.status = 'OCCUPIED'
        else:
            self.status = 'VACANT'
        self.save()


class PGRoom(models.Model):
    """PG Room - belongs to a PG Unit"""
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name='pg_rooms', 
                            limit_choices_to={'unit_type': 'PG'})
    room_number = models.CharField(max_length=20, help_text="e.g., 'Room 1', 'Room A'")
    sharing_type = models.IntegerField(help_text="Number of beds: 1, 2, 3, etc.")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['room_number']
        unique_together = ['unit', 'room_number']
        verbose_name = "PG Room"
        verbose_name_plural = "PG Rooms"
        indexes = [
            models.Index(fields=['unit']),
        ]
    
    def __str__(self):
        return f"{self.unit.unit_number} - {self.room_number} ({self.sharing_type} sharing)"
    
    @property
    def occupied_beds(self):
        """Count of occupied beds"""
        return self.beds.filter(status='OCCUPIED').count()
    
    @property
    def vacant_beds(self):
        """Count of vacant beds"""
        return self.beds.filter(status='VACANT').count()


class Bed(models.Model):
    """Bed in a PG Room"""
    STATUS_CHOICES = [
        ('VACANT', 'Vacant'),
        ('OCCUPIED', 'Occupied'),
    ]
    
    room = models.ForeignKey(PGRoom, on_delete=models.CASCADE, related_name='beds')
    bed_number = models.CharField(max_length=10, help_text="e.g., 'Bed 1', 'Bed A'")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='VACANT')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['bed_number']
        unique_together = ['room', 'bed_number']
        verbose_name = "Bed"
        verbose_name_plural = "Beds"
        indexes = [
            models.Index(fields=['room', 'status']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.room} - {self.bed_number}"
    
    @property
    def current_occupancy(self):
        """Get current active occupancy for this bed"""
        return self.occupancies.filter(is_active=True).first()
    
    def update_status(self):
        """Update status based on occupancy"""
        if self.current_occupancy:
            self.status = 'OCCUPIED'
        else:
            self.status = 'VACANT'
        self.save()

