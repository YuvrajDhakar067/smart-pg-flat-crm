"""
Management command to initialize default settings
"""
from django.core.management.base import BaseCommand
from common.models import SiteSettings, StatusLabel, NotificationTemplate, ContentBlock


class Command(BaseCommand):
    help = 'Initialize default site settings and content'

    def handle(self, *args, **options):
        self.stdout.write('Initializing default settings...')
        
        # Create default site settings
        settings = SiteSettings.load()
        self.stdout.write(self.style.SUCCESS(f'✓ Site settings created/loaded'))
        
        # Create default status labels
        status_labels = [
            # Unit statuses
            {'status_type': 'unit', 'code': 'occupied', 'label': 'Occupied', 'color': '#10b981', 'icon': 'bi-check-circle'},
            {'status_type': 'unit', 'code': 'vacant', 'label': 'Vacant', 'color': '#ef4444', 'icon': 'bi-x-circle'},
            
            # Rent statuses
            {'status_type': 'rent', 'code': 'paid', 'label': 'Paid', 'color': '#10b981', 'icon': 'bi-check-circle'},
            {'status_type': 'rent', 'code': 'pending', 'label': 'Pending', 'color': '#f59e0b', 'icon': 'bi-clock'},
            {'status_type': 'rent', 'code': 'partial', 'label': 'Partial', 'color': '#3b82f6', 'icon': 'bi-hourglass'},
            
            # Issue statuses
            {'status_type': 'issue', 'code': 'raised', 'label': 'Raised', 'color': '#ef4444', 'icon': 'bi-exclamation-triangle'},
            {'status_type': 'issue', 'code': 'assigned', 'label': 'Assigned', 'color': '#3b82f6', 'icon': 'bi-person-check'},
            {'status_type': 'issue', 'code': 'in_progress', 'label': 'In Progress', 'color': '#3b82f6', 'icon': 'bi-gear'},
            {'status_type': 'issue', 'code': 'resolved', 'label': 'Resolved', 'color': '#10b981', 'icon': 'bi-check-circle'},
        ]
        
        for label_data in status_labels:
            StatusLabel.objects.get_or_create(
                status_type=label_data['status_type'],
                code=label_data['code'],
                defaults=label_data
            )
        
        self.stdout.write(self.style.SUCCESS(f'✓ Status labels created'))
        
        # Create default content blocks
        content_blocks = [
            {
                'key': 'dashboard_welcome',
                'block_type': 'dashboard_welcome',
                'title': 'Dashboard Welcome Message',
                'content': 'Welcome to your property management dashboard! Track your buildings, tenants, rent, and issues all in one place.',
            },
            {
                'key': 'vacancy_alert',
                'block_type': 'vacancy_alert',
                'title': 'Vacancy Alert Message',
                'content': 'You have vacant units. Fill them to maximize your revenue!',
            },
        ]
        
        for block_data in content_blocks:
            ContentBlock.objects.get_or_create(
                key=block_data['key'],
                defaults=block_data
            )
        
        self.stdout.write(self.style.SUCCESS(f'✓ Content blocks created'))
        
        # Create default notification templates
        notification_templates = [
            {
                'template_type': 'rent_due',
                'subject': 'Rent Due Reminder',
                'message': 'Dear {{tenant_name}}, Your rent of {{amount}} for {{month}} is due. Please pay by {{due_date}}.',
            },
            {
                'template_type': 'rent_paid',
                'subject': 'Rent Payment Confirmation',
                'message': 'Dear {{tenant_name}}, We have received your rent payment of {{amount}} for {{month}}. Thank you!',
            },
            {
                'template_type': 'issue_raised',
                'subject': 'New Issue Reported',
                'message': 'A new issue "{{issue_title}}" has been reported for {{unit_number}}. We will address it soon.',
            },
            {
                'template_type': 'issue_resolved',
                'subject': 'Issue Resolved',
                'message': 'The issue "{{issue_title}}" for {{unit_number}} has been resolved. Thank you for your patience.',
            },
        ]
        
        for template_data in notification_templates:
            NotificationTemplate.objects.get_or_create(
                template_type=template_data['template_type'],
                defaults=template_data
            )
        
        self.stdout.write(self.style.SUCCESS(f'✓ Notification templates created'))
        
        self.stdout.write(self.style.SUCCESS('\n✅ All default settings initialized successfully!'))
        self.stdout.write('\nYou can now customize these settings from the Admin Panel:')
        self.stdout.write('  - Site Settings: /admin/common/sitesettings/')
        self.stdout.write('  - Content Blocks: /admin/common/contentblock/')
        self.stdout.write('  - Status Labels: /admin/common/statuslabel/')
        self.stdout.write('  - Notification Templates: /admin/common/notificationtemplate/')

