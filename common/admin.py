from django.contrib import admin
from .models import (
    SiteSettings, ContentBlock, EditingSession
    # StatusLabel, NotificationTemplate - kept for future use but not actively used
    # PricingPlan, HelpArticle - removed as unused
)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ['site_name', 'company_name', 'company_email', 'max_properties_per_owner', 'max_managers_per_owner', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('site_name', 'site_tagline', 'company_name', 'company_email', 
                      'company_phone', 'company_address')
        }),
        ('Branding', {
            'fields': ('primary_color', 'secondary_color')
        }),
        ('Features', {
            'fields': ('enable_tenant_portal', 'enable_sms_notifications', 
                      'enable_email_notifications')
        }),
        ('Rent Settings', {
            'fields': ('auto_generate_rent', 'rent_due_day')
        }),
        ('Property Limits', {
            'fields': ('max_properties_per_owner',),
            'description': 'Set the maximum number of properties each owner can add. Set to 0 for unlimited.'
        }),
        ('Manager Limits', {
            'fields': ('max_managers_per_owner',),
            'description': 'Set the maximum number of managers each owner can create. Set to 0 for unlimited.'
        }),
        ('About & Contact', {
            'fields': ('about_us', 'contact_email', 'contact_phone', 'contact_address')
        }),
        ('Legal Pages', {
            'fields': ('terms_and_conditions', 'privacy_policy')
        }),
        ('Currency', {
            'fields': ('currency_symbol', 'currency_code')
        }),
        ('Footer', {
            'fields': ('footer_text',)
        }),
    )
    
    def has_add_permission(self, request):
        # Only allow one instance
        return not SiteSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion
        return False


@admin.register(ContentBlock)
class ContentBlockAdmin(admin.ModelAdmin):
    list_display = ['key', 'block_type', 'title', 'is_active', 'order']
    list_filter = ['block_type', 'is_active']
    search_fields = ['key', 'title', 'content']
    list_editable = ['is_active', 'order']


# StatusLabel and NotificationTemplate kept in models but not registered in admin
# as they're not actively used. Can be enabled if needed for future features.

# PricingPlan and HelpArticle removed - not used anywhere

@admin.register(EditingSession)
class EditingSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'resource_type', 'resource_id', 'action', 'started_at', 'last_activity', 'is_active_display']
    list_filter = ['resource_type', 'action', 'started_at']
    search_fields = ['user__username', 'user__email', 'resource_type']
    readonly_fields = ['started_at', 'last_activity']
    ordering = ['-last_activity']
    
    def is_active_display(self, obj):
        return obj.is_active()
    is_active_display.boolean = True
    is_active_display.short_description = 'Active'

