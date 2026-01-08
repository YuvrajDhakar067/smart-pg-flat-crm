from django import forms
from buildings.models import Building
from units.models import Unit, PGRoom, Bed
from tenants.models import Tenant
from occupancy.models import Occupancy
from rent.models import Rent
from issues.models import Issue


class BuildingForm(forms.ModelForm):
    """Form for adding/editing buildings"""
    class Meta:
        model = Building
        fields = ['name', 'address', 'total_floors']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Building Name'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Full Address'}),
            'total_floors': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }


class UnitForm(forms.ModelForm):
    """Form for adding/editing units (Flats or PGs)"""
    class Meta:
        model = Unit
        fields = ['building', 'unit_number', 'unit_type', 'bhk_type', 'expected_rent', 'deposit']
        widgets = {
            'building': forms.Select(attrs={'class': 'form-control'}),
            'unit_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 101, PG-1'}),
            'unit_type': forms.Select(attrs={'class': 'form-control'}),
            'bhk_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 1BHK, 2BHK (for flats)'}),
            'expected_rent': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
            'deposit': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
        }
    
    def __init__(self, *args, **kwargs):
        account = kwargs.pop('account', None)
        super().__init__(*args, **kwargs)
        if account:
            self.fields['building'].queryset = Building.objects.filter(account=account)


class PGRoomForm(forms.ModelForm):
    """Form for adding/editing PG rooms"""
    class Meta:
        model = PGRoom
        fields = ['unit', 'room_number', 'sharing_type']
        widgets = {
            'unit': forms.Select(attrs={'class': 'form-control'}),
            'room_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Room 1, Room A'}),
            'sharing_type': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'placeholder': 'Number of beds'}),
        }
    
    def __init__(self, *args, **kwargs):
        account = kwargs.pop('account', None)
        super().__init__(*args, **kwargs)
        if account:
            self.fields['unit'].queryset = Unit.objects.filter(account=account, unit_type='PG')


class BedForm(forms.ModelForm):
    """Form for adding/editing beds"""
    class Meta:
        model = Bed
        fields = ['room', 'bed_number']
        widgets = {
            'room': forms.Select(attrs={'class': 'form-control'}),
            'bed_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Bed 1, Bed A'}),
        }
    
    def __init__(self, *args, **kwargs):
        account = kwargs.pop('account', None)
        super().__init__(*args, **kwargs)
        if account:
            self.fields['room'].queryset = PGRoom.objects.filter(unit__account=account)


class TenantForm(forms.ModelForm):
    """Form for adding/editing tenants"""
    class Meta:
        model = Tenant
        fields = ['name', 'phone', 'email', 'id_proof_type', 'id_proof_number', 'address', 'emergency_contact']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email (optional)'}),
            'id_proof_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Aadhar, PAN'}),
            'id_proof_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ID Proof Number'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Address (optional)'}),
            'emergency_contact': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Emergency Contact (optional)'}),
        }


class OccupancyForm(forms.ModelForm):
    """Form for assigning tenants to units/beds"""
    class Meta:
        model = Occupancy
        fields = ['tenant', 'unit', 'bed', 'rent', 'deposit', 'start_date', 'notes']
        widgets = {
            'tenant': forms.Select(attrs={'class': 'form-control'}),
            'unit': forms.Select(attrs={'class': 'form-control'}),
            'bed': forms.Select(attrs={'class': 'form-control'}),
            'rent': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
            'deposit': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Additional notes (optional)'}),
        }
    
    def __init__(self, *args, **kwargs):
        account = kwargs.pop('account', None)
        unit_id = kwargs.pop('unit_id', None)
        bed_id = kwargs.pop('bed_id', None)
        super().__init__(*args, **kwargs)
        
        if account:
            self.fields['tenant'].queryset = Tenant.objects.filter(account=account)
            self.fields['unit'].queryset = Unit.objects.filter(account=account, unit_type='FLAT')
            self.fields['bed'].queryset = Bed.objects.filter(room__unit__account=account)
        
        # Pre-fill unit or bed if provided
        if unit_id:
            self.fields['unit'].initial = unit_id
            self.fields['unit'].widget = forms.HiddenInput()
            self.fields['bed'].required = False
        elif bed_id:
            self.fields['bed'].initial = bed_id
            self.fields['bed'].widget = forms.HiddenInput()
            self.fields['unit'].required = False
        else:
            # Show both fields if neither is pre-filled
            # Make them not required individually, but at least one must be filled
            self.fields['unit'].required = False
            self.fields['bed'].required = False


class RentForm(forms.ModelForm):
    """Form for adding/editing rent records"""
    class Meta:
        model = Rent
        fields = ['occupancy', 'month', 'amount', 'paid_amount', 'paid_date', 'payment_proof', 'notes']
        widgets = {
            'occupancy': forms.Select(attrs={'class': 'form-control'}),
            'month': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
            'paid_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
            'paid_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'payment_proof': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf,.jpg,.jpeg,.png,.doc,.docx'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Notes (optional)'}),
        }
    
    def __init__(self, *args, **kwargs):
        account = kwargs.pop('account', None)
        occupancy_id = kwargs.pop('occupancy_id', None)
        super().__init__(*args, **kwargs)
        
        if account:
            self.fields['occupancy'].queryset = Occupancy.objects.filter(tenant__account=account, is_active=True)
        
        if occupancy_id:
            self.fields['occupancy'].initial = occupancy_id


class IssueForm(forms.ModelForm):
    """Form for adding/editing issues"""
    class Meta:
        model = Issue
        fields = ['unit', 'tenant', 'title', 'description', 'priority', 'assigned_to']
        widgets = {
            'unit': forms.Select(attrs={'class': 'form-control'}),
            'tenant': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Issue Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Describe the issue...'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'assigned_to': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Assigned to (optional)'}),
        }
    
    def __init__(self, *args, **kwargs):
        account = kwargs.pop('account', None)
        unit_id = kwargs.pop('unit_id', None)
        super().__init__(*args, **kwargs)
        
        if account:
            self.fields['unit'].queryset = Unit.objects.filter(account=account)
            self.fields['tenant'].queryset = Tenant.objects.filter(account=account)
        
        if unit_id:
            self.fields['unit'].initial = unit_id

