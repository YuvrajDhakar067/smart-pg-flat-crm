from django.contrib import admin
from .models import Account


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    """
    ⭐ CLIENT ACCOUNT MANAGEMENT ⭐
    
    Use this to create new client accounts for your product.
    
    STEP-BY-STEP: How to Add a New Client (Owner)
    ──────────────────────────────────────────────
    1. Click "Add Account" button above
    2. Fill in:
       - Name: Client's company/business name
       - Plan: Select FREE, BASIC, or PREMIUM
       - Is Active: Check this to enable the account
       - Phone: Client's contact number (optional)
       - Address: Client's address (optional)
    3. Click "Save"
    4. Go to "Users" section (in left sidebar)
    5. Click "Add User"
    6. Fill in:
       - Username: Choose a username for the owner
       - Email: Owner's email address
       - Password: Set a secure password
       - Account: Select the Account you just created
       - Role: Select "OWNER"
       - Phone: Owner's phone (optional)
    7. Click "Save"
    8. The owner can now login and use the system!
    
    The owner will be able to:
    - Add properties (up to the limit set in Site Settings)
    - Create managers (up to the limit set in Site Settings)
    - Manage tenants, rent, issues, etc.
    """
    list_display = ['name', 'plan', 'is_active', 'owner_count', 'user_count', 'created_at']
    list_filter = ['plan', 'is_active', 'created_at']
    search_fields = ['name', 'phone']
    list_editable = ['is_active']
    
    fieldsets = (
        ('⭐ Basic Information (REQUIRED)', {
            'fields': ('name', 'plan', 'is_active'),
            'description': 'Create an account for your client. After saving, go to Users section to create the owner user.'
        }),
        ('Contact Information (Optional)', {
            'fields': ('phone', 'address')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def owner_count(self, obj):
        """Show number of owners for this account"""
        return obj.users.filter(role='OWNER').count()
    owner_count.short_description = 'Owners'
    
    def user_count(self, obj):
        """Show total number of users (owners + managers)"""
        return obj.users.count()
    user_count.short_description = 'Total Users'