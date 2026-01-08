from django.contrib import admin
from .models import Building


@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ['name', 'account', 'total_floors', 'total_units', 'occupied_units', 'vacant_units', 'created_at']
    list_filter = ['account', 'created_at']
    search_fields = ['name', 'address', 'account__name']
    readonly_fields = ['total_units', 'occupied_units', 'vacant_units']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('account', 'name', 'address', 'total_floors')
        }),
        ('Statistics', {
            'fields': ('total_units', 'occupied_units', 'vacant_units'),
            'classes': ('collapse',)
        }),
    )

