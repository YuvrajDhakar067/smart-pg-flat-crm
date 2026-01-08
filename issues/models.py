from django.db import models
from units.models import Unit
from tenants.models import Tenant


class Issue(models.Model):
    """Complaint/Issue tracking"""
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('ASSIGNED', 'Assigned'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]
    
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name='issues')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='issues', 
                              null=True, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM')
    assigned_to = models.CharField(max_length=255, blank=True, 
                                  help_text="e.g., 'Plumber', 'Electrician', 'Manager'")
    raised_date = models.DateTimeField(auto_now_add=True)
    resolved_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-raised_date']
        verbose_name = "Issue"
        verbose_name_plural = "Issues"
        indexes = [
            models.Index(fields=['unit', 'status']),
            models.Index(fields=['unit', 'priority']),
            models.Index(fields=['unit', 'status', 'priority']),
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['status', 'raised_date']),
        ]
    
    def __str__(self):
        return f"{self.unit} - {self.title} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        """Auto-set resolved_date when status changes to RESOLVED"""
        if self.status == 'RESOLVED' and not self.resolved_date:
            from django.utils import timezone
            self.resolved_date = timezone.now()
        elif self.status != 'RESOLVED':
            self.resolved_date = None
        super().save(*args, **kwargs)
    
    @property
    def account(self):
        """Get account from unit"""
        return self.unit.account

