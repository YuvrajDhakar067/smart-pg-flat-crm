from django.db import models
from django.core.validators import MinValueValidator, FileExtensionValidator
from occupancy.models import Occupancy


def rent_payment_proof_path(instance, filename):
    """File will be uploaded to MEDIA_ROOT/rent_proofs/<rent_id>/<filename>"""
    return f'rent_proofs/{instance.id}/{filename}'


class Rent(models.Model):
    """Monthly rent ledger - tracks rent payments"""
    STATUS_CHOICES = [
        ('PAID', 'Paid'),
        ('PENDING', 'Pending'),
        ('PARTIAL', 'Partial'),
    ]
    
    occupancy = models.ForeignKey(Occupancy, on_delete=models.CASCADE, related_name='rents')
    month = models.DateField(help_text="First day of the month")
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], 
                                 help_text="Expected rent amount")
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, 
                                      validators=[MinValueValidator(0)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    paid_date = models.DateField(null=True, blank=True)
    payment_proof = models.FileField(
        upload_to=rent_payment_proof_path,
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'])],
        help_text="Upload payment proof (receipt, screenshot, etc.)"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-month']
        unique_together = ['occupancy', 'month']
        verbose_name = "Rent"
        verbose_name_plural = "Rents"
        indexes = [
            models.Index(fields=['occupancy', 'month']),
            models.Index(fields=['occupancy', 'status']),
            models.Index(fields=['month', 'status']),
            models.Index(fields=['occupancy', 'month', 'status']),
        ]
    
    def __str__(self):
        return f"{self.occupancy.tenant.name} - {self.month.strftime('%B %Y')} - {self.get_status_display()}"
    
    def save(self, *args, **kwargs):
        """Auto-update status based on paid_amount"""
        if self.amount is not None:
            if self.paid_amount >= self.amount:
                self.status = 'PAID'
                if not self.paid_date:
                    from django.utils import timezone
                    self.paid_date = timezone.now().date()
            elif self.paid_amount > 0:
                self.status = 'PARTIAL'
            else:
                self.status = 'PENDING'
        else:
            # If amount is not set, default to PENDING
            self.status = 'PENDING'
        
        super().save(*args, **kwargs)
    
    @property
    def pending_amount(self):
        """Calculate pending amount"""
        if self.amount is None:
            return 0
        return self.amount - self.paid_amount
    
    @property
    def account(self):
        """Get account from occupancy"""
        return self.occupancy.account

