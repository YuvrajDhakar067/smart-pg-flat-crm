from django.contrib import admin

# Customize admin site
admin.site.site_header = "Smart PG & Flat Management CRM - Admin Panel"
admin.site.site_title = "Property Management Admin"
admin.site.index_title = "Welcome to Property Management Administration"

# Import all admin configurations to register them
from common import admin as common_admin  # noqa: F401
from accounts import admin as accounts_admin  # noqa: F401
from users import admin as users_admin  # noqa: F401
