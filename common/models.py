from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class SiteSettings(models.Model):
    """Singleton model for site-wide settings"""
    site_name = models.CharField(max_length=200, default='Smart PG & Flat Management CRM')
    site_tagline = models.CharField(max_length=255, default='One dashboard to know everything about your property')
    company_name = models.CharField(max_length=200, default='Property Management Co.')
    company_email = models.CharField(max_length=200, default='info@example.com')
    company_phone = models.CharField(max_length=20, default='+91 1234567890')
    company_address = models.TextField(default='Your Company Address')
    primary_color = models.CharField(max_length=7, default='#2563eb', help_text='Hex color code')
    secondary_color = models.CharField(max_length=7, default='#64748b', help_text='Hex color code')
    enable_tenant_portal = models.BooleanField(default=False, help_text='Allow tenants to login')
    enable_sms_notifications = models.BooleanField(default=False)
    enable_email_notifications = models.BooleanField(default=False)
    auto_generate_rent = models.BooleanField(default=False, help_text='Auto-create rent entries each month')
    rent_due_day = models.IntegerField(
        default=5,
        help_text='Day of month when rent is due',
        validators=[MinValueValidator(1), MaxValueValidator(28)]
    )
    currency_symbol = models.CharField(max_length=10, default='₹')
    currency_code = models.CharField(max_length=10, default='INR')
    footer_text = models.TextField(default='Built with ❤️ for Property Owners & Managers')
    
    # Property Limits
    max_properties_per_owner = models.IntegerField(
        default=10,
        help_text='Maximum number of properties (buildings) each owner can add. Set to 0 for unlimited.',
        validators=[MinValueValidator(0)]
    )
    
    # Manager Limits
    max_managers_per_owner = models.IntegerField(
        default=5,
        help_text='Maximum number of managers each owner can create. Set to 0 for unlimited.',
        validators=[MinValueValidator(0)]
    )
    
    # About & Contact Information
    about_us = models.TextField(
        blank=True,
        help_text='About Us content (HTML allowed)'
    )
    contact_email = models.EmailField(
        blank=True,
        help_text='Contact email for support/inquiries'
    )
    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        help_text='Contact phone number'
    )
    contact_address = models.TextField(
        blank=True,
        help_text='Contact address'
    )
    terms_and_conditions = models.TextField(
        blank=True,
        help_text='Terms and Conditions (HTML allowed)'
    )
    privacy_policy = models.TextField(
        blank=True,
        help_text='Privacy Policy (HTML allowed)'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Site Settings'
        verbose_name_plural = 'Site Settings'
    
    @classmethod
    def load(cls):
        """Get or create the singleton instance"""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
    
    def __str__(self):
        return self.site_name


class ContentBlock(models.Model):
    BLOCK_TYPE_CHOICES = [
        ('dashboard_welcome', 'Dashboard Welcome Message'),
        ('vacancy_alert', 'Vacancy Alert Message'),
        ('rent_reminder', 'Rent Reminder Message'),
        ('issue_notification', 'Issue Notification Message'),
        ('help_text', 'Help Text'),
        ('terms', 'Terms and Conditions'),
        ('privacy', 'Privacy Policy'),
        ('about', 'About Us'),
        ('custom', 'Custom Block'),
    ]
    
    key = models.CharField(max_length=100, unique=True, help_text='Unique identifier for this content')
    block_type = models.CharField(max_length=50, choices=BLOCK_TYPE_CHOICES, default='custom')
    title = models.CharField(max_length=200, blank=True)
    content = models.TextField(help_text='HTML content allowed')
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0, help_text='Display order')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Content Block'
        verbose_name_plural = 'Content Blocks'
        ordering = ['order', 'key']
    
    def __str__(self):
        return f"{self.key} ({self.block_type})"


class StatusLabel(models.Model):
    STATUS_TYPE_CHOICES = [
        ('unit', 'Unit Status'),
        ('rent', 'Rent Status'),
        ('issue', 'Issue Status'),
        ('occupancy', 'Occupancy Status'),
    ]
    
    status_type = models.CharField(max_length=50, choices=STATUS_TYPE_CHOICES)
    code = models.CharField(max_length=50, help_text="Internal code (e.g., 'occupied', 'vacant')")
    label = models.CharField(max_length=100, help_text='Display label')
    color = models.CharField(max_length=7, default='#64748b', help_text='Hex color code')
    icon = models.CharField(max_length=50, blank=True, help_text='Bootstrap icon class')
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Status Label'
        verbose_name_plural = 'Status Labels'
        ordering = ['status_type', 'order']
        unique_together = [('status_type', 'code')]
    
    def __str__(self):
        return f"{self.status_type}: {self.label}"


class NotificationTemplate(models.Model):
    TEMPLATE_TYPE_CHOICES = [
        ('rent_due', 'Rent Due Reminder'),
        ('rent_paid', 'Rent Payment Confirmation'),
        ('issue_raised', 'Issue Raised Notification'),
        ('issue_resolved', 'Issue Resolved Notification'),
        ('tenant_welcome', 'Tenant Welcome Message'),
        ('vacancy_alert', 'Vacancy Alert'),
    ]
    
    template_type = models.CharField(max_length=50, choices=TEMPLATE_TYPE_CHOICES, unique=True)
    subject = models.CharField(max_length=200, help_text='Email subject or SMS prefix')
    message = models.TextField(help_text='Use {{variable}} for dynamic content')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Notification Template'
        verbose_name_plural = 'Notification Templates'
    
    def __str__(self):
        return f"{self.template_type}: {self.subject}"


# PricingPlan and HelpArticle models removed - not used anywhere in the application
# If needed in future, can be re-added

# class PricingPlan(models.Model):
#     """Removed - not used"""
#     pass
#
# class HelpArticle(models.Model):
#     """Removed - not used"""
#     pass


class EditingSession(models.Model):
    """
    Tracks active editing sessions to prevent concurrent edits.
    Shows "Someone is editing this" warnings.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='editing_sessions'
    )
    
    # Resource being edited
    resource_type = models.CharField(max_length=50)  # 'occupancy', 'rent', 'unit', 'bed', etc.
    resource_id = models.IntegerField()
    
    # Session info
    started_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Additional context
    action = models.CharField(max_length=50, default='edit')  # 'edit', 'assign', 'checkout', etc.
    
    class Meta:
        unique_together = ['resource_type', 'resource_id']
        indexes = [
            models.Index(fields=['resource_type', 'resource_id']),
            models.Index(fields=['last_activity']),
        ]
        ordering = ['-last_activity']
    
    def __str__(self):
        return f"{self.user.username} editing {self.resource_type}#{self.resource_id}"
    
    def is_active(self, timeout_seconds=300):
        """Check if session is still active (default 5 minutes)"""
        if not self.last_activity:
            return False
        elapsed = (timezone.now() - self.last_activity).total_seconds()
        return elapsed < timeout_seconds
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = timezone.now()
        self.save(update_fields=['last_activity'])
