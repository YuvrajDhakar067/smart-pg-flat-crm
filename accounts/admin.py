from django.contrib import admin
from .models import Account
from buildings.models import Building
from users.models import User


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    """
    ⭐ CLIENT ACCOUNT MANAGEMENT ⭐
    
    Use this to create new client accounts and set custom limits for each client.
    
    STEP-BY-STEP: How to Add a New Client (Owner)
    ──────────────────────────────────────────────
    1. Click "Add Account" button above
    2. Fill in:
       - Name: Client's company/business name
       - Plan: Select FREE, BASIC, PRO, or ENTERPRISE
       - Is Active: Check this to enable the account
       - Max Properties: Set custom limit (leave blank to use site default)
       - Max Managers: Set custom limit (leave blank to use site default)
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
    
    ⚠️ IMPORTANT: Limits are PER ACCOUNT (PER CLIENT)
    - Each client can have different limits
    - Leave blank to use site-wide defaults
    - Set to 0 for unlimited
    - Set a number to enforce that limit for this client only
    """
    list_display = ['name', 'plan', 'is_active', 'limits_display', 'usage_display', 'owner_count', 'created_at']
    list_filter = ['plan', 'is_active', 'created_at']
    search_fields = ['name', 'phone']
    list_editable = ['is_active']
    
    fieldsets = (
        ('⭐ Basic Information (REQUIRED)', {
            'fields': ('name', 'plan', 'is_active'),
            'description': 'Create an account for your client. After saving, go to Users section to create the owner user.'
        }),
        ('🎯 Custom Limits (PER CLIENT)', {
            'fields': ('max_properties', 'max_managers'),
            'description': (
                '⚠️ Set custom limits for THIS CLIENT ONLY. '
                'Leave blank to use site-wide defaults from Site Settings. '
                'Set to 0 for unlimited. Each client can have different limits!'
            ),
            'classes': ('wide',)
        }),
        ('📊 Current Usage (Read-only)', {
            'fields': ('properties_usage_display', 'managers_usage_display'),
            'description': 'Current usage vs limits for this account',
            'classes': ('collapse',)
        }),
        ('Contact Information (Optional)', {
            'fields': ('phone', 'address')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'properties_usage_display', 'managers_usage_display']
    
    def owner_count(self, obj):
        """Show number of owners for this account"""
        try:
            return obj.users.filter(role='OWNER').count()
        except Exception:
            return 0
    owner_count.short_description = 'Owners'
    
    def user_count(self, obj):
        """Show total number of users (owners + managers)"""
        try:
            return obj.users.count()
        except Exception:
            return 0
    user_count.short_description = 'Total Users'
    
    def limits_display(self, obj):
        """Show the limits for this account"""
        if obj.pk:
            max_props = obj.get_max_properties()
            max_mgrs = obj.get_max_managers()
            props_text = f"{max_props}" if max_props > 0 else "∞"
            mgrs_text = f"{max_mgrs}" if max_mgrs > 0 else "∞"
            return f"Props: {props_text} | Mgrs: {mgrs_text}"
        return "-"
    limits_display.short_description = 'Limits'
    
    def usage_display(self, obj):
        """Show current usage"""
        if obj.pk:
            try:
                props_count = Building.objects.filter(account=obj).count()
                mgrs_count = User.objects.filter(account=obj, role='MANAGER').count()
                return f"Props: {props_count} | Mgrs: {mgrs_count}"
            except Exception:
                return "-"
        return "-"
    usage_display.short_description = 'Usage'
    
    def properties_usage_display(self, obj):
        """Show properties usage in detail view"""
        if obj.pk:
            try:
                current = Building.objects.filter(account=obj).count()
                limit = obj.get_max_properties()
                limit_text = f"{limit}" if limit > 0 else "Unlimited"
                percentage = (current / limit * 100) if limit > 0 else 0
                status = "✅" if (limit == 0 or current < limit) else "⚠️"
                return f"{status} {current} / {limit_text} properties ({percentage:.0f}%)"
            except Exception:
                return "Error calculating usage"
        return "Save account first to see usage"
    properties_usage_display.short_description = 'Properties Usage'
    
    def managers_usage_display(self, obj):
        """Show managers usage in detail view"""
        if obj.pk:
            try:
                current = User.objects.filter(account=obj, role='MANAGER').count()
                limit = obj.get_max_managers()
                limit_text = f"{limit}" if limit > 0 else "Unlimited"
                percentage = (current / limit * 100) if limit > 0 else 0
                status = "✅" if (limit == 0 or current < limit) else "⚠️"
                return f"{status} {current} / {limit_text} managers ({percentage:.0f}%)"
            except Exception:
                return "Error calculating usage"
        return "Save account first to see usage"
    managers_usage_display.short_description = 'Managers Usage'