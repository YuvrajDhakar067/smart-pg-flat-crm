from django.contrib import admin
from .models import Occupancy


@admin.register(Occupancy)
class OccupancyAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'location', 'rent', 'start_date', 'end_date', 'is_active']
    list_filter = ['is_active', 'start_date', 'tenant__account']
    search_fields = ['tenant__name', 'unit__unit_number', 'bed__bed_number']
    readonly_fields = ['location', 'account']
    
    fieldsets = (
        ('Tenant', {
            'fields': ('tenant',)
        }),
        ('Location', {
            'fields': ('unit', 'bed', 'location'),
            'description': 'For Flats: select unit. For PGs: select bed.'
        }),
        ('Rent Information', {
            'fields': ('rent', 'deposit')
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date', 'is_active')
        }),
        ('Documents', {
            'fields': ('agreement_document', 'notes'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('tenant', 'unit', 'bed', 'bed__room', 'bed__room__unit')
    
    def get_form(self, request, obj=None, **kwargs):
        """Pre-fill unit or bed from URL parameters"""
        form = super().get_form(request, obj, **kwargs)
        
        # Pre-fill unit if provided in URL
        if 'unit' in request.GET and not obj:
            try:
                unit_id = int(request.GET.get('unit'))
                form.base_fields['unit'].initial = unit_id
                # Clear bed field for flats
                form.base_fields['bed'].initial = None
            except (ValueError, KeyError):
                pass
        
        # Pre-fill bed if provided in URL
        if 'bed' in request.GET and not obj:
            try:
                bed_id = int(request.GET.get('bed'))
                form.base_fields['bed'].initial = bed_id
                # Clear unit field for PGs
                form.base_fields['unit'].initial = None
            except (ValueError, KeyError):
                pass
        
        return form

