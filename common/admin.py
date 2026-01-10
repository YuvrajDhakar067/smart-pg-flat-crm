from django.contrib import admin
from .models import (
    SiteSettings, ContentBlock, EditingSession
    # StatusLabel, NotificationTemplate - kept for future use but not actively used
    # PricingPlan, HelpArticle - removed as unused
)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    """
    Site Settings - Configure system-wide settings
    
    IMPORTANT: This is a singleton - only one instance exists.
    If you don't see an entry, click "Add Site Settings" to create it.
    
    Key Settings:
    - Property Limits: Control how many properties each owner can add
    - Manager Limits: Control how many managers each owner can create
    - Set to 0 for unlimited
    """
    
    def _field_exists(self, field_name):
        """Check if a field exists in the database"""
        try:
            from django.db import connection
            if 'sqlite' in connection.vendor:
                cursor = connection.cursor()
                cursor.execute("PRAGMA table_info(common_sitesettings)")
                columns = [row[1] for row in cursor.fetchall()]
                return field_name in columns
            elif 'postgresql' in connection.vendor:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name='common_sitesettings' 
                        AND column_name=%s
                    """, [field_name])
                    return cursor.fetchone() is not None
        except Exception:
            return False
        return False
    
    def get_list_display(self, request):
        """Dynamically get list_display, checking if columns exist"""
        base_fields = ['site_name', 'company_name', 'company_email', 'updated_at']
        
        # Check if new fields exist in database
        if self._field_exists('max_properties_per_owner'):
            base_fields.insert(-1, 'max_properties_per_owner')
        if self._field_exists('max_managers_per_owner'):
            base_fields.insert(-1, 'max_managers_per_owner')
        
        return base_fields
    
    def get_fieldsets(self, request, obj=None):
        """Dynamically get fieldsets, only including fields that exist"""
        base_fieldsets = [
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
        ]
        
        # Add Property Limits if field exists
        if self._field_exists('max_properties_per_owner'):
            base_fieldsets.append(('⚠️ Property Limits (IMPORTANT)', {
                'fields': ('max_properties_per_owner',),
                'description': 'Default maximum number of properties (buildings) each owner can add. Set to 0 for unlimited. ⚠️ NOTE: This is the DEFAULT limit. You can override this per-client in Accounts → Edit Account → Custom Limits. Each client can have different limits!'
            }))
        
        # Add Manager Limits if field exists
        if self._field_exists('max_managers_per_owner'):
            base_fieldsets.append(('⚠️ Manager Limits (IMPORTANT)', {
                'fields': ('max_managers_per_owner',),
                'description': 'Default maximum number of managers each owner can create. Set to 0 for unlimited. ⚠️ NOTE: This is the DEFAULT limit. You can override this per-client in Accounts → Edit Account → Custom Limits. Each client can have different limits!'
            }))
        
        # Add About & Contact fields (check if they exist)
        about_fields = []
        if self._field_exists('about_us'):
            about_fields.append('about_us')
        if self._field_exists('contact_email'):
            about_fields.append('contact_email')
        if self._field_exists('contact_phone'):
            about_fields.append('contact_phone')
        if self._field_exists('contact_address'):
            about_fields.append('contact_address')
        
        if about_fields:
            base_fieldsets.append(('About & Contact', {
                'fields': tuple(about_fields)
            }))
        
        # Add Legal Pages if fields exist
        legal_fields = []
        if self._field_exists('terms_and_conditions'):
            legal_fields.append('terms_and_conditions')
        if self._field_exists('privacy_policy'):
            legal_fields.append('privacy_policy')
        
        if legal_fields:
            base_fieldsets.append(('Legal Pages', {
                'fields': tuple(legal_fields)
            }))
        
        base_fieldsets.extend([
            ('Currency', {
                'fields': ('currency_symbol', 'currency_code')
            }),
            ('Footer', {
                'fields': ('footer_text',)
            }),
        ])
        
        # Add timestamps if editing existing object
        if obj:
            base_fieldsets.append(('Timestamps', {
                'fields': ('created_at', 'updated_at'),
                'classes': ('collapse',)
            }))
        
        return base_fieldsets
    
    list_display = ['site_name', 'company_name', 'company_email', 'updated_at']
    readonly_fields = ['created_at', 'updated_at']
    
    def has_add_permission(self, request):
        # Only allow one instance
        try:
            return not SiteSettings.objects.exists()
        except Exception:
            # If database error (e.g., missing columns), allow creation
            # This handles the case where migration hasn't been applied yet
            return True
    
    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion
        return False
    
    def save_model(self, request, obj, form, change):
        """Ensure default values are set for new instances"""
        if not change:  # Creating new instance
            # Set defaults if not provided
            if not hasattr(obj, 'max_properties_per_owner') or obj.max_properties_per_owner is None:
                obj.max_properties_per_owner = 5
            if not hasattr(obj, 'max_managers_per_owner') or obj.max_managers_per_owner is None:
                obj.max_managers_per_owner = 5
            if not obj.site_name:
                obj.site_name = "Smart PG & Flat Management CRM"
            if not obj.currency_symbol:
                obj.currency_symbol = "₹"
            if not obj.currency_code:
                obj.currency_code = "INR"
        super().save_model(request, obj, form, change)
    
    def changelist_view(self, request, extra_context=None):
        """Customize the changelist to show singleton behavior"""
        extra_context = extra_context or {}
        try:
            if not SiteSettings.objects.exists():
                extra_context['show_create'] = True
                extra_context['message'] = 'No Site Settings found. Click "Add Site Settings" to create the initial configuration.'
            else:
                extra_context['show_create'] = False
                extra_context['message'] = 'Site Settings is a singleton. Click on the entry below to edit.'
        except Exception as e:
            # Handle database errors gracefully
            extra_context['show_create'] = True
            error_msg = str(e)
            if 'does not exist' in error_msg.lower() or 'no such column' in error_msg.lower() or 'undefinedcolumn' in error_msg.lower():
                extra_context['message'] = '⚠️ Database migration pending. Please run: python manage.py migrate'
            else:
                extra_context['message'] = f'Database migration may be pending. Error: {error_msg[:100]}'
        return super().changelist_view(request, extra_context)
    
    def get_form(self, request, obj=None, **kwargs):
        """Customize form to show help text and ensure defaults"""
        form = super().get_form(request, obj, **kwargs)
        
        # Add help text for important fields
        if 'max_properties_per_owner' in form.base_fields:
            form.base_fields['max_properties_per_owner'].help_text = (
                "Maximum number of properties (buildings) each owner can add. "
                "Set to 0 for unlimited. Default: 10"
            )
        if 'max_managers_per_owner' in form.base_fields:
            form.base_fields['max_managers_per_owner'].help_text = (
                "Maximum number of managers each owner can create. "
                "Set to 0 for unlimited. Default: 5"
            )
        
        return form


@admin.register(ContentBlock)
class ContentBlockAdmin(admin.ModelAdmin):
    """Content Block Admin - handles missing fields gracefully"""
    
    def _field_exists(self, field_name):
        """Check if a field exists in the database"""
        try:
            from django.db import connection
            if 'sqlite' in connection.vendor:
                cursor = connection.cursor()
                cursor.execute("PRAGMA table_info(common_contentblock)")
                columns = [row[1] for row in cursor.fetchall()]
                return field_name in columns
            elif 'postgresql' in connection.vendor:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name='common_contentblock' 
                        AND column_name=%s
                    """, [field_name])
                    return cursor.fetchone() is not None
        except Exception:
            return False
        return False
    
    def get_list_display(self, request):
        """Dynamically get list_display based on available fields"""
        base_fields = ['key', 'block_type', 'title', 'is_active', 'order']
        return base_fields
    
    def get_fieldsets(self, request, obj=None):
        """Dynamically get fieldsets, only including fields that exist"""
        base_fieldsets = [
            ('Basic Information', {
                'fields': ('key', 'block_type', 'title', 'content', 'is_active', 'order')
            }),
        ]
        
        # Add image and video fields if they exist
        media_fields = []
        if self._field_exists('image'):
            media_fields.append('image')
        if self._field_exists('video_url'):
            media_fields.append('video_url')
        
        if media_fields:
            base_fieldsets.append(('Media', {
                'fields': tuple(media_fields),
                'description': 'Image and video fields (if migration has been applied)'
            }))
        
        base_fieldsets.append(('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }))
        
        return base_fieldsets
    
    list_display = ['key', 'block_type', 'title', 'is_active', 'order']
    list_filter = ['block_type', 'is_active']
    search_fields = ['key', 'title', 'content']
    list_editable = ['is_active', 'order']
    readonly_fields = ['created_at', 'updated_at']


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

