"""
Management command to generate monthly rent records for all active occupancies.
Run this command at the start of each month to ensure all tenants have rent entries.

Usage:
    python manage.py generate_monthly_rent
    
Can be added to crontab to run automatically:
    0 0 1 * * cd /path/to/project && python manage.py generate_monthly_rent
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
from occupancy.models import Occupancy
from rent.models import Rent


class Command(BaseCommand):
    help = 'Generate monthly rent records for all active occupancies'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating records',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        current_date = timezone.now().date()
        current_month = current_date.replace(day=1)
        
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"  MONTHLY RENT GENERATION - {current_month.strftime('%B %Y')}")
        self.stdout.write(f"{'='*60}\n")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No records will be created\n"))
        
        # Get all active occupancies with rent > 0
        # Skip secondary tenants in shared flats (they have ₹0 rent)
        active_occupancies = Occupancy.objects.filter(
            is_active=True,
            rent__gt=0  # Only occupancies with actual rent
        ).select_related('tenant', 'unit', 'bed', 'bed__room', 'bed__room__unit')
        
        total_occupancies = active_occupancies.count()
        created_count = 0
        already_exists_count = 0
        
        self.stdout.write(f"Found {total_occupancies} active occupancies\n")
        
        for occupancy in active_occupancies:
            # Get tenant name and location for logging
            tenant_name = occupancy.tenant.name
            if occupancy.unit:
                location = f"{occupancy.unit.building.name} - Unit {occupancy.unit.unit_number}"
            elif occupancy.bed:
                location = f"{occupancy.bed.room.unit.building.name} - Room {occupancy.bed.room.room_number}, Bed {occupancy.bed.bed_number}"
            else:
                location = "Unknown"
            
            # Check if rent record exists for current month
            existing = Rent.objects.filter(
                occupancy=occupancy,
                month=current_month
            ).first()
            
            if existing:
                already_exists_count += 1
                self.stdout.write(f"  ✓ {tenant_name} ({location}) - Already has rent record")
            else:
                monthly_rent = occupancy.rent or Decimal('0')
                
                if not dry_run:
                    Rent.objects.create(
                        occupancy=occupancy,
                        month=current_month,
                        amount=monthly_rent,
                        paid_amount=Decimal('0'),
                        status='PENDING',
                        notes=f"Auto-generated rent entry for {current_month.strftime('%B %Y')}"
                    )
                
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  + {tenant_name} ({location}) - Created PENDING rent: ₹{monthly_rent}")
                )
        
        # Summary
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write("  SUMMARY")
        self.stdout.write(f"{'='*60}")
        self.stdout.write(f"  Total occupancies: {total_occupancies}")
        self.stdout.write(f"  Already had records: {already_exists_count}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f"  Would create: {created_count}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"  Created: {created_count}"))
        
        self.stdout.write(f"{'='*60}\n")
        
        if not dry_run and created_count > 0:
            self.stdout.write(self.style.SUCCESS(f"✅ Successfully created {created_count} rent records!"))

