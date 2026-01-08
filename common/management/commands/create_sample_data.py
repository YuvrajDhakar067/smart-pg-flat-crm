"""
Management command to create comprehensive sample data for testing
Creates buildings, units, PG rooms, beds, tenants, occupancies, rent records, and issues
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from accounts.models import Account
from buildings.models import Building
from units.models import Unit, PGRoom, Bed
from tenants.models import Tenant
from occupancy.models import Occupancy
from rent.models import Rent
from issues.models import Issue

User = get_user_model()


class Command(BaseCommand):
    help = 'Create sample data: 2 buildings, 5 PG rooms, 2 1BHK, 2 2BHK, 3 3BHK'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default='yuvraj',
            help='Username to create data for (default: yuvraj)'
        )

    def handle(self, *args, **options):
        username = options['username']
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User "{username}" not found. Please create the user first.'))
            return
        
        if not user.account:
            # Create account if missing
            account = Account.objects.create(
                name=f"{user.username}'s Account",
                plan='FREE',
                phone=''
            )
            user.account = account
            user.role = 'OWNER'
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Created account for {username}'))
        else:
            account = user.account
        
        # Clear existing data for this account (optional - comment out if you want to keep existing)
        # Building.objects.filter(account=account).delete()
        
        # Building 1: "Green Valley Apartments"
        building1, created = Building.objects.get_or_create(
            account=account,
            name="Green Valley Apartments",
            defaults={
                'address': "123 Main Street, City Center, Mumbai - 400001",
                'total_floors': 5
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created Building 1: {building1.name}'))
        
        # Building 2: "Sunset Heights"
        building2, created = Building.objects.get_or_create(
            account=account,
            name="Sunset Heights",
            defaults={
                'address': "456 Park Avenue, Suburbia, Mumbai - 400002",
                'total_floors': 4
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created Building 2: {building2.name}'))
        
        # Building 1: Add 5 PG Rooms
        pg_units_created = 0
        for i in range(1, 6):
            pg_unit, created = Unit.objects.get_or_create(
                account=account,
                building=building1,
                unit_number=f"PG-{i}",
                defaults={
                    'unit_type': 'PG',
                    'expected_rent': 8000 + (i * 500),  # 8500, 9000, 9500, 10000, 10500
                    'deposit': 15000,
                    'status': 'VACANT'
                }
            )
            if created:
                pg_units_created += 1
                # Create PG Room with beds
                room, _ = PGRoom.objects.get_or_create(
                    unit=pg_unit,
                    room_number=f"Room-{i}",
                    defaults={
                        'sharing_type': 2 if i <= 3 else 3  # First 3 are double sharing, rest triple
                    }
                )
                # Create beds for the room
                for bed_num in range(1, room.sharing_type + 1):
                    Bed.objects.get_or_create(
                        room=room,
                        bed_number=f"Bed-{bed_num}",
                        defaults={'status': 'VACANT'}
                    )
        
        if pg_units_created > 0:
            self.stdout.write(self.style.SUCCESS(f'Created {pg_units_created} PG units in {building1.name}'))
        
        # Building 1: Add 2 1BHK flats
        bhk1_created = 0
        for i in range(1, 3):
            flat, created = Unit.objects.get_or_create(
                account=account,
                building=building1,
                unit_number=f"101-{i}",  # 101-1, 101-2
                defaults={
                    'unit_type': 'FLAT',
                    'bhk_type': '1BHK',
                    'expected_rent': 18000 + (i * 1000),  # 19000, 20000
                    'deposit': 50000,
                    'status': 'VACANT'
                }
            )
            if created:
                bhk1_created += 1
        
        if bhk1_created > 0:
            self.stdout.write(self.style.SUCCESS(f'Created {bhk1_created} 1BHK flats in {building1.name}'))
        
        # Building 2: Add 2 2BHK flats
        bhk2_created = 0
        for i in range(1, 3):
            flat, created = Unit.objects.get_or_create(
                account=account,
                building=building2,
                unit_number=f"201-{i}",  # 201-1, 201-2
                defaults={
                    'unit_type': 'FLAT',
                    'bhk_type': '2BHK',
                    'expected_rent': 28000 + (i * 2000),  # 30000, 32000
                    'deposit': 80000,
                    'status': 'VACANT'
                }
            )
            if created:
                bhk2_created += 1
        
        if bhk2_created > 0:
            self.stdout.write(self.style.SUCCESS(f'Created {bhk2_created} 2BHK flats in {building2.name}'))
        
        # Building 2: Add 3 3BHK flats
        bhk3_created = 0
        for i in range(1, 4):
            flat, created = Unit.objects.get_or_create(
                account=account,
                building=building2,
                unit_number=f"301-{i}",  # 301-1, 301-2, 301-3
                defaults={
                    'unit_type': 'FLAT',
                    'bhk_type': '3BHK',
                    'expected_rent': 45000 + (i * 3000),  # 48000, 51000, 54000
                    'deposit': 120000,
                    'status': 'VACANT'
                }
            )
            if created:
                bhk3_created += 1
        
        if bhk3_created > 0:
            self.stdout.write(self.style.SUCCESS(f'Created {bhk3_created} 3BHK flats in {building2.name}'))
        
        # ========== CREATE TENANTS ==========
        self.stdout.write(self.style.WARNING('\nCreating Tenants...'))
        
        tenant_data = [
            {'name': 'Rahul Sharma', 'phone': '9876543210', 'email': 'rahul.sharma@email.com', 'id_proof_type': 'Aadhar', 'id_proof_number': '1234 5678 9012'},
            {'name': 'Priya Patel', 'phone': '9876543211', 'email': 'priya.patel@email.com', 'id_proof_type': 'PAN', 'id_proof_number': 'ABCDE1234F'},
            {'name': 'Amit Kumar', 'phone': '9876543212', 'email': 'amit.kumar@email.com', 'id_proof_type': 'Aadhar', 'id_proof_number': '2345 6789 0123'},
            {'name': 'Sneha Desai', 'phone': '9876543213', 'email': 'sneha.desai@email.com', 'id_proof_type': 'Aadhar', 'id_proof_number': '3456 7890 1234'},
            {'name': 'Vikram Singh', 'phone': '9876543214', 'email': 'vikram.singh@email.com', 'id_proof_type': 'PAN', 'id_proof_number': 'FGHIJ5678K'},
            {'name': 'Anjali Mehta', 'phone': '9876543215', 'email': 'anjali.mehta@email.com', 'id_proof_type': 'Aadhar', 'id_proof_number': '4567 8901 2345'},
            {'name': 'Rajesh Gupta', 'phone': '9876543216', 'email': 'rajesh.gupta@email.com', 'id_proof_type': 'Aadhar', 'id_proof_number': '5678 9012 3456'},
            {'name': 'Kavita Reddy', 'phone': '9876543217', 'email': 'kavita.reddy@email.com', 'id_proof_type': 'PAN', 'id_proof_number': 'KLMNO9012P'},
            {'name': 'Suresh Iyer', 'phone': '9876543218', 'email': 'suresh.iyer@email.com', 'id_proof_type': 'Aadhar', 'id_proof_number': '6789 0123 4567'},
            {'name': 'Meera Joshi', 'phone': '9876543219', 'email': 'meera.joshi@email.com', 'id_proof_type': 'Aadhar', 'id_proof_number': '7890 1234 5678'},
        ]
        
        tenants_created = []
        for tenant_info in tenant_data:
            tenant, created = Tenant.objects.get_or_create(
                account=account,
                phone=tenant_info['phone'],
                defaults={
                    'name': tenant_info['name'],
                    'email': tenant_info['email'],
                    'id_proof_type': tenant_info['id_proof_type'],
                    'id_proof_number': tenant_info['id_proof_number'],
                    'address': f"Address for {tenant_info['name']}",
                    'emergency_contact': f"9{tenant_info['phone'][-9:]}"
                }
            )
            if created:
                tenants_created.append(tenant)
        
        if tenants_created:
            self.stdout.write(self.style.SUCCESS(f'Created {len(tenants_created)} tenants'))
        
        # ========== CREATE OCCUPANCIES (Assign tenants to units/beds) ==========
        self.stdout.write(self.style.WARNING('\nCreating Occupancies...'))
        
        # Get some units and beds
        flat_units = list(Unit.objects.filter(account=account, unit_type='FLAT').order_by('id')[:7])
        pg_beds = list(Bed.objects.filter(room__unit__account=account).order_by('id')[:3])
        
        occupancies_created = []
        
        # Assign tenants to flats
        for i, unit in enumerate(flat_units[:7]):
            if i < len(tenants_created):
                tenant = tenants_created[i]
                # Check if occupancy already exists
                existing = Occupancy.objects.filter(unit=unit, is_active=True).first()
                if not existing:
                    occupancy = Occupancy.objects.create(
                        tenant=tenant,
                        unit=unit,
                        bed=None,
                        rent=unit.expected_rent,
                        deposit=unit.deposit,
                        start_date=date.today() - timedelta(days=30 + (i * 5)),  # Different move-in dates
                        is_active=True,
                        notes=f"Occupancy created for {tenant.name}"
                    )
                    occupancies_created.append(occupancy)
                    unit.update_status()  # Update unit status to OCCUPIED
        
        # Assign tenants to PG beds
        for i, bed in enumerate(pg_beds[:3]):
            tenant_idx = 7 + i
            if tenant_idx < len(tenants_created):
                tenant = tenants_created[tenant_idx]
                # Check if occupancy already exists
                existing = Occupancy.objects.filter(bed=bed, is_active=True).first()
                if not existing:
                    occupancy = Occupancy.objects.create(
                        tenant=tenant,
                        unit=None,
                        bed=bed,
                        rent=bed.room.unit.expected_rent / bed.room.sharing_type,  # Split rent by sharing
                        deposit=15000,
                        start_date=date.today() - timedelta(days=20 + (i * 3)),
                        is_active=True,
                        notes=f"PG occupancy for {tenant.name}"
                    )
                    occupancies_created.append(occupancy)
                    bed.update_status()  # Update bed status to OCCUPIED
        
        if occupancies_created:
            self.stdout.write(self.style.SUCCESS(f'Created {len(occupancies_created)} occupancies'))
        
        # ========== CREATE RENT RECORDS ==========
        self.stdout.write(self.style.WARNING('\nCreating Rent Records...'))
        
        current_month = timezone.now().replace(day=1).date()
        previous_month = (current_month - timedelta(days=1)).replace(day=1)
        two_months_ago = (previous_month - timedelta(days=1)).replace(day=1)
        
        rent_records_created = []
        
        for occupancy in occupancies_created:
            # Current month rent - mix of paid, pending, and partial
            rent_status = ['PAID', 'PENDING', 'PARTIAL', 'PAID'][len(rent_records_created) % 4]
            
            if rent_status == 'PAID':
                paid_amount = occupancy.rent
                paid_date = current_month + timedelta(days=5)
            elif rent_status == 'PARTIAL':
                paid_amount = occupancy.rent * Decimal('0.5')
                paid_date = current_month + timedelta(days=10)
            else:
                paid_amount = Decimal('0')
                paid_date = None
            
            rent, created = Rent.objects.get_or_create(
                occupancy=occupancy,
                month=current_month,
                defaults={
                    'amount': occupancy.rent,
                    'paid_amount': paid_amount,
                    'paid_date': paid_date,
                    'notes': f"Rent for {current_month.strftime('%B %Y')}"
                }
            )
            if created:
                rent_records_created.append(rent)
            
            # Previous month rent - mostly paid
            prev_rent, created = Rent.objects.get_or_create(
                occupancy=occupancy,
                month=previous_month,
                defaults={
                    'amount': occupancy.rent,
                    'paid_amount': occupancy.rent,
                    'paid_date': previous_month + timedelta(days=3),
                    'notes': f"Rent for {previous_month.strftime('%B %Y')}"
                }
            )
            if created:
                rent_records_created.append(prev_rent)
            
            # Two months ago - all paid
            old_rent, created = Rent.objects.get_or_create(
                occupancy=occupancy,
                month=two_months_ago,
                defaults={
                    'amount': occupancy.rent,
                    'paid_amount': occupancy.rent,
                    'paid_date': two_months_ago + timedelta(days=2),
                    'notes': f"Rent for {two_months_ago.strftime('%B %Y')}"
                }
            )
            if created:
                rent_records_created.append(old_rent)
        
        if rent_records_created:
            self.stdout.write(self.style.SUCCESS(f'Created {len(rent_records_created)} rent records'))
        
        # ========== CREATE ISSUES ==========
        self.stdout.write(self.style.WARNING('\nCreating Issues...'))
        
        issue_data = [
            {
                'title': 'Water Leakage in Bathroom',
                'description': 'There is a continuous water leakage from the bathroom tap. Needs immediate attention.',
                'priority': 'URGENT',
                'status': 'OPEN',
                'assigned_to': 'Plumber - Rajesh',
                'unit_idx': 0
            },
            {
                'title': 'AC Not Working',
                'description': 'The air conditioner in the living room is not cooling properly.',
                'priority': 'HIGH',
                'status': 'ASSIGNED',
                'assigned_to': 'AC Repair - Service Center',
                'unit_idx': 1
            },
            {
                'title': 'Door Lock Issue',
                'description': 'Main door lock is getting stuck, difficult to open.',
                'priority': 'MEDIUM',
                'status': 'IN_PROGRESS',
                'assigned_to': 'Locksmith - Local Shop',
                'unit_idx': 2
            },
            {
                'title': 'Paint Peeling Off',
                'description': 'Wall paint is peeling off in the bedroom. Needs repainting.',
                'priority': 'LOW',
                'status': 'RESOLVED',
                'assigned_to': 'Painter - Contractor',
                'unit_idx': 3
            },
            {
                'title': 'Electricity Problem',
                'description': 'Frequent power cuts and voltage fluctuations in the unit.',
                'priority': 'URGENT',
                'status': 'OPEN',
                'assigned_to': 'Electrician - Local',
                'unit_idx': 4
            },
            {
                'title': 'Fan Repair Needed',
                'description': 'Ceiling fan in the room is making noise and not rotating properly.',
                'priority': 'MEDIUM',
                'status': 'ASSIGNED',
                'assigned_to': 'Electrician',
                'unit_idx': 5
            },
        ]
        
        issues_created = []
        for issue_info in issue_data:
            if issue_info['unit_idx'] < len(flat_units):
                unit = flat_units[issue_info['unit_idx']]
                # Get tenant from occupancy if exists
                occupancy = Occupancy.objects.filter(unit=unit, is_active=True).first()
                tenant = occupancy.tenant if occupancy else None
                
                issue, created = Issue.objects.get_or_create(
                    unit=unit,
                    title=issue_info['title'],
                    defaults={
                        'tenant': tenant,
                        'description': issue_info['description'],
                        'priority': issue_info['priority'],
                        'status': issue_info['status'],
                        'assigned_to': issue_info['assigned_to'],
                        'raised_date': date.today() - timedelta(days=issue_info['unit_idx'] * 2)
                    }
                )
                if created:
                    issues_created.append(issue)
        
        if issues_created:
            self.stdout.write(self.style.SUCCESS(f'Created {len(issues_created)} issues'))
        
        # ========== SUMMARY ==========
        total_buildings = Building.objects.filter(account=account).count()
        total_units = Unit.objects.filter(account=account).count()
        total_pg_rooms = PGRoom.objects.filter(unit__account=account).count()
        total_beds = Bed.objects.filter(room__unit__account=account).count()
        total_tenants = Tenant.objects.filter(account=account).count()
        total_occupancies = Occupancy.objects.filter(tenant__account=account, is_active=True).count()
        total_rents = Rent.objects.filter(occupancy__tenant__account=account).count()
        total_issues = Issue.objects.filter(unit__account=account).count()
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('📊 COMPREHENSIVE DEMO DATA SUMMARY'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(self.style.SUCCESS(f'  🏢 Buildings: {total_buildings}'))
        self.stdout.write(self.style.SUCCESS(f'  🏠 Total Units: {total_units}'))
        self.stdout.write(self.style.SUCCESS(f'  🛏️  PG Rooms: {total_pg_rooms}'))
        self.stdout.write(self.style.SUCCESS(f'  🛏️  Beds: {total_beds}'))
        self.stdout.write(self.style.SUCCESS(f'  👥 Tenants: {total_tenants}'))
        self.stdout.write(self.style.SUCCESS(f'  📋 Active Occupancies: {total_occupancies}'))
        self.stdout.write(self.style.SUCCESS(f'  💰 Rent Records: {total_rents}'))
        self.stdout.write(self.style.SUCCESS(f'  ⚠️  Issues: {total_issues}'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(self.style.SUCCESS(f'\n✅ Demo data created successfully for {username}!'))
        self.stdout.write(self.style.SUCCESS(f'🌐 Login at: http://127.0.0.1:8000/'))
        self.stdout.write(self.style.SUCCESS(f'📱 Username: {username}'))
        self.stdout.write(self.style.SUCCESS('\n💡 You can now test all features:'))
        self.stdout.write(self.style.SUCCESS('   - View buildings, units, and tenants'))
        self.stdout.write(self.style.SUCCESS('   - Check rent management with paid/pending records'))
        self.stdout.write(self.style.SUCCESS('   - Review issues with different statuses'))
        self.stdout.write(self.style.SUCCESS('   - See vacancy intelligence'))
        self.stdout.write(self.style.SUCCESS('   - Test tenant list and history'))

