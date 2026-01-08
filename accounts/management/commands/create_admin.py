from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import Account


class Command(BaseCommand):
    help = 'Create admin superuser if not exists'

    def handle(self, *args, **options):
        User = get_user_model()
        
        # Check if admin user exists
        if User.objects.filter(username='admin').exists():
            self.stdout.write(self.style.WARNING('Admin user already exists'))
            return
        
        # Create account for admin first
        admin_account, created = Account.objects.get_or_create(
            name='PropertyNest Admin',
            defaults={'plan': 'FREE', 'phone': ''}
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('Created PropertyNest Admin account'))
        
        # Create superuser manually with account
        user = User(
            username='admin',
            email='admin@propertynest.com',
            is_staff=True,
            is_superuser=True,
            is_active=True,
            account=admin_account,
            role='OWNER'
        )
        user.set_password('Admin@123456')
        user.save()
        
        self.stdout.write(self.style.SUCCESS('Superuser created: admin / Admin@123456'))

