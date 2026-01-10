from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    ⭐ USER MANAGEMENT - Create Owners and Managers ⭐
    
    IMPORTANT: Public registration is disabled. Only admins can create users.
    
    ──────────────────────────────────────────────────────────────
    HOW TO CREATE A NEW CLIENT (OWNER):
    ──────────────────────────────────────────────────────────────
    1. First, go to "Accounts" section and create an Account
    2. Then come back here and click "Add User"
    3. Fill in:
       - Username: Choose a unique username
       - Password: Set a secure password (user can change later)
       - Email: Owner's email address
       - Account: Select the Account you created in step 1
       - Role: Select "OWNER" (this is important!)
       - Phone: Optional
    4. Click "Save"
    5. The owner can now login at /accounts/login/
    
    ──────────────────────────────────────────────────────────────
    HOW TO CREATE A MANAGER:
    ──────────────────────────────────────────────────────────────
    1. Click "Add User"
    2. Fill in:
       - Username, Password, Email
       - Account: Select the Account that owns the properties
       - Role: Select "MANAGER"
    3. Click "Save"
    4. The owner can then grant building access to this manager
       (from the main application, not admin)
    """
    list_display = ['username', 'email', 'account', 'role', 'is_active', 'is_staff', 'date_joined']
    list_filter = ['role', 'is_active', 'is_staff', 'account']
    search_fields = ['username', 'email', 'account__name', 'phone']
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('⭐ Account Information (REQUIRED)', {
            'fields': ('account', 'role', 'phone'),
            'description': '⚠️ Account is required! If you don\'t see the account, go to Accounts section and create it first. Role must be OWNER for clients or MANAGER for staff.'
        }),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('⭐ Account Information (REQUIRED)', {
            'fields': ('account', 'role', 'phone'),
            'description': '⚠️ IMPORTANT: Account must be created first in Accounts section. Public registration is disabled. Role: OWNER for clients, MANAGER for staff.'
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        """Make account readonly for existing users to prevent breaking relationships"""
        readonly = list(super().get_readonly_fields(request, obj))
        if obj:  # Editing existing user
            readonly.append('account')
        return readonly

