from django.urls import path
from django.shortcuts import redirect
from . import views

app_name = 'properties'

def root_redirect(request):
    """Redirect root to dashboard or login"""
    if request.user.is_authenticated:
        return redirect('properties:dashboard')
    return redirect('accounts:login')

urlpatterns = [
    path('', root_redirect, name='root'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('buildings/', views.building_list, name='building_list'),
    path('buildings/add/', views.add_building, name='add_building'),
    path('buildings/<int:building_id>/', views.building_detail, name='building_detail'),
    path('buildings/<int:building_id>/delete/', views.delete_building, name='delete_building'),
    path('buildings/<int:building_id>/units/add/', views.add_unit, name='add_unit'),
    path('units/<int:unit_id>/', views.unit_detail, name='unit_detail'),
    path('vacancy/', views.vacancy_view, name='vacancy'),
    path('rents/', views.rent_management, name='rent_management'),
    path('rents/add/', views.add_rent, name='add_rent'),
    path('rents/add/unit/<int:unit_id>/', views.add_rent, name='add_rent_unit'),
    path('rents/add/room/<int:room_id>/', views.add_rent, name='add_rent_room'),
    path('rents/<int:rent_id>/edit/', views.edit_rent, name='edit_rent'),
    path('rents/<int:rent_id>/receipt/', views.view_rent_receipt, name='view_rent_receipt'),
    path('rents/<int:rent_id>/receipt/download/', views.download_rent_receipt, name='download_rent_receipt'),
    path('rents/<int:rent_id>/receipt/print/', views.print_rent_receipt, name='print_rent_receipt'),
    path('issues/', views.issue_list, name='issue_list'),
    path('issues/add/', views.add_issue, name='add_issue'),
    path('issues/<int:unit_id>/add/', views.add_issue, name='add_issue_unit'),
    path('issues/<int:issue_id>/', views.issue_detail, name='issue_detail'),
    path('tenants/', views.tenant_list, name='tenant_list'),
    path('tenants/add/', views.add_tenant, name='add_tenant'),
    path('tenants/<int:tenant_id>/history/', views.tenant_history, name='tenant_history'),
    path('tenants/<int:tenant_id>/checkout/', views.tenant_checkout, name='tenant_checkout'),
    path('tenants/<int:tenant_id>/notice/', views.give_notice, name='give_notice'),
    path('tenants/<int:tenant_id>/cancel-notice/', views.cancel_notice, name='cancel_notice'),
    path('tenants/<int:tenant_id>/documents/', views.tenant_documents, name='tenant_documents'),
    path('tenants/<int:tenant_id>/documents/upload/', views.upload_document, name='upload_document'),
    path('tenants/<int:tenant_id>/assign/', views.add_occupancy, name='add_occupancy_tenant'),
    
    # Document Management
    path('documents/<int:document_id>/', views.view_document, name='view_document'),
    path('documents/<int:document_id>/verify/', views.verify_document, name='verify_document'),
    path('documents/<int:document_id>/delete/', views.delete_document, name='delete_document'),
    path('occupancy/add/', views.add_occupancy, name='add_occupancy'),
    path('occupancy/add/unit/<int:unit_id>/', views.add_occupancy, name='add_occupancy_unit'),
    path('occupancy/add/bed/<int:bed_id>/', views.add_occupancy, name='add_occupancy_bed'),
    path('units/<int:unit_id>/occupants/', views.manage_flat_occupants, name='manage_flat_occupants'),
    path('search/', views.search, name='search'),
    
    # Analytics
    path('revenue/', views.revenue_dashboard, name='revenue_dashboard'),
    
    # Notice Period Management
    path('notices/', views.notice_list, name='notice_list'),
    path('buildings/<int:building_id>/notice-period/', views.update_building_notice_period, name='update_building_notice_period'),
    
    # Team/Manager Management (Owner only)
    path('team/', views.team_management, name='team_management'),
    path('team/add/', views.add_manager, name='add_manager'),
    path('team/<int:manager_id>/', views.manager_detail, name='manager_detail'),
    path('team/<int:manager_id>/remove/', views.remove_manager, name='remove_manager'),
    path('team/<int:manager_id>/access/', views.manage_building_access, name='manage_building_access'),
]

