from django.contrib.auth.models import AbstractUser
from django.db import models
from accounts.models import Account


class User(AbstractUser):
    """Custom User model - Owner/Manager"""
    ROLE_CHOICES = [
        ('OWNER', 'Owner'),
        ('MANAGER', 'Manager'),
    ]
    
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='users')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='OWNER')
    phone = models.CharField(max_length=15, blank=True)
    
    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

