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

echo "👤 Creating admin superuser..."
python manage.py create_admin

echo "✅ Build complete!"
