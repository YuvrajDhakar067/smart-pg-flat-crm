from django.contrib import admin
from .models import Account


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    """
    Account Management - Only administrators can create accounts.
    
    To create a new owner account:
    1. Create an Account here (name, plan, etc.)
    2. Go to Users and create a User with:
       - Link to the Account you just created
       - Role: OWNER
       - Set username, email, and password
    3. The owner can then login and use the system
    """
    list_display = ['name', 'plan', 'is_active', 'owner_count', 'created_at']
    list_filter = ['plan', 'is_active', 'created_at']
    search_fields = ['name', 'phone']
    list_editable = ['is_active']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'plan', 'is_active'),
            'description': 'Create an account first, then create an owner user in the Users section.'
        }),
        ('Contact Information', {
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