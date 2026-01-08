"""
Management command to create comprehensive test data.

FLAT SYSTEM: One rent entry per flat (one person pays total rent)
PG SYSTEM: One rent entry per bed (each bed pays individually)

Run: python manage.py setup_test_data --reset
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta
import random

from accounts.models import Account
from buildings.models import Building, BuildingAccess
from units.models import Unit, PGRoom, Bed
from tenants.models import Tenant
from occupancy.models import Occupancy
from rent.models import Rent
from issues.models import Issue

User = get_user_model()


class Command(BaseCommand):
    help = 'Creates test data with FLAT (one rent per flat) and PG (rent per bed) systems'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Delete all data before creating new')

    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write(self.style.WARNING('🗑️  Deleting all existing data...'))
            self.reset_all_data()

        self.stdout.write(self.style.SUCCESS('\n📦 Creating test data...\n'))
        
        # Create two accounts
        yuvraj_account = self.create_account('Yuvraj Properties', 'yuvraj', 'Yuvraj', 'Dhakar', 'yuvraj123')
        shubham_account = self.create_account('Shubham Estates', 'shubham', 'Shubham', 'Verma', 'shubham123')
        
        # Create managers
        manager1_y = self.create_manager('manager1_y', 'Rahul', 'Manager', yuvraj_account)
        manager2_y = self.create_manager('manager2_y', 'Priya', 'Manager', yuvraj_account)
        manager1_s = self.create_manager('manager1_s', 'Amit', 'Manager', shubham_account)
        manager2_s = self.create_manager('manager2_s', 'Neha', 'Manager', shubham_account)
        
        # === YUVRAJ'S PROPERTIES ===
        self.stdout.write(self.style.HTTP_INFO('\n🏢 Creating Yuvraj\'s Properties...\n'))
        
        # Building 1: Green Valley (FLATS) - 3 flats with different scenarios
        gv = self.create_building(yuvraj_account, 'Green Valley Apartments', '123 MG Road, Bangalore - 560001', 5)
        
        # Flat 101: Single tenant, fully paid
        flat_101 = self.create_flat(gv, '101', '1BHK', 15000, 30000)
        t1 = self.create_tenant(yuvraj_account, 'Arjun Reddy', '9876543210')
        self.create_occupancy(t1, flat_101, 15000, date(2025, 1, 15))
        self.create_flat_rent(t1, flat_101, 15000, 15000, date(2026, 1, 1), 'PAID')
        
        # Flat 102: 3 tenants sharing (roommates), partial payment
        flat_102 = self.create_flat(gv, '102', '3BHK', 36000, 72000)
        t2 = self.create_tenant(yuvraj_account, 'Divya Singh', '9827055867')
        t3 = self.create_tenant(yuvraj_account, 'Sneha Mehta', '9883745683')
        t4 = self.create_tenant(yuvraj_account, 'Priya Reddy', '9853960167')
        self.create_occupancy(t2, flat_102, 36000, date(2025, 2, 20))  # Primary tenant pays full rent
        self.create_occupancy(t3, flat_102, 0, date(2025, 6, 14))  # Roommate (no separate rent)
        self.create_occupancy(t4, flat_102, 0, date(2025, 8, 30))  # Roommate (no separate rent)
        self.create_flat_rent(t2, flat_102, 36000, 20000, date(2026, 1, 1), 'PARTIAL')  # ₹16000 pending
        
        # Flat 103: Single tenant, pending payment
        flat_103 = self.create_flat(gv, '103', '2BHK', 22000, 44000)
        t5 = self.create_tenant(yuvraj_account, 'Vikram Joshi', '9812345678')
        self.create_occupancy(t5, flat_103, 22000, date(2025, 3, 1))
        self.create_flat_rent(t5, flat_103, 22000, 0, date(2026, 1, 1), 'PENDING')  # Not paid
        
        # Flat 104: Vacant
        self.create_flat(gv, '104', '2BHK', 20000, 40000, status='VACANT')
        
        # Flat 105: Single tenant, fully paid
        flat_105 = self.create_flat(gv, '105', '1BHK', 12000, 24000)
        t6 = self.create_tenant(yuvraj_account, 'Kavita Nair', '9898989898')
        self.create_occupancy(t6, flat_105, 12000, date(2025, 4, 10))
        self.create_flat_rent(t6, flat_105, 12000, 12000, date(2026, 1, 1), 'PAID')
        
        # Grant manager1 access to Green Valley
        BuildingAccess.objects.get_or_create(user=manager1_y, building=gv, defaults={'created_by': User.objects.get(username='yuvraj')})
        
        # Building 2: Tech Park PG (PG SYSTEM) - 3 Floors, 8 Rooms, 20 Beds
        tp = self.create_building(yuvraj_account, 'Tech Park PG', '456 Whitefield, Bangalore - 560066', 3)
        pg_unit = self.create_pg_unit(tp, 'Main Block')
        
        self.stdout.write(self.style.HTTP_INFO('    📍 Floor 1 (Ground Floor)'))
        
        # Floor 1: Room 101, 102, 103
        room_101 = self.create_pg_room(pg_unit, '101', 3)  # 3-sharing, ₹5000/bed
        bed_101_a = self.create_bed(room_101, '1')
        bed_101_b = self.create_bed(room_101, '2')
        bed_101_c = self.create_bed(room_101, '3', status='VACANT')
        t7 = self.create_tenant(yuvraj_account, 'Suresh Kumar', '9123456789')
        t8 = self.create_tenant(yuvraj_account, 'Ramesh Verma', '9234567890')
        self.create_bed_occupancy(t7, bed_101_a, 5000, date(2025, 5, 1))
        self.create_bed_occupancy(t8, bed_101_b, 5000, date(2025, 5, 15))
        self.create_bed_rent(t7, bed_101_a, 5000, 5000, date(2026, 1, 1), 'PAID')
        self.create_bed_rent(t8, bed_101_b, 5000, 3000, date(2026, 1, 1), 'PARTIAL')
        
        room_102 = self.create_pg_room(pg_unit, '102', 2)  # 2-sharing, ₹6000/bed
        bed_102_a = self.create_bed(room_102, '1')
        bed_102_b = self.create_bed(room_102, '2')
        t9 = self.create_tenant(yuvraj_account, 'Ganesh Iyer', '9345678901')
        t10 = self.create_tenant(yuvraj_account, 'Mahesh Rao', '9456789012')
        self.create_bed_occupancy(t9, bed_102_a, 6000, date(2025, 6, 1))
        self.create_bed_occupancy(t10, bed_102_b, 6000, date(2025, 6, 10))
        self.create_bed_rent(t9, bed_102_a, 6000, 6000, date(2026, 1, 1), 'PAID')
        self.create_bed_rent(t10, bed_102_b, 6000, 0, date(2026, 1, 1), 'PENDING')
        
        room_103 = self.create_pg_room(pg_unit, '103', 4)  # 4-sharing, ₹4000/bed
        bed_103_a = self.create_bed(room_103, '1')
        bed_103_b = self.create_bed(room_103, '2')
        bed_103_c = self.create_bed(room_103, '3', status='VACANT')
        bed_103_d = self.create_bed(room_103, '4', status='VACANT')
        t11 = self.create_tenant(yuvraj_account, 'Ajay Patel', '9567890123')
        t12 = self.create_tenant(yuvraj_account, 'Vijay Singh', '9678901234')
        self.create_bed_occupancy(t11, bed_103_a, 4000, date(2025, 7, 1))
        self.create_bed_occupancy(t12, bed_103_b, 4000, date(2025, 7, 15))
        self.create_bed_rent(t11, bed_103_a, 4000, 4000, date(2026, 1, 1), 'PAID')
        self.create_bed_rent(t12, bed_103_b, 4000, 4000, date(2026, 1, 1), 'PAID')
        
        self.stdout.write(self.style.HTTP_INFO('    📍 Floor 2'))
        
        # Floor 2: Room 201, 202
        room_201 = self.create_pg_room(pg_unit, '201', 3)  # 3-sharing, ₹5500/bed
        bed_201_a = self.create_bed(room_201, '1')
        bed_201_b = self.create_bed(room_201, '2')
        bed_201_c = self.create_bed(room_201, '3')
        t13 = self.create_tenant(yuvraj_account, 'Rohit Sharma', '9789012345')
        t14 = self.create_tenant(yuvraj_account, 'Amit Verma', '9890123456')
        t15 = self.create_tenant(yuvraj_account, 'Karan Kapoor', '9901234567')
        self.create_bed_occupancy(t13, bed_201_a, 5500, date(2025, 8, 1))
        self.create_bed_occupancy(t14, bed_201_b, 5500, date(2025, 8, 10))
        self.create_bed_occupancy(t15, bed_201_c, 5500, date(2025, 8, 20))
        self.create_bed_rent(t13, bed_201_a, 5500, 5500, date(2026, 1, 1), 'PAID')
        self.create_bed_rent(t14, bed_201_b, 5500, 0, date(2026, 1, 1), 'PENDING')
        self.create_bed_rent(t15, bed_201_c, 5500, 2000, date(2026, 1, 1), 'PARTIAL')
        
        room_202 = self.create_pg_room(pg_unit, '202', 2)  # 2-sharing, ₹7000/bed (AC)
        bed_202_a = self.create_bed(room_202, '1')
        bed_202_b = self.create_bed(room_202, '2', status='VACANT')
        t16 = self.create_tenant(yuvraj_account, 'Nikhil Jain', '9012345678')
        self.create_bed_occupancy(t16, bed_202_a, 7000, date(2025, 9, 1))
        self.create_bed_rent(t16, bed_202_a, 7000, 7000, date(2026, 1, 1), 'PAID')
        
        self.stdout.write(self.style.HTTP_INFO('    📍 Floor 3'))
        
        # Floor 3: Room 301 (Single occupancy - premium)
        room_301 = self.create_pg_room(pg_unit, '301', 1)  # Single, ₹10000/bed
        bed_301_a = self.create_bed(room_301, '1')
        t17 = self.create_tenant(yuvraj_account, 'Rajesh Menon', '9123450000')
        self.create_bed_occupancy(t17, bed_301_a, 10000, date(2025, 10, 1))
        self.create_bed_rent(t17, bed_301_a, 10000, 10000, date(2026, 1, 1), 'PAID')
        
        # Grant manager2 access to Tech Park PG
        BuildingAccess.objects.get_or_create(user=manager2_y, building=tp, defaults={'created_by': User.objects.get(username='yuvraj')})
        
        # === SHUBHAM'S PROPERTIES ===
        self.stdout.write(self.style.HTTP_INFO('\n🏢 Creating Shubham\'s Properties...\n'))
        
        # Building: Royal Palace (FLATS)
        rp = self.create_building(shubham_account, 'Royal Palace', '321 Indiranagar, Bangalore - 560038', 6)
        
        flat_201 = self.create_flat(rp, '201', '2BHK', 25000, 50000)
        t11 = self.create_tenant(shubham_account, 'Arun Sharma', '9567890123')
        self.create_occupancy(t11, flat_201, 25000, date(2025, 1, 1))
        self.create_flat_rent(t11, flat_201, 25000, 25000, date(2026, 1, 1), 'PAID')
        
        flat_202 = self.create_flat(rp, '202', '3BHK', 35000, 70000)
        t12 = self.create_tenant(shubham_account, 'Meera Krishnan', '9678901234')
        self.create_occupancy(t12, flat_202, 35000, date(2025, 2, 1))
        self.create_flat_rent(t12, flat_202, 35000, 15000, date(2026, 1, 1), 'PARTIAL')
        
        self.create_flat(rp, '203', '1BHK', 18000, 36000, status='VACANT')
        
        BuildingAccess.objects.get_or_create(user=manager1_s, building=rp, defaults={'created_by': User.objects.get(username='shubham')})
        
        # Create some issues
        self.create_issue(yuvraj_account, flat_101, 'Leaking Tap', 'Kitchen tap is leaking', 'MEDIUM', 'OPEN')
        self.create_issue(yuvraj_account, flat_102, 'AC Not Working', 'Bedroom AC not cooling', 'HIGH', 'ASSIGNED')
        self.create_issue(shubham_account, flat_201, 'Door Lock Issue', 'Main door lock stuck', 'URGENT', 'OPEN')
        
        self.print_summary()

    def reset_all_data(self):
        """Delete ALL data in correct order"""
        from django.db import connection
        
        try:
            # Delete in dependency order
            Issue.objects.all().delete()
            self.stdout.write('  ✓ Issues deleted')
        except Exception as e:
            self.stdout.write(f'  ⚠ Issues: {e}')
            
        try:
            Rent.objects.all().delete()
            self.stdout.write('  ✓ Rent records deleted')
        except Exception as e:
            self.stdout.write(f'  ⚠ Rent: {e}')
            
        try:
            Occupancy.objects.all().delete()
            self.stdout.write('  ✓ Occupancies deleted')
        except Exception as e:
            self.stdout.write(f'  ⚠ Occupancies: {e}')
            
        try:
            Tenant.objects.all().delete()
            self.stdout.write('  ✓ Tenants deleted')
        except Exception as e:
            self.stdout.write(f'  ⚠ Tenants: {e}')
            
        try:
            Bed.objects.all().delete()
            self.stdout.write('  ✓ Beds deleted')
        except Exception as e:
            self.stdout.write(f'  ⚠ Beds: {e}')
            
        try:
            PGRoom.objects.all().delete()
            self.stdout.write('  ✓ PG Rooms deleted')
        except Exception as e:
            self.stdout.write(f'  ⚠ PG Rooms: {e}')
            
        try:
            Unit.objects.all().delete()
            self.stdout.write('  ✓ Units deleted')
        except Exception as e:
            self.stdout.write(f'  ⚠ Units: {e}')
            
        try:
            BuildingAccess.objects.all().delete()
            self.stdout.write('  ✓ Building Access deleted')
        except Exception as e:
            self.stdout.write(f'  ⚠ Building Access: {e}')
            
        try:
            Building.objects.all().delete()
            self.stdout.write('  ✓ Buildings deleted')
        except Exception as e:
            self.stdout.write(f'  ⚠ Buildings: {e}')
            
        try:
            User.objects.exclude(is_superuser=True).delete()
            self.stdout.write('  ✓ Users deleted')
        except Exception as e:
            self.stdout.write(f'  ⚠ Users: {e}')
            
        try:
            Account.objects.all().delete()
            self.stdout.write('  ✓ Accounts deleted')
        except Exception as e:
            self.stdout.write(f'  ⚠ Accounts: {e}')
        
        self.stdout.write(self.style.SUCCESS('✓ Data reset complete'))

    def create_account(self, name, username, first_name, last_name, password):
        account, _ = Account.objects.get_or_create(name=name)
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': f'{username}@example.com',
                'first_name': first_name,
                'last_name': last_name,
                'account': account,
                'role': 'OWNER'
            }
        )
        if created:
            user.set_password(password)
            user.save()
        self.stdout.write(f'  ✓ Account: {name} | Owner: {username} (pw: {password})')
        return account

    def create_manager(self, username, first_name, last_name, account):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': f'{username}@example.com',
                'first_name': first_name,
                'last_name': last_name,
                'account': account,
                'role': 'MANAGER'
            }
        )
        if created:
            user.set_password('manager123')
            user.save()
        self.stdout.write(f'    → Manager: {username} (pw: manager123)')
        return user

    def create_building(self, account, name, address, floors):
        building, _ = Building.objects.get_or_create(
            name=name, account=account,
            defaults={'address': address, 'total_floors': floors}
        )
        self.stdout.write(f'  🏢 {name}')
        return building

    def create_flat(self, building, unit_number, bhk_type, rent, deposit, status='OCCUPIED'):
        unit, _ = Unit.objects.get_or_create(
            unit_number=unit_number, building=building, account=building.account,
            defaults={
                'unit_type': 'FLAT',
                'bhk_type': bhk_type,
                'expected_rent': Decimal(rent),
                'deposit': Decimal(deposit),
                'status': status
            }
        )
        status_icon = '🟢' if status == 'OCCUPIED' else '🔴'
        self.stdout.write(f'    {status_icon} Flat {unit_number} ({bhk_type}) - ₹{rent}/mo')
        return unit

    def create_pg_unit(self, building, unit_number):
        unit, _ = Unit.objects.get_or_create(
            unit_number=unit_number, building=building, account=building.account,
            defaults={
                'unit_type': 'PG', 
                'status': 'OCCUPIED',
                'expected_rent': Decimal(0),  # PG rent is per bed, not per unit
                'deposit': Decimal(0)
            }
        )
        self.stdout.write(f'    🏠 PG Unit {unit_number}')
        return unit

    def create_pg_room(self, unit, room_number, sharing_type):
        room, _ = PGRoom.objects.get_or_create(
            unit=unit, room_number=room_number,
            defaults={'sharing_type': sharing_type}
        )
        self.stdout.write(f'      🚪 Room {room_number} ({sharing_type}-sharing)')
        return room

    def create_bed(self, room, bed_id, status='OCCUPIED'):
        bed, _ = Bed.objects.get_or_create(
            room=room, bed_number=f'Bed-{bed_id}',
            defaults={'status': status}
        )
        icon = '🛏️' if status == 'OCCUPIED' else '⬜'
        self.stdout.write(f'        {icon} Bed-{bed_id}')
        return bed

    def create_tenant(self, account, name, phone):
        tenant, _ = Tenant.objects.get_or_create(
            name=name, account=account,
            defaults={
                'phone': phone,
                'email': f'{name.lower().replace(" ", ".")}@example.com',
                'id_proof_type': 'Aadhar',
                'id_proof_number': f'{random.randint(1000,9999)}{random.randint(10000000,99999999)}'
            }
        )
        return tenant

    def create_occupancy(self, tenant, unit, rent, start_date):
        """Create flat occupancy"""
        occupancy, _ = Occupancy.objects.get_or_create(
            tenant=tenant, unit=unit, is_active=True,
            defaults={
                'rent': Decimal(rent),
                'deposit': unit.deposit or 0,
                'start_date': start_date,
            }
        )
        self.stdout.write(f'      👤 {tenant.name} → Flat {unit.unit_number} (₹{rent}/mo)')
        return occupancy

    def create_bed_occupancy(self, tenant, bed, rent, start_date):
        """Create PG bed occupancy"""
        occupancy, _ = Occupancy.objects.get_or_create(
            tenant=tenant, bed=bed, is_active=True,
            defaults={
                'rent': Decimal(rent),
                'deposit': Decimal(rent * 2),
                'start_date': start_date,
            }
        )
        bed.status = 'OCCUPIED'
        bed.save()
        self.stdout.write(f'        👤 {tenant.name} → {bed.bed_number} (₹{rent}/mo)')
        return occupancy

    def create_flat_rent(self, tenant, unit, amount, paid, month, status):
        """Create FLAT rent - one entry for whole flat"""
        occupancy = Occupancy.objects.filter(tenant=tenant, unit=unit, is_active=True).first()
        if not occupancy:
            return None
        
        rent, _ = Rent.objects.get_or_create(
            occupancy=occupancy, month=month,
            defaults={
                'amount': Decimal(amount),
                'paid_amount': Decimal(paid),
                'status': status,
                'paid_date': timezone.now().date() if paid > 0 else None,
                'notes': f'Flat rent for {unit.unit_number}'
            }
        )
        pending = amount - paid
        icon = '✅' if status == 'PAID' else ('⚠️' if status == 'PARTIAL' else '❌')
        self.stdout.write(f'      {icon} Rent: ₹{amount} | Paid: ₹{paid} | Pending: ₹{pending}')
        return rent

    def create_bed_rent(self, tenant, bed, amount, paid, month, status):
        """Create PG bed rent - one entry per bed"""
        occupancy = Occupancy.objects.filter(tenant=tenant, bed=bed, is_active=True).first()
        if not occupancy:
            return None
        
        rent, _ = Rent.objects.get_or_create(
            occupancy=occupancy, month=month,
            defaults={
                'amount': Decimal(amount),
                'paid_amount': Decimal(paid),
                'status': status,
                'paid_date': timezone.now().date() if paid > 0 else None,
                'notes': f'Bed rent for {bed.bed_number}'
            }
        )
        icon = '✅' if status == 'PAID' else ('⚠️' if status == 'PARTIAL' else '❌')
        self.stdout.write(f'          {icon} Rent: ₹{amount} | Paid: ₹{paid}')
        return rent

    def create_issue(self, account, unit, title, description, priority, status):
        Issue.objects.get_or_create(
            title=title, unit=unit,
            defaults={
                'description': description,
                'priority': priority,
                'status': status
            }
        )

    def print_summary(self):
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('📊 TEST DATA SUMMARY'))
        self.stdout.write(self.style.SUCCESS('='*60))
        
        self.stdout.write(f'''
┌─────────────────────────────────────────────────────────────┐
│  LOGIN CREDENTIALS                                          │
├─────────────────────────────────────────────────────────────┤
│  OWNER 1:  yuvraj / yuvraj123                               │
│  OWNER 2:  shubham / shubham123                             │
│  MANAGERS: manager1_y, manager2_y, manager1_s, manager2_s   │
│            Password: manager123                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  TEST SCENARIOS                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  🏢 FLATS (One rent per flat)                               │
│  ─────────────────────────────                              │
│  Flat 101: 1 tenant, PAID (₹15,000)                         │
│  Flat 102: 3 tenants sharing, PARTIAL (₹20k/36k paid)       │
│  Flat 103: 1 tenant, PENDING (₹0/22k paid)                  │
│  Flat 104: VACANT                                           │
│  Flat 105: 1 tenant, PAID (₹12,000)                         │
│                                                             │
│  🏠 PG (Rent per bed)                                       │
│  ─────────────────────                                      │
│  Room R1: 3-sharing                                         │
│    - Bed A: PAID (₹5,000)                                   │
│    - Bed B: PARTIAL (₹3k/5k paid)                           │
│    - Bed C: VACANT                                          │
│  Room R2: 2-sharing                                         │
│    - Bed A: PAID (₹6,000)                                   │
│    - Bed B: PENDING (₹0/6k paid)                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘

✅ Test data created successfully!
''')
