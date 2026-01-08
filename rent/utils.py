"""
Utilities for rent management - Receipt generation, reports, etc.
"""
from django.http import HttpResponse
from django.template.loader import render_to_string
from io import BytesIO
import csv
from decimal import Decimal
from datetime import datetime

# Optional weasyprint for PDF generation
try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False


def generate_rent_receipt(rent, format='html'):
    """
    Generate rent receipt for a rent payment
    
    Args:
        rent: Rent model instance
        format: 'html' or 'pdf'
    
    Returns:
        HttpResponse with receipt
    """
    context = {
        'rent': rent,
        'occupancy': rent.occupancy,
        'tenant': rent.occupancy.tenant,
        'unit': rent.occupancy.unit if rent.occupancy.unit else rent.occupancy.bed.room.unit,
        'bed': rent.occupancy.bed,
        'building': rent.occupancy.unit.building if rent.occupancy.unit else rent.occupancy.bed.room.unit.building,
        'date': datetime.now(),
    }
    
    if format == 'pdf':
        if not WEASYPRINT_AVAILABLE:
            # Fallback to HTML if PDF not available
            html_string = render_to_string('rent/receipt_template.html', context)
            response = HttpResponse(html_string, content_type='text/html')
            response['Content-Disposition'] = f'inline; filename="rent_receipt_{rent.id}_{rent.month.strftime("%Y%m")}.html"'
            return response
        
        html_string = render_to_string('rent/receipt_template.html', context)
        html = HTML(string=html_string)
        pdf_file = html.write_pdf()
        
        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="rent_receipt_{rent.id}_{rent.month.strftime("%Y%m")}.pdf"'
        return response
    else:
        html_string = render_to_string('rent/receipt_template.html', context)
        response = HttpResponse(html_string, content_type='text/html')
        return response


def export_rent_report(rents, format='csv'):
    """
    Export rent data to CSV or Excel
    
    Args:
        rents: QuerySet of Rent objects
        format: 'csv' or 'excel'
    
    Returns:
        HttpResponse with file
    """
    if format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="rent_report.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Month', 'Tenant', 'Unit/Bed', 'Expected', 'Paid', 'Pending', 'Status', 'Paid Date'])
        
        for rent in rents:
            tenant_name = rent.occupancy.tenant.name
            location = rent.occupancy.unit.unit_number if rent.occupancy.unit else f"{rent.occupancy.bed.room.unit.unit_number} - {rent.occupancy.bed.bed_number}"
            
            writer.writerow([
                rent.month.strftime('%B %Y'),
                tenant_name,
                location,
                str(rent.amount),
                str(rent.paid_amount),
                str(rent.pending_amount),
                rent.get_status_display(),
                rent.paid_date.strftime('%Y-%m-%d') if rent.paid_date else '',
            ])
        
        return response
    
    # Excel export would require openpyxl or xlsxwriter
    # For now, return CSV
    return export_rent_report(rents, format='csv')

