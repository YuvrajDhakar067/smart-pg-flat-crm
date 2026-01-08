from django.db import models
from django.conf import settings
from accounts.models import Account
import os


def tenant_document_path(instance, filename):
    """Generate upload path for tenant documents"""
    # Files will be uploaded to MEDIA_ROOT/tenant_docs/<tenant_id>/<filename>
    ext = filename.split('.')[-1]
    safe_filename = f"{instance.document_type}_{instance.tenant.id}.{ext}"
    return f"tenant_docs/{instance.tenant.id}/{safe_filename}"


class Tenant(models.Model):
    """Tenant - can occupy Flat or PG Bed"""
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='tenants')
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True)
    id_proof_type = models.CharField(max_length=50, blank=True, help_text="e.g., 'Aadhar', 'PAN', 'Driving License'")
    id_proof_number = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    emergency_contact = models.CharField(max_length=15, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "Tenant"
        verbose_name_plural = "Tenants"
        indexes = [
            models.Index(fields=['account', 'name']),
            models.Index(fields=['account', 'phone']),
            models.Index(fields=['account', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.phone})"
    
    @property
    def current_occupancy(self):
        """Get current active occupancy"""
        return self.occupancies.filter(is_active=True).first()
    
    @property
    def document_count(self):
        """Get count of uploaded documents"""
        return self.documents.count()
    
    @property
    def verified_documents(self):
        """Get count of verified documents"""
        return self.documents.filter(verification_status='VERIFIED').count()


class TenantDocument(models.Model):
    """Store tenant documents like Aadhaar, PAN, Police Verification, etc."""
    
    DOCUMENT_TYPES = [
        ('AADHAAR', 'Aadhaar Card'),
        ('PAN', 'PAN Card'),
        ('PASSPORT', 'Passport'),
        ('DRIVING_LICENSE', 'Driving License'),
        ('VOTER_ID', 'Voter ID'),
        ('POLICE_VERIFICATION', 'Police Verification'),
        ('RENT_AGREEMENT', 'Rent Agreement'),
        ('PHOTO', 'Photograph'),
        ('ADDRESS_PROOF', 'Address Proof'),
        ('EMPLOYMENT_PROOF', 'Employment Proof'),
        ('OTHER', 'Other Document'),
    ]
    
    VERIFICATION_STATUS = [
        ('PENDING', 'Pending Verification'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
        ('EXPIRED', 'Expired'),
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPES)
    document_number = models.CharField(max_length=50, blank=True, help_text="Document ID/Number if applicable")
    file = models.FileField(upload_to=tenant_document_path)
    original_filename = models.CharField(max_length=255, blank=True)
    file_size = models.IntegerField(default=0, help_text="File size in bytes")
    
    # Verification
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS, default='PENDING')
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name='verified_documents'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(blank=True)
    
    # Expiry tracking
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    
    # Metadata
    notes = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name='uploaded_documents'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Tenant Document"
        verbose_name_plural = "Tenant Documents"
        indexes = [
            models.Index(fields=['tenant', 'document_type']),
            models.Index(fields=['tenant', 'verification_status']),
            models.Index(fields=['verification_status']),
        ]
    
    def __str__(self):
        return f"{self.tenant.name} - {self.get_document_type_display()}"
    
    def save(self, *args, **kwargs):
        # Store original filename and file size
        if self.file and hasattr(self.file, 'name'):
            if not self.original_filename:
                self.original_filename = os.path.basename(self.file.name)
            if hasattr(self.file, 'size'):
                self.file_size = self.file.size
        super().save(*args, **kwargs)
    
    @property
    def file_extension(self):
        """Get file extension"""
        if self.file:
            return os.path.splitext(self.file.name)[1].lower()
        return ''
    
    @property
    def is_image(self):
        """Check if document is an image"""
        return self.file_extension in ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    
    @property
    def is_pdf(self):
        """Check if document is a PDF"""
        return self.file_extension == '.pdf'
    
    @property
    def is_expired(self):
        """Check if document has expired"""
        if self.expiry_date:
            from django.utils import timezone
            return self.expiry_date < timezone.now().date()
        return False
    
    @property
    def formatted_file_size(self):
        """Get human-readable file size"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

