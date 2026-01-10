from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    User Management - Create owners and managers here.
    
    IMPORTANT: Public registration is disabled. Only admins can create users.
    
    To create a new owner:
    1. First create an Account in the Accounts section
    2. Then create a User here with:
       - Select the Account you created
       - Set Role to 'OWNER'
       - Set username, email, and password
    3. The owner can then login and start using the system
    
    To create a manager:
    1. Select an existing Account
    2. Create a User with Role 'MANAGER'
    3. The owner can then grant building access to this manager
    """
    list_display = ['username', 'email', 'account', 'role', 'is_active', 'date_joined']
    list_filter = ['role', 'is_active', 'account']
    search_fields = ['username', 'email', 'account__name']
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Account Information', {
            'fields': ('account', 'role', 'phone'),
            'description': 'Account is required. Create an Account first if it does not exist.'
        }),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Account Information', {
            'fields': ('account', 'role', 'phone'),
            'description': 'IMPORTANT: Account must be created first. Public registration is disabled.'
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        """Make account readonly for existing users to prevent breaking relationships"""
        readonly = list(super().get_readonly_fields(request, obj))
        if obj:  # Editing existing user
            readonly.append('account')
        return readonly

