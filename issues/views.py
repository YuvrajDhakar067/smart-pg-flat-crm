from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from .models import Issue
from .serializers import IssueSerializer, IssueListSerializer
from api.permissions import IsAccountOwner, IsOwnerOrManager
from api.filters import AccountFilterBackend


class IssueViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Issue management
    Handles complaint/issue tracking
    Uses atomic transactions for data consistency
    """
    permission_classes = [IsAuthenticated, IsOwnerOrManager]
    filter_backends = [AccountFilterBackend]
    search_fields = ['title', 'description', 'unit__unit_number', 'tenant__name']
    ordering_fields = ['raised_date', 'priority', 'status']
    ordering = ['-raised_date']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return IssueListSerializer
        return IssueSerializer
    
    def get_queryset(self):
        """
        Filter issues by user's account AND building-level permissions
        
        - OWNER: All issues in all buildings in their account
        - MANAGER: Only issues in buildings they have access to
        """
        from buildings.access import filter_by_accessible_buildings
        
        # Start with account-level isolation
        queryset = Issue.objects.filter(unit__account=self.request.user.account)
        
        # Apply building-level access control
        queryset = filter_by_accessible_buildings(queryset, self.request.user, 'unit__building')
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by priority
        priority_filter = self.request.query_params.get('priority', None)
        if priority_filter:
            queryset = queryset.filter(priority=priority_filter)
        
        # OPTIMIZED: select_related for all foreign keys - avoid select_related('tenant') to prevent FieldError
        # Note: tenant is nullable, so select_related('tenant') causes FieldError when combined with deferred fields
        return queryset.select_related(
            'unit',
            'unit__building',
            'unit__account'
        )
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create issue with atomic transaction"""
        return super().create(request, *args, **kwargs)
    
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Update issue with atomic transaction and row-level locking"""
        issue = Issue.objects.select_for_update().filter(
            id=kwargs.get('pk'),
            unit__account=request.user.account
        ).first()
        
        if not issue:
            return Response(
                {'detail': 'Issue not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(issue, data=request.data, partial=kwargs.get('partial', False))
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    
    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        """Handle PATCH requests with concurrency control"""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Mark issue as resolved with row-level locking"""
        issue = Issue.objects.select_for_update().filter(
            id=pk,
            unit__account=request.user.account
        ).first()
        
        if not issue:
            return Response(
                {'detail': 'Issue not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        issue.status = 'RESOLVED'
        issue.save()  # Auto-sets resolved_date
        
        serializer = self.get_serializer(issue)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def open(self, request):
        """Get all open issues"""
        issues = self.get_queryset().filter(status__in=['OPEN', 'ASSIGNED', 'IN_PROGRESS'])
        serializer = self.get_serializer(issues, many=True)
        return Response(serializer.data)

