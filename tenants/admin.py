from django.contrib import admin
from .models import Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'email', 'account', 'created_at']
    list_filter = ['account', 'created_at']
    search_fields = ['name', 'phone', 'email', 'id_proof_number']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('account', 'name', 'phone', 'email')
        }),
        ('Identity', {
            'fields': ('id_proof_type', 'id_proof_number')
        }),
        ('Additional Information', {
            'fields': ('address', 'emergency_contact')
        }),
    )

