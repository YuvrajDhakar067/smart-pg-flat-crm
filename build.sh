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
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@propertynest.com', 'Admin@123456')
    print('Superuser created: admin / Admin@123456')
else:
    print('Superuser already exists')
EOF

echo "✅ Build complete!"
