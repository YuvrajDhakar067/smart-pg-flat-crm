from django.db import models


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

