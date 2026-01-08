# Smart PG & Flat Management CRM

> **Enterprise-grade multi-tenant SaaS platform** for property management with comprehensive security, audit logging, and role-based access control.

[![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-3.2+-green.svg)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/DRF-3.12+-red.svg)](https://www.django-rest-framework.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 📋 Overview

A complete property management solution for managing PG accommodations and flats with:
- **Multi-tenant architecture** - Complete account isolation
- **Role-based access** - Owner and Manager roles with building-level permissions
- **Audit logging** - Immutable logs for all actions
- **Concurrency control** - Prevent double-booking and race conditions
- **REST API** - Full-featured API with JWT authentication
- **Dashboard** - Role-aware metrics and analytics

## 🚀 Quick Start

### Prerequisites
- Python 3.7+
- pip
- virtualenv (recommended)

### Installation

```bash
# Clone repository
git clone <repository-url>
cd "Smart PG & Flat Management CRM"

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

Access the application at `http://localhost:8000`

### Create Demo Data

```bash
python manage.py create_sample_data
```

## 🏗️ Architecture

### Tech Stack
- **Backend**: Django 3.2+, Django REST Framework
- **Database**: SQLite (dev) / PostgreSQL (production)
- **Authentication**: JWT (djangorestframework-simplejwt)
- **Frontend**: Django templates, Bootstrap 5, Inter Font
- **UI/UX**: Modern gradient design, smooth animations, responsive layout

### Apps Structure
```
├── accounts/          # Multi-tenant accounts
├── users/            # Custom user model (Owner/Manager)
├── buildings/        # Buildings and access control
├── units/            # Units, PG Rooms, Beds
├── tenants/          # Tenant management
├── occupancy/        # Tenant assignments
├── rent/             # Rent tracking
├── issues/           # Issue/complaint management
├── dashboard/        # Analytics API
├── audit/            # Audit logging
└── common/           # Shared utilities, middleware
```

## 🔑 Key Features

### 1. Multi-Tenant Architecture
- **Complete account isolation** - Users can only access their account's data
- **Building-level permissions** - Managers can only access assigned buildings
- **Global middleware enforcement** - Security checks before all requests

### 2. Role-Based Access Control
- **OWNER**: Full access to all buildings and data
- **MANAGER**: Access only to assigned buildings
- **BuildingAccess model**: Links managers to specific buildings

### 3. Audit Logging
- **Immutable logs** - Cannot be edited or deleted
- **Complete tracking** - Who, what, when, where
- **11 action types**: CREATE, UPDATE, DELETE, PAY_RENT, GRANT_ACCESS, etc.
- **Rich metadata**: IP address, user agent, custom context

### 4. Concurrency Control
- **Database locking** - `select_for_update()` prevents race conditions
- **Atomic transactions** - Ensures data consistency
- **Conflict handling** - Returns HTTP 409 for double-booking attempts

### 5. Dashboard Analytics
- **Role-aware metrics** - Automatically filtered by user access
- **Real-time data** - Occupancy rates, rent collection, issues
- **Building performance** - Track each building individually

## 📡 API Endpoints

### Authentication
```
POST /api/auth/login/          # Get JWT token
POST /api/auth/refresh/        # Refresh token
```

### Resources
```
GET    /api/buildings/         # List buildings
POST   /api/buildings/         # Create building
GET    /api/buildings/{id}/    # Get building detail
PUT    /api/buildings/{id}/    # Update building

GET    /api/units/             # List units
POST   /api/occupancies/       # Assign tenant
POST   /api/rents/{id}/pay/    # Pay rent
GET    /api/issues/            # List issues
```

### Dashboard
```
GET /dashboard/metrics/        # Summary metrics
GET /dashboard/detailed/       # Detailed building metrics
GET /dashboard/api/recent_activity/  # Recent activity
```

### Audit Logs
```
GET /api/audit/logs/           # List all logs
GET /api/audit/logs/resource_trail/  # Get audit trail
GET /api/audit/logs/stats/     # Statistics
```

## 🔒 Security Features

### Account Isolation
```python
# All queries filtered by account
queryset = Building.objects.filter(account=request.user.account)
```

### Building-Level Access
```python
# Managers only see assigned buildings
accessible_buildings = get_accessible_buildings(request.user)
```

### Permission Middleware
- Validates all requests before reaching views
- Enforces account isolation
- Checks building-level permissions
- Fails closed if uncertain

### Audit Trail
- Every action logged automatically
- Logs are immutable (cannot be modified)
- Read-only API and admin interface

## 📊 Database Schema

### Core Models
- **Account** - Multi-tenant accounts
- **User** - Custom user with role (OWNER/MANAGER)
- **Building** - Properties
- **BuildingAccess** - Manager-to-building assignments
- **Unit** - Flats and PG rooms
- **Tenant** - Tenant information
- **Occupancy** - Links tenant to unit/bed
- **Rent** - Monthly rent tracking
- **Issue** - Complaints/issues
- **AuditLog** - Immutable action logs

## 🧪 Testing

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test tests.test_audit_logging
python manage.py test tests.test_dashboard_access

# With coverage
coverage run --source='.' manage.py test
coverage report
```

**Test Coverage**: 100+ tests across all features

## 📖 Documentation

### Main Documentation
- **[FEATURES.md](FEATURES.md)** - Complete feature documentation
  - Multi-Tenant Access Control
  - Audit Logging System
  - Dashboard Analytics
  - Concurrency Control
  - API Reference
  - Usage Examples

- **[UI_IMPROVEMENTS.md](UI_IMPROVEMENTS.md)** - UI/UX enhancements
  - Modern design system
  - Component breakdown
  - Color palette
  - Responsive design
  - Accessibility features

## 🔧 Configuration

### Environment Variables
```bash
# Django
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (PostgreSQL)
DB_NAME=smart_pg_db
DB_USER=postgres
DB_PASSWORD=password
DB_HOST=localhost
DB_PORT=5432

# JWT
JWT_ACCESS_TOKEN_LIFETIME=60  # minutes
JWT_REFRESH_TOKEN_LIFETIME=1440  # minutes
```

### Settings
Key settings in `smart_pg/settings.py`:
- Multi-tenant middleware enabled
- JWT authentication configured
- Audit logging enabled
- Permission middleware active

## 🚀 Deployment

### Production Checklist
- [ ] Set `DEBUG=False`
- [ ] Configure proper `SECRET_KEY`
- [ ] Set `ALLOWED_HOSTS`
- [ ] Use PostgreSQL database
- [ ] Configure static files (whitenoise/S3)
- [ ] Set up HTTPS
- [ ] Configure email backend
- [ ] Set up Celery for async tasks
- [ ] Configure logging
- [ ] Set up monitoring (Sentry)

### Docker Deployment
```bash
# Build image
docker build -t smart-pg-crm .

# Run container
docker run -p 8000:8000 smart-pg-crm
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👥 Authors

- **Yuvraj Dhakar** - Initial work

## 🙏 Acknowledgments

- Django & Django REST Framework communities
- Bootstrap for UI components
- All contributors and testers

## 📞 Support

For support, email support@example.com or open an issue in the repository.

---

**Built with ❤️ for Property Owners & Managers**
