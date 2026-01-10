from django.db import models
from django.core.validators import (
    MinValueValidator, MaxValueValidator
)


class SiteSettings(models.Model):
    """
    Site-wide settings (singleton pattern - only one instance)
    """
    site_name = models.CharField(max_length=200, default="Smart PG & Flat Management CRM")
    site_tagline = models.CharField(max_length=500, blank=True, default="")
    company_name = models.CharField(max_length=200, blank=True, default="")
    company_email = models.EmailField(blank=True, default="")
    company_phone = models.CharField(max_length=20, blank=True, default="")
    company_address = models.TextField(blank=True, default="")
    
    # Branding
    primary_color = models.CharField(max_length=7, blank=True, default="#007bff")
    secondary_color = models.CharField(max_length=7, blank=True, default="#6c757d")
    
    # Features
    enable_tenant_portal = models.BooleanField(default=False)
    enable_sms_notifications = models.BooleanField(default=False)
    enable_email_notifications = models.BooleanField(default=True)
    
    # Rent Settings
    auto_generate_rent = models.BooleanField(default=True)
    rent_due_day = models.IntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(28)])
    
    # Currency
    currency_symbol = models.CharField(max_length=10, default="₹")
    currency_code = models.CharField(max_length=3, default="INR")
    
    # Footer
    footer_text = models.TextField(blank=True, default="")
    
    # Property and Manager Limits (added in migration 0003)
    max_properties_per_owner = models.IntegerField(
        default=10,
        help_text="Maximum number of properties (buildings) each owner can add. Set to 0 for unlimited. Default: 10",
        verbose_name="Max Properties Per Owner"
    )
    max_managers_per_owner = models.IntegerField(
        default=5,
        help_text="Maximum number of managers each owner can create. Set to 0 for unlimited. Default: 5",
        verbose_name="Max Managers Per Owner"
    )
    
    # About & Contact (added in migration 0003)
    about_us = models.TextField(
        blank=True, 
        default="",
        help_text="About us content displayed on the website",
        verbose_name="About Us"
    )
    contact_email = models.EmailField(
        blank=True, 
        default="",
        help_text="Contact email address for customer support",
        verbose_name="Contact Email"
    )
    contact_phone = models.CharField(
        max_length=20, 
        blank=True, 
        default="",
        help_text="Contact phone number for customer support",
        verbose_name="Contact Phone"
    )
    contact_address = models.TextField(
        blank=True, 
        default="",
        help_text="Contact address for customer support",
        verbose_name="Contact Address"
    )
    
    # Legal Pages (added in migration 0003)
    terms_and_conditions = models.TextField(
        blank=True, 
        default="",
        help_text="Terms and conditions content for the website",
        verbose_name="Terms and Conditions"
    )
    privacy_policy = models.TextField(
        blank=True, 
        default="",
        help_text="Privacy policy content for the website",
        verbose_name="Privacy Policy"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Site Settings'
        verbose_name_plural = 'Site Settings'
    
    @classmethod
    def load(cls):
        """Get or create the singleton instance - handles missing columns gracefully"""
        from django.db import connection
        
        try:
            # First, check which columns exist in the database
            existing_columns = set()
            try:
                if 'postgresql' in connection.vendor:
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name='common_sitesettings'
                        """)
                        existing_columns = {row[0] for row in cursor.fetchall()}
                elif 'sqlite' in connection.vendor:
                    with connection.cursor() as cursor:
                        cursor.execute("PRAGMA table_info(common_sitesettings)")
                        existing_columns = {row[1] for row in cursor.fetchall()}
            except Exception:
                # If we can't check columns, try Django ORM and let it fail gracefully
                existing_columns = None
            
            # Try to get existing object using raw SQL to avoid missing columns
            if existing_columns:
                try:
                    # Build SELECT query with only existing columns
                    base_columns = ['id', 'site_name', 'currency_symbol', 'currency_code', 
                                    'company_name', 'company_email', 'company_phone', 'company_address',
                                    'site_tagline', 'primary_color', 'secondary_color',
                                    'enable_tenant_portal', 'enable_sms_notifications', 'enable_email_notifications',
                                    'auto_generate_rent', 'rent_due_day', 'footer_text']
                    
                    # Only include columns that exist
                    select_columns = [col for col in base_columns if col in existing_columns]
                    
                    if select_columns and 'id' in select_columns:
                        if 'postgresql' in connection.vendor:
                            with connection.cursor() as cursor:
                                cursor.execute(f"""
                                    SELECT {', '.join(select_columns)}
                                    FROM common_sitesettings WHERE id = 1
                                """)
                                row = cursor.fetchone()
                                if row:
                                    obj = cls()
                                    obj.pk = 1
                                    # Map columns to attributes
                                    col_map = dict(zip(select_columns, row))
                                    for col, val in col_map.items():
                                        setattr(obj, col, val)
                                    # Set defaults for missing fields (won't be saved to DB)
                                    obj.max_properties_per_owner = 10
                                    obj.max_managers_per_owner = 5
                                    return obj
                except Exception:
                    pass
            
            # Fallback: Try Django ORM (will fail if columns don't exist, but we'll catch it)
            try:
                obj, _ = cls.objects.get_or_create(pk=1)
                # Set defaults for missing fields
                if not hasattr(obj, 'max_properties_per_owner'):
                    obj.max_properties_per_owner = 10
                if not hasattr(obj, 'max_managers_per_owner'):
                    obj.max_managers_per_owner = 5
                return obj
            except Exception as create_error:
                # If get_or_create fails due to missing columns
                error_msg = str(create_error).lower()
                if 'does not exist' in error_msg or 'no such column' in error_msg or 'undefinedcolumn' in error_msg:
                    # Return a minimal object with defaults (not saved to DB)
                    obj = cls()
                    obj.pk = 1
                    obj.site_name = "Smart PG & Flat Management CRM"
                    obj.currency_symbol = "₹"
                    obj.max_properties_per_owner = 10
                    obj.max_managers_per_owner = 5
                    return obj
                raise
        except Exception as e:
            # Last resort: return a minimal object with defaults
            error_msg = str(e).lower()
            if 'does not exist' in error_msg or 'no such column' in error_msg or 'undefinedcolumn' in error_msg:
                obj = cls()
                obj.pk = 1
                obj.site_name = "Smart PG & Flat Management CRM"
                obj.currency_symbol = "₹"
                obj.max_properties_per_owner = 10
                obj.max_managers_per_owner = 5
                return obj
            raise
    
    def __str__(self):
        return self.site_name


class ContentBlock(models.Model):
    BLOCK_TYPE_CHOICES = [
        ('text', 'Text'),
        ('html', 'HTML'),
        ('image', 'Image'),
        ('video', 'Video'),
    ]
    
    key = models.SlugField(unique=True, help_text="Unique identifier for this content block")
    block_type = models.CharField(max_length=20, choices=BLOCK_TYPE_CHOICES, default='text')
    title = models.CharField(max_length=200, blank=True)
    content = models.TextField(blank=True)
    image = models.ImageField(upload_to='content_blocks/', blank=True, null=True)
    video_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order', 'title']
        verbose_name = 'Content Block'
        verbose_name_plural = 'Content Blocks'
    
    def __str__(self):
        return self.title or self.key


# StatusLabel and NotificationTemplate kept in models but not actively used
# Can be enabled if needed for future features

class StatusLabel(models.Model):
    """Custom status labels for various entities"""
    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default="#007bff")
    description = models.TextField(blank=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class NotificationTemplate(models.Model):
    """Templates for notifications"""
    name = models.CharField(max_length=100, unique=True)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


# EditingSession model for concurrent editing detection
class EditingSession(models.Model):
    """Track active editing sessions to prevent concurrent edits"""
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='editing_sessions')
    resource_type = models.CharField(max_length=50)  # e.g., 'building', 'unit', 'tenant'
    resource_id = models.IntegerField()
    action = models.CharField(max_length=20, default='edit')  # 'edit', 'view'
    started_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['resource_type', 'resource_id', 'user']
        indexes = [
            models.Index(fields=['resource_type', 'resource_id']),
            models.Index(fields=['last_activity']),
        ]
    
    def is_active(self, timeout_seconds=300):
        """Check if session is still active (default 5 minutes)"""
        from django.utils import timezone
        from datetime import timedelta
        return (timezone.now() - self.last_activity) < timedelta(seconds=timeout_seconds)
    
    def __str__(self):
        return f"{self.user.username} editing {self.resource_type} #{self.resource_id}"
