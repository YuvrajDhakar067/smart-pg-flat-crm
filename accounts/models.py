from django.db import models
from django.core.validators import MinValueValidator


class Account(models.Model):
    """Multi-tenant SaaS account - each customer has one account"""
    PLAN_CHOICES = [
        ('FREE', 'Free'),
        ('BASIC', 'Basic'),
        ('PRO', 'Pro'),
        ('ENTERPRISE', 'Enterprise'),
    ]
    
    name = models.CharField(max_length=255, help_text="Account/Business name")
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='FREE')
    is_active = models.BooleanField(default=True)
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    
    # Per-account limits (override site-wide defaults)
    # If None, uses site settings default. If set, uses this value. 0 = unlimited
    max_properties = models.IntegerField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Maximum number of properties (buildings) for this account. Leave blank to use site default. Set to 0 for unlimited."
    )
    max_managers = models.IntegerField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Maximum number of managers for this account. Leave blank to use site default. Set to 0 for unlimited."
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Account"
        verbose_name_plural = "Accounts"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_plan_display()})"
    
    @property
    def owner(self):
        """Get the owner user (first user with OWNER role)"""
        return self.users.filter(role='OWNER').first()
    
    def get_max_properties(self):
        """Get max properties limit for this account (checks account first, then site settings)"""
        if self.max_properties is not None:
            return self.max_properties
        # Fall back to site settings default
        from common.utils import get_site_settings
        site_settings = get_site_settings()
        return getattr(site_settings, 'max_properties_per_owner', 5)
    
    def get_max_managers(self):
        """Get max managers limit for this account (checks account first, then site settings)"""
        if self.max_managers is not None:
            return self.max_managers
        # Fall back to site settings default
        from common.utils import get_site_settings
        site_settings = get_site_settings()
        return getattr(site_settings, 'max_managers_per_owner', 5)

