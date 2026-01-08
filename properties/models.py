from django.db import models
from django.contrib.auth.models import User
from accounts.models import Account
from django.core.validators import MinValueValidator


class Building(models.Model):
    """Building owned by an account - LEGACY MODEL (deprecated)"""
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='legacy_buildings')
    name = models.CharField(max_length=200)
    address = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.account.name})"
    
    @property
    def total_units(self):
        return self.units.count()
    
    @property
    def occupied_units(self):
        return self.units.filter(status='occupied').count()
    
    @property
    def vacant_units(self):
        return self.units.filter(status='vacant').count()
    
    @property
    def total_expected_rent(self):
        return sum(unit.expected_rent for unit in self.units.filter(status='occupied'))


class Unit(models.Model):
    """Unit (Flat or PG Room)"""
    UNIT_TYPE_CHOICES = [
        ('flat', 'Flat'),
        ('pg', 'PG Room'),
    ]
    
    STATUS_CHOICES = [
        ('occupied', 'Occupied'),
        ('vacant', 'Vacant'),
    ]
    
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='units')
    unit_type = models.CharField(max_length=20, choices=UNIT_TYPE_CHOICES)
    unit_number = models.CharField(max_length=50)  # e.g., "203", "PG-3 Bed-2"
    bhk = models.CharField(max_length=10, blank=True)  # "1BHK", "2BHK", "Double", "Single"
    expected_rent = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='vacant')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['unit_number']
        unique_together = ['building', 'unit_number']
    
    def __str__(self):
        return f"{self.building.name} - {self.unit_number} ({self.unit_type})"
    
    @property
    def current_tenant(self):
        return self.tenants.filter(is_active=True).first()


class Tenant(models.Model):
    """Tenant living in a unit"""
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name='tenants')
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True)
    move_in_date = models.DateField()
    move_out_date = models.DateField(null=True, blank=True)
    rent_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    deposit = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    is_active = models.BooleanField(default=True)
    agreement_document = models.FileField(upload_to='agreements/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-move_in_date']
    
    def __str__(self):
        return f"{self.name} - {self.unit}"
    
    @property
    def account(self):
        return self.unit.building.account


class Rent(models.Model):
    """Monthly rent record"""
    STATUS_CHOICES = [
        ('paid', 'Paid'),
        ('pending', 'Pending'),
        ('partial', 'Partial'),
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='rents')
    month = models.DateField()  # First day of the month
    expected_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    paid_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-month']
        unique_together = ['tenant', 'month']
    
    def __str__(self):
        return f"{self.tenant.name} - {self.month.strftime('%B %Y')} - {self.status}"
    
    @property
    def pending_amount(self):
        return self.expected_amount - self.paid_amount


class Issue(models.Model):
    """Complaint/Issue tracking"""
    STATUS_CHOICES = [
        ('raised', 'Raised'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name='issues')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='issues', null=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='raised')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    assigned_to = models.CharField(max_length=200, blank=True)  # e.g., "Plumber", "Electrician"
    raised_date = models.DateTimeField(auto_now_add=True)
    resolved_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-raised_date']
    
    def __str__(self):
        return f"{self.unit} - {self.title} ({self.status})"
    
    @property
    def account(self):
        return self.unit.building.account

