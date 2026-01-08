from django.contrib import admin
from .models import Rent


@admin.register(Rent)
class RentAdmin(admin.ModelAdmin):
    list_display = ['occupancy', 'month', 'amount', 'paid_amount', 'pending_amount', 'status', 'paid_date']
    list_filter = ['status', 'month']
    search_fields = ['occupancy__tenant__name', 'occupancy__unit__unit_number']
    readonly_fields = ['pending_amount', 'account']
    
    def account(self, obj):
        """Get account from occupancy"""
        return obj.occupancy.account
    account.short_description = 'Account'
    date_hierarchy = 'month'
    
    fieldsets = (
        ('Occupancy', {
            'fields': ('occupancy',)
        }),
        ('Rent Information', {
            'fields': ('month', 'amount', 'paid_amount', 'pending_amount', 'status', 'paid_date')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('occupancy', 'occupancy__tenant', 'occupancy__unit', 'occupancy__bed')

