"""
Audit Log API Views

Provides read-only access to audit logs with role-based filtering.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q

from audit.models import AuditLog
from audit.serializers import AuditLogSerializer
from buildings.access import get_accessible_building_ids


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for audit logs.
    
    Access Rules:
    - OWNER: Can view all logs in their account
    - MANAGER: Can view logs only for assigned buildings
    
    Features:
    - List all accessible logs
    - Filter by action, resource_type, user
    - Search by description
    - Get audit trail for specific resource
    """
    
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['action', 'resource_type', 'user']
    search_fields = ['description']
    ordering_fields = ['timestamp', 'action']
    ordering = ['-timestamp']
    
    def get_queryset(self):
        """
        Filter audit logs based on user's access level.
        
        - OWNER: All logs in account
        - MANAGER: Logs only for assigned buildings
        """
        user = self.request.user
        
        if not hasattr(user, 'account') or not user.account:
            return AuditLog.objects.none()
        
        # Start with account filter
        queryset = AuditLog.objects.filter(account=user.account)
        
        # OWNER sees all logs
        if user.role == 'OWNER':
            return queryset
        
        # MANAGER sees only logs for assigned buildings
        elif user.role == 'MANAGER':
            accessible_building_ids = get_accessible_building_ids(user)
            
            # Filter logs related to accessible buildings
            # This includes: Building, Unit, Issue, Occupancy, Rent logs
            return queryset.filter(
                Q(resource_type=AuditLog.RESOURCE_BUILDING, resource_id__in=accessible_building_ids) |
                Q(resource_type=AuditLog.RESOURCE_UNIT, metadata__building_id__in=accessible_building_ids) |
                Q(resource_type=AuditLog.RESOURCE_ISSUE, metadata__building_id__in=accessible_building_ids) |
                Q(resource_type=AuditLog.RESOURCE_OCCUPANCY, metadata__building_id__in=accessible_building_ids) |
                Q(resource_type=AuditLog.RESOURCE_RENT, metadata__building_id__in=accessible_building_ids) |
                Q(user=user)  # Always show manager's own actions
            )
        
        return AuditLog.objects.none()
    
    @action(detail=False, methods=['get'])
    def resource_trail(self, request):
        """
        Get audit trail for a specific resource.
        
        Query params:
        - resource_type: Type of resource (Building, Unit, etc.)
        - resource_id: ID of the resource
        
        Example: GET /api/audit/resource_trail/?resource_type=Building&resource_id=123
        """
        resource_type = request.query_params.get('resource_type')
        resource_id = request.query_params.get('resource_id')
        
        if not resource_type or not resource_id:
            return Response(
                {'detail': 'Both resource_type and resource_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get filtered queryset (already applies access control)
        queryset = self.get_queryset().filter(
            resource_type=resource_type,
            resource_id=resource_id
        )
        
        serializer = self.get_serializer(queryset, many=True)
        
        return Response({
            'resource_type': resource_type,
            'resource_id': resource_id,
            'audit_trail': serializer.data,
            'count': queryset.count()
        })
    
    @action(detail=False, methods=['get'])
    def user_activity(self, request):
        """
        Get activity logs for a specific user.
        
        Query params:
        - user_id: ID of the user (optional, defaults to current user)
        
        Example: GET /api/audit/user_activity/?user_id=5
        """
        user_id = request.query_params.get('user_id')
        
        if user_id:
            # Check if requesting user can view other users' activity
            if request.user.role != 'OWNER':
                return Response(
                    {'detail': 'Only owners can view other users\' activity'},
                    status=status.HTTP_403_FORBIDDEN
                )
        else:
            # Default to current user
            user_id = request.user.id
        
        # Get filtered queryset
        queryset = self.get_queryset().filter(user_id=user_id)
        
        # Paginate
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """
        Get recent audit logs (last 50).
        
        Example: GET /api/audit/recent/
        """
        queryset = self.get_queryset()[:50]
        serializer = self.get_serializer(queryset, many=True)
        
        return Response({
            'recent_logs': serializer.data,
            'count': queryset.count()
        })
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get audit log statistics.
        
        Returns:
        - Total logs
        - Logs by action type
        - Logs by resource type
        - Recent activity count
        """
        queryset = self.get_queryset()
        
        from django.db.models import Count
        from datetime import timedelta
        from django.utils import timezone
        
        # Total logs
        total = queryset.count()
        
        # By action
        by_action = dict(
            queryset.values_list('action')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        # By resource type
        by_resource = dict(
            queryset.values_list('resource_type')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        # Recent activity (last 24 hours)
        recent_threshold = timezone.now() - timedelta(hours=24)
        recent_count = queryset.filter(timestamp__gte=recent_threshold).count()
        
        # By user (top 10)
        by_user = list(
            queryset.values('user__username', 'user__id')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        
        return Response({
            'total_logs': total,
            'by_action': by_action,
            'by_resource': by_resource,
            'recent_24h': recent_count,
            'top_users': by_user
        })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def audit_summary(request):
    """
    Get quick audit summary for dashboard.
    
    Returns:
    - Total logs in account
    - Logs today
    - Recent critical actions
    """
    user = request.user
    
    if not hasattr(user, 'account') or not user.account:
        return Response({'detail': 'User account not found'}, status=400)
    
    from django.utils import timezone
    from datetime import timedelta
    
    # Filter by account
    logs = AuditLog.objects.filter(account=user.account)
    
    # Apply building-level access for managers
    if user.role == 'MANAGER':
        accessible_building_ids = get_accessible_building_ids(user)
        logs = logs.filter(
            Q(resource_type=AuditLog.RESOURCE_BUILDING, resource_id__in=accessible_building_ids) |
            Q(user=user)
        )
    
    # Stats
    total_logs = logs.count()
    
    today = timezone.now().date()
    logs_today = logs.filter(timestamp__date=today).count()
    
    # Recent critical actions (CREATE, DELETE, GRANT_ACCESS, REVOKE_ACCESS)
    critical_actions = logs.filter(
        action__in=[
            AuditLog.ACTION_CREATE,
            AuditLog.ACTION_DELETE,
            AuditLog.ACTION_GRANT_ACCESS,
            AuditLog.ACTION_REVOKE_ACCESS
        ]
    ).order_by('-timestamp')[:10]
    
    from audit.serializers import AuditLogSerializer
    critical_serializer = AuditLogSerializer(critical_actions, many=True)
    
    return Response({
        'total_logs': total_logs,
        'logs_today': logs_today,
        'recent_critical_actions': critical_serializer.data
    })

