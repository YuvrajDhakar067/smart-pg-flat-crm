from django.contrib import admin
from .models import Unit, PGRoom, Bed


class BedInline(admin.TabularInline):
    model = Bed
    extra = 1


class PGRoomInline(admin.TabularInline):
    model = PGRoom
    extra = 1
    show_change_link = True


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ['unit_number', 'building', 'unit_type', 'bhk_type', 'status', 'expected_rent', 'account']
    list_filter = ['unit_type', 'status', 'account', 'building']
    search_fields = ['unit_number', 'building__name']
    inlines = [PGRoomInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('account', 'building', 'unit_number', 'unit_type', 'bhk_type')
        }),
        ('Rent Information', {
            'fields': ('expected_rent', 'deposit', 'status')
        }),
    )


@admin.register(PGRoom)
class PGRoomAdmin(admin.ModelAdmin):
    list_display = ['room_number', 'unit', 'sharing_type', 'occupied_beds', 'vacant_beds']
    list_filter = ['unit', 'sharing_type']
    search_fields = ['room_number', 'unit__unit_number']
    inlines = [BedInline]
    readonly_fields = ['occupied_beds', 'vacant_beds']


@admin.register(Bed)
class BedAdmin(admin.ModelAdmin):
    list_display = ['bed_number', 'room', 'status']
    list_filter = ['status', 'room__unit']
    search_fields = ['bed_number', 'room__room_number']

