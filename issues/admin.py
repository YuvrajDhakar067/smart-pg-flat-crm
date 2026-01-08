from django.contrib import admin
from .models import Issue


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ['title', 'unit', 'tenant', 'status', 'priority', 'assigned_to', 'raised_date']
    list_filter = ['status', 'priority', 'unit__account', 'raised_date']
    search_fields = ['title', 'description', 'unit__unit_number', 'tenant__name']
    readonly_fields = ['resolved_date', 'account']
    date_hierarchy = 'raised_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('unit', 'tenant', 'title', 'description')
        }),
        ('Status & Priority', {
            'fields': ('status', 'priority', 'assigned_to')
        }),
        ('Dates', {
            'fields': ('raised_date', 'resolved_date'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Avoid select_related('tenant') to prevent FieldError with deferred fields
        return qs.select_related('unit', 'unit__building')

