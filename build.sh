#!/usr/bin/env bash
# =============================================================================
# Render.com Build Script
# =============================================================================

set -o errexit  # Exit on error

echo "🔧 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "📁 Creating necessary directories..."
mkdir -p logs
mkdir -p staticfiles
mkdir -p media

echo "📦 Collecting static files..."
python manage.py collectstatic --no-input

echo "🗄️ Running database migrations..."
python manage.py migrate

echo "👤 Creating superuser if not exists..."
python manage.py shell << EOF
from django.contrib.auth import get_user_model
from accounts.models import Account

User = get_user_model()

# Check if admin user exists
if not User.objects.filter(username='admin').exists():
    # Create account for admin first
    admin_account, created = Account.objects.get_or_create(
        name='PropertyNest Admin',
        defaults={'plan': 'FREE', 'phone': ''}
    )
    
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
    print('Superuser created: admin / Admin@123456')
else:
    print('Superuser already exists')
EOF

echo "✅ Build complete!"
