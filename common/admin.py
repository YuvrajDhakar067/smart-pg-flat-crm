from django.contrib import admin
from .models import (
    SiteSettings, ContentBlock, StatusLabel, 
    NotificationTemplate, PricingPlan, HelpArticle, EditingSession
)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ['site_name', 'company_name', 'company_email', 'updated_at']
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


@admin.register(StatusLabel)
class StatusLabelAdmin(admin.ModelAdmin):
    list_display = ['status_type', 'code', 'label', 'color', 'is_active', 'order']
    list_filter = ['status_type', 'is_active']
    search_fields = ['code', 'label']
    list_editable = ['label', 'color', 'is_active', 'order']


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ['template_type', 'subject', 'is_active', 'updated_at']
    list_filter = ['is_active', 'template_type']
    search_fields = ['subject', 'message']
    list_editable = ['is_active']


@admin.register(PricingPlan)
class PricingPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'billing_period', 'max_buildings', 'max_units', 'is_active', 'is_popular', 'order']
    list_filter = ['is_active', 'is_popular', 'billing_period']
    search_fields = ['name', 'slug']
    list_editable = ['is_active', 'is_popular', 'order']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(HelpArticle)
class HelpArticleAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'is_active', 'views', 'order']
    list_filter = ['category', 'is_active']
    search_fields = ['title', 'content']
    list_editable = ['is_active', 'order']
    prepopulated_fields = {'slug': ('title',)}


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

