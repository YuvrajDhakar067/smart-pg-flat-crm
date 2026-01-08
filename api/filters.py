"""
Custom filters for multi-tenant data
"""
from rest_framework import filters


class AccountFilterBackend(filters.BaseFilterBackend):
    """
    Filter queryset to only show objects belonging to the user's account
    """
    
    def filter_queryset(self, request, queryset, view):
        """Filter by account"""
        if request.user and request.user.is_authenticated and hasattr(request.user, 'account'):
            return queryset.filter(account=request.user.account)
        return queryset.none()

