from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'account', 'role', 'is_active', 'date_joined']
    list_filter = ['role', 'is_active', 'account']
    search_fields = ['username', 'email', 'account__name']
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Account Information', {
            'fields': ('account', 'role', 'phone')
        }),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Account Information', {
            'fields': ('account', 'role', 'phone')
        }),
    )

