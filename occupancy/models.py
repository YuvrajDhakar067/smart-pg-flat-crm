from django.db import models
from django.core.validators import MinValueValidator
from tenants.models import Tenant
from units.models import Unit, Bed


class Occupancy(models.Model):
    """
    MOST IMPORTANT TABLE - Links tenant to unit (flat) or bed (PG)
    
    Logic:
    - Flat: unit is filled, bed is None
    - PG: bed is filled, unit is None (but bed.room.unit gives the unit)
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='occupancies')
    
    # For Flats
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name='occupancies', 
                            null=True, blank=True, limit_choices_to={'unit_type': 'FLAT'})
    
    # For PGs
    bed = models.ForeignKey(Bed, on_delete=models.CASCADE, related_name='occupancies',
                           null=True, blank=True)
    
    rent = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    deposit = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    
    # Primary tenant designation (for flats only)
    is_primary = models.BooleanField(
        default=False,
        help_text="Mark as primary tenant. Only primary tenant gets rent records for shared flats."
    )
    
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Notice Period Management
    notice_date = models.DateField(
        null=True, blank=True,
        help_text="Date when tenant gave notice to vacate"
    )
    expected_checkout_date = models.DateField(
        null=True, blank=True,
        help_text="Expected date of checkout after notice period"
    )
    notice_reason = models.TextField(
        blank=True,
        help_text="Reason for leaving (optional)"
    )
    
    agreement_document = models.FileField(upload_to='agreements/', blank=True, null=True)
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-start_date']
        verbose_name = "Occupancy"
        verbose_name_plural = "Occupancies"
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['unit', 'is_active']),
            models.Index(fields=['bed', 'is_active']),
            models.Index(fields=['is_active', 'start_date']),
            models.Index(fields=['tenant', 'is_active', 'start_date']),
        ]
    
    def __str__(self):
        location = self.unit.unit_number if self.unit else f"{self.bed.room.unit.unit_number} - {self.bed.bed_number}"
        return f"{self.tenant.name} - {location}"
    
    def clean(self):
        """Validate that either unit OR bed is set, not both"""
        from django.core.exceptions import ValidationError
        if not self.unit and not self.bed:
            raise ValidationError("Either unit (for flat) or bed (for PG) must be set.")
        if self.unit and self.bed:
            raise ValidationError("Cannot set both unit and bed. Use unit for flats, bed for PGs.")
        if self.unit and self.unit.unit_type != 'FLAT':
            raise ValidationError("Unit must be of type FLAT.")
        if self.bed and self.bed.room.unit.unit_type != 'PG':
            raise ValidationError("Bed must belong to a PG unit.")
    
    def save(self, *args, **kwargs):
        """Override save to update unit/bed status"""
        self.full_clean()
        super().save(*args, **kwargs)
        
        # Update unit/bed status
        if self.unit:
            self.unit.update_status()
        if self.bed:
            self.bed.update_status()
    
    @property
    def location(self):
        """Get human-readable location"""
        if self.unit:
            return f"{self.unit.building.name} - {self.unit.unit_number}"
        elif self.bed:
            return f"{self.bed.room.unit.building.name} - {self.bed.room.unit.unit_number} - {self.bed.bed_number}"
        return "Unknown"
    
    @property
    def account(self):
        """Get account from tenant"""
        return self.tenant.account
    
    @property
    def building(self):
        """Get building for this occupancy"""
        if self.unit:
            return self.unit.building
        elif self.bed:
            return self.bed.room.unit.building
        return None
    
    @property
    def required_notice_days(self):
        """Get required notice period in days"""
        building = self.building
        if building:
            return building.notice_period_days
        return 30  # Default
    
    @property
    def has_given_notice(self):
        """Check if tenant has given notice"""
        return self.notice_date is not None
    
    @property
    def days_since_notice(self):
        """Days since notice was given"""
        if not self.notice_date:
            return None
        from django.utils import timezone
        today = timezone.now().date()
        return (today - self.notice_date).days
    
    @property
    def days_until_eligible(self):
        """Days remaining until eligible for checkout"""
        if not self.notice_date:
            return self.required_notice_days
        days_since = self.days_since_notice
        remaining = self.required_notice_days - days_since
        return max(0, remaining)
    
    @property
    def is_eligible_for_checkout(self):
        """Check if tenant has completed notice period"""
        if not self.notice_date:
            return False
        return self.days_until_eligible <= 0
    
    @property
    def notice_status(self):
        """Get notice status for display"""
        if not self.notice_date:
            return 'NO_NOTICE'
        if self.is_eligible_for_checkout:
            return 'ELIGIBLE'
        return 'IN_NOTICE_PERIOD'
    
    def calculate_expected_checkout(self):
        """Calculate expected checkout date based on notice date"""
        if not self.notice_date:
            return None
        from datetime import timedelta
        return self.notice_date + timedelta(days=self.required_notice_days)

