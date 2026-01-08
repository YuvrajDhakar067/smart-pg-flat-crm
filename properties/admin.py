"""
Properties app admin - Legacy models are deprecated.

All models are now registered in their respective apps:
- Building: buildings/admin.py
- Unit: units/admin.py
- Tenant: tenants/admin.py
- Rent: rent/admin.py
- Issue: issues/admin.py
- Occupancy: occupancy/admin.py

This file is kept for reference but no longer registers any models.
"""
from django.contrib import admin

# All models are registered in their respective app admin files
# to avoid conflicts with legacy properties.models

