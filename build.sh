#!/usr/bin/env bash
# =============================================================================
# Render.com Build Script
# =============================================================================

set -o errexit  # Exit on error

echo "🧹 Clearing pip cache..."
pip cache purge || true

echo "🔧 Installing dependencies (fresh with legacy resolver)..."
pip install --upgrade pip
pip install --no-cache-dir --use-deprecated=legacy-resolver -r requirements.txt

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
