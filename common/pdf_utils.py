"""
PDF Utility Functions for generating receipts and reports
"""
from io import BytesIO
from django.utils import timezone
from decimal import Decimal
import os

# Try to import reportlab, set flag if not available
REPORTLAB_AVAILABLE = False
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    REPORTLAB_AVAILABLE = True
except ImportError:
    # ReportLab not installed - functions will raise helpful errors
    pass


def generate_rent_receipt_pdf(rent, account_name=None, include_header=True, signed_by_user=None, tenant_name=None):
    """
    Generate a professional rent receipt PDF
    
    Args:
        rent: Rent model instance
        account_name: Name of the property management company/owner
        include_header: Whether to include company header
        signed_by_user: User object (owner/manager) who is signing the receipt
        tenant_name: Tenant's name (if not provided, will use rent.occupancy.tenant.name)
    
    Returns:
        BytesIO buffer containing the PDF
    
    Raises:
        ImportError: If reportlab is not installed
    """
    if not REPORTLAB_AVAILABLE:
        raise ImportError(
            "ReportLab is not installed. Please install it using: pip install reportlab==3.6.13"
        )
    
    buffer = BytesIO()
    
    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm
    )
    
    # Get styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    styles.add(ParagraphStyle(
        name='ReceiptTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1e40af')
    ))
    
    styles.add(ParagraphStyle(
        name='ReceiptSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#64748b'),
        spaceAfter=20
    ))
    
    styles.add(ParagraphStyle(
        name='SectionHeader',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1e40af'),
        spaceBefore=15,
        spaceAfter=10
    ))
    
    styles.add(ParagraphStyle(
        name='ReceiptLabel',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#64748b')
    ))
    
    styles.add(ParagraphStyle(
        name='ReceiptValue',
        parent=styles['Normal'],
        fontSize=11,
        fontName='Helvetica-Bold'
    ))
    
    styles.add(ParagraphStyle(
        name='AmountLarge',
        parent=styles['Normal'],
        fontSize=28,
        fontName='Helvetica-Bold',
        alignment=TA_CENTER,
        textColor=colors.HexColor('#10b981')
    ))
    
    styles.add(ParagraphStyle(
        name='Footer',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#94a3b8')
    ))
    
    # Build document elements
    elements = []
    
    # Get rent details
    occupancy = rent.occupancy
    tenant = occupancy.tenant
    
    # Determine location
    if occupancy.unit:
        building = occupancy.unit.building
        location = f"Unit {occupancy.unit.unit_number}"
        property_type = "Flat"
    else:
        building = occupancy.bed.room.unit.building
        location = f"Room {occupancy.bed.room.room_number}, Bed {occupancy.bed.bed_number}"
        property_type = "PG"
    
    # Header
    if include_header:
        company_name = account_name or building.account.name or "Property Management"
        elements.append(Paragraph(company_name, styles['ReceiptTitle']))
        elements.append(Paragraph(building.address[:100] if building.address else "", styles['ReceiptSubtitle']))
        elements.append(Spacer(1, 10))
    
    # Receipt Title
    elements.append(Paragraph("RENT RECEIPT", styles['ReceiptTitle']))
    elements.append(Paragraph(f"Receipt No: RR-{rent.id:06d}", styles['ReceiptSubtitle']))
    elements.append(Spacer(1, 10))
    
    # Status Badge
    status_color = colors.HexColor('#10b981') if rent.status == 'PAID' else colors.HexColor('#f59e0b') if rent.status == 'PARTIAL' else colors.HexColor('#ef4444')
    status_text = "PAID" if rent.status == 'PAID' else "PARTIAL PAYMENT" if rent.status == 'PARTIAL' else "PENDING"
    
    status_table = Table(
        [[Paragraph(f"<font color='white'><b>{status_text}</b></font>", styles['Normal'])]],
        colWidths=[100]
    )
    status_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), status_color),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 15),
        ('RIGHTPADDING', (0, 0), (-1, -1), 15),
    ]))
    
    # Center the status badge
    status_wrapper = Table([[status_table]], colWidths=[doc.width])
    status_wrapper.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    elements.append(status_wrapper)
    elements.append(Spacer(1, 20))
    
    # Amount Box
    amount_text = f"₹{rent.paid_amount:,.0f}" if rent.status in ['PAID', 'PARTIAL'] else f"₹{rent.amount:,.0f}"
    elements.append(Paragraph(amount_text, styles['AmountLarge']))
    elements.append(Paragraph(f"For {rent.month.strftime('%B %Y')}", styles['ReceiptSubtitle']))
    elements.append(Spacer(1, 20))
    
    # Horizontal line
    line_table = Table([['']], colWidths=[doc.width])
    line_table.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, 0), 1, colors.HexColor('#e2e8f0')),
    ]))
    elements.append(line_table)
    elements.append(Spacer(1, 15))
    
    # Tenant Details Section
    elements.append(Paragraph("Tenant Details", styles['SectionHeader']))
    
    tenant_data = [
        ['Name:', tenant.name, 'Phone:', tenant.phone],
        ['Property:', building.name, 'Type:', property_type],
        ['Location:', location, 'Move-in:', occupancy.start_date.strftime('%d %b %Y')],
    ]
    
    tenant_table = Table(tenant_data, colWidths=[70, 180, 70, 130])
    tenant_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
        ('FONTNAME', (3, 0), (3, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#64748b')),
        ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#64748b')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(tenant_table)
    elements.append(Spacer(1, 15))
    
    # Payment Details Section
    elements.append(Paragraph("Payment Details", styles['SectionHeader']))
    
    payment_data = [
        ['Rent Month', rent.month.strftime('%B %Y')],
        ['Expected Amount', f'₹{rent.amount:,.0f}'],
        ['Paid Amount', f'₹{rent.paid_amount:,.0f}'],
    ]
    
    if rent.status == 'PARTIAL':
        pending = rent.amount - rent.paid_amount
        payment_data.append(['Pending Amount', f'₹{pending:,.0f}'])
    
    if rent.paid_date:
        payment_data.append(['Payment Date', rent.paid_date.strftime('%d %b %Y')])
    
    payment_table = Table(payment_data, colWidths=[150, 300])
    payment_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#64748b')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, colors.HexColor('#e2e8f0')),
        ('LINEBELOW', (0, -1), (-1, -1), 1.5, colors.HexColor('#1e40af')),
    ]))
    elements.append(payment_table)
    elements.append(Spacer(1, 30))
    
    # Notes if any
    if rent.notes:
        elements.append(Paragraph("Notes", styles['SectionHeader']))
        elements.append(Paragraph(rent.notes, styles['Normal']))
        elements.append(Spacer(1, 20))
    
    # Signature Section
    # Get tenant name
    tenant_display_name = tenant_name or rent.occupancy.tenant.name
    
    # Get signed by name (owner/manager who is logged in)
    if signed_by_user:
        signed_by_name = signed_by_user.get_full_name() or signed_by_user.username
        signed_by_role = getattr(signed_by_user, 'role', '').title() or 'Authorized'
    else:
        signed_by_name = "Authorized Person"
        signed_by_role = "Authorized"
    
    sig_data = [
        ['', ''],
        ['_' * 30, '_' * 30],
        [tenant_display_name, signed_by_name],
        ["Tenant", signed_by_role],
    ]
    
    sig_table = Table(sig_data, colWidths=[doc.width/2, doc.width/2])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTSIZE', (0, 2), (-1, 2), 11),  # Name in slightly larger font
        ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),  # Names in bold
        ('TEXTCOLOR', (0, 0), (-1, 1), colors.HexColor('#000000')),  # Underline in black
        ('TEXTCOLOR', (0, 2), (-1, 2), colors.HexColor('#1e40af')),  # Names in blue
        ('TEXTCOLOR', (0, 3), (-1, 3), colors.HexColor('#64748b')),  # Labels in gray
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 2), (-1, 2), 10),  # Extra padding for names
    ]))
    elements.append(sig_table)
    elements.append(Spacer(1, 30))
    
    # Footer
    generated_date = timezone.now().strftime('%d %b %Y, %I:%M %p')
    elements.append(Paragraph(f"Generated on {generated_date}", styles['Footer']))
    elements.append(Paragraph("This is a computer-generated receipt.", styles['Footer']))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    return buffer


def generate_bulk_receipts_pdf(rents, account_name=None):
    """
    Generate multiple rent receipts in a single PDF
    
    Args:
        rents: List of Rent model instances
        account_name: Name of the property management company/owner
    
    Returns:
        BytesIO buffer containing the PDF
    
    Raises:
        ImportError: If reportlab is not installed
    """
    if not REPORTLAB_AVAILABLE:
        raise ImportError(
            "ReportLab is not installed. Please install it using: pip install reportlab==3.6.13"
        )
    
    from reportlab.platypus import PageBreak
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm
    )
    
    elements = []
    
    for i, rent in enumerate(rents):
        # Generate single receipt content
        single_buffer = generate_rent_receipt_pdf(rent, account_name)
        
        # For bulk, we'll just add page breaks between receipts
        if i > 0:
            elements.append(PageBreak())
        
        # Add receipt number header
        styles = getSampleStyleSheet()
        elements.append(Paragraph(f"Receipt {i+1} of {len(rents)}", styles['Normal']))
    
    # For now, return single receipts - bulk implementation would need more work
    if len(rents) == 1:
        return generate_rent_receipt_pdf(rents[0], account_name)
    
    return buffer

