from datetime import datetime, timedelta, date
import csv
import io
import math
from flask import url_for
from models import TimeEntry, User, Job, LaborActivity, WeeklyApprovalLock
from app import db

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees) using the haversine formula.
    Returns distance in meters.
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371000  # Radius of earth in meters
    return c * r

def get_week_start(target_date):
    """Return the Monday of the week containing the target date."""
    return target_date - timedelta(days=target_date.weekday())

def get_week_range(target_date):
    """Return a tuple of (start_date, end_date) for the week containing target_date."""
    start_date = get_week_start(target_date)
    end_date = start_date + timedelta(days=6)
    return (start_date, end_date)

def is_timesheet_approved(user_id, job_id, week_start):
    """Check if a timesheet is approved for a given user, job, and week."""
    return WeeklyApprovalLock.query.filter_by(
        user_id=user_id,
        job_id=job_id,
        week_start=week_start
    ).first() is not None

def get_weekly_totals(user_id, start_date, end_date=None):
    """Get total hours for a user for a given week."""
    if end_date is None:
        end_date = start_date + timedelta(days=6)

    total_hours = db.session.query(db.func.sum(TimeEntry.hours)).\
        filter(
            TimeEntry.user_id == user_id,
            TimeEntry.date >= start_date,
            TimeEntry.date <= end_date
        ).scalar() or 0

    return total_hours

def get_daily_totals(user_id, start_date, end_date=None):
    """Get daily hour totals for a user for a date range."""
    if end_date is None:
        end_date = start_date + timedelta(days=6)

    # Get all entries in the date range
    entries = TimeEntry.query.filter(
        TimeEntry.user_id == user_id,
        TimeEntry.date >= start_date,
        TimeEntry.date <= end_date
    ).all()

    # Group by date
    daily_totals = {}
    for day in range((end_date - start_date).days + 1):
        current_date = start_date + timedelta(days=day)
        daily_totals[current_date] = 0

    # Sum hours for each date
    for entry in entries:
        daily_totals[entry.date] += entry.hours

    return daily_totals

def get_job_totals(job_id, start_date, end_date=None):
    """Get total hours for a job for a given date range."""
    if end_date is None:
        end_date = start_date + timedelta(days=6)

    total_hours = db.session.query(db.func.sum(TimeEntry.hours)).\
        filter(
            TimeEntry.job_id == job_id,
            TimeEntry.date >= start_date,
            TimeEntry.date <= end_date
        ).scalar() or 0

    return total_hours

def generate_csv_report(data, columns):
    """Generate a CSV report from a list of dictionaries."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()

    for row in data:
        writer.writerow(row)

    output.seek(0)
    return output.getvalue()

def generate_pdf_report(data, columns, title="Report"):
    """Generate a PDF report from a list of dictionaries."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch

    # Create a buffer for the PDF
    buffer = io.BytesIO()

    # Create the PDF document with landscape orientation and 1-inch margins
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=landscape(letter),
        leftMargin=0.25*inch,
        rightMargin=0.25*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )

    # Get styles for paragraphs
    styles = getSampleStyleSheet()
    
    # Create an enhanced title style
    title_style = styles['Heading1'].clone('CustomTitle')
    title_style.alignment = 1  # Center the title
    title_style.fontSize = 16
    title_style.spaceAfter = 12
    title_style.spaceBefore = 6
    title_style.textColor = colors.Color(0.2, 0.2, 0.6)  # Dark blue
    
    # Create a subtitle style for timestamp
    subtitle_style = styles['Normal'].clone('Subtitle')
    subtitle_style.fontSize = 10
    subtitle_style.alignment = 1  # Center
    subtitle_style.spaceAfter = 20  # More space after timestamp

    # Define Column Headers and their display names
    header_map = {
        'id': 'ID',
        'date': 'Date',
        'hours': 'Hours',
        'approved': 'Approved',
        'worker_name': 'Worker Name',
        'job_code': 'Job Code',
        'job_description': 'Job Description',
        'activity': 'Activity',
        'trade_category': 'Trade Category'
    }

    # Format the data for the table
    table_data = []
    
    # Create header row with proper column names
    header_row = [header_map.get(col, col.replace('_', ' ').title()) for col in columns]
    table_data.append(header_row)

    # Add data rows
    for row in data:
        # Format any special types (dates, booleans)
        formatted_row = []
        for col in columns:
            value = row.get(col, '')
            # Format dates to USA style (MM/DD/YYYY)
            if col == 'date' and isinstance(value, (datetime, date)):
                value = value.strftime('%m/%d/%Y')
            # Format booleans
            elif col == 'approved':
                value = 'Yes' if value else 'No'
            # Format numeric values
            elif col == 'hours' and isinstance(value, (int, float)):
                value = f"{value:.2f}"  # Format with 2 decimal places
            # Truncate long text fields to prevent bleeding
            elif isinstance(value, str):
                if 'description' in col and len(value) > 25:
                    value = value[:22] + '...'
                elif col == 'activity' and len(value) > 18:
                    value = value[:15] + '...'
                elif col == 'worker_name' and len(value) > 20:
                    value = value[:17] + '...'
            formatted_row.append(value)
        table_data.append(formatted_row)

    # Create better column widths for a more balanced layout
    col_widths = []
    
    # Calculate available width (landscape letter is 11 inches, minus margins)
    available_width = 10.5*inch  # 10.5 inches available
    
    # Adjust widths based on column type and number of columns
    for col in columns:
        if col == 'id':
            col_widths.append(0.6*inch)  # ID columns are narrow
        elif col == 'date':
            col_widths.append(1.0*inch)  # Date columns have fixed width
        elif col == 'hours':
            col_widths.append(0.8*inch)  # Hours columns are narrow
        elif col == 'approved':
            col_widths.append(0.9*inch)  # Boolean columns
        elif 'description' in col or col == 'job_description':
            col_widths.append(2.2*inch)  # Description columns need more space
        elif col == 'worker_name':
            col_widths.append(1.5*inch)  # Name columns need moderate space
        elif col == 'job_code':
            col_widths.append(1.1*inch)  # Job codes are moderately sized
        elif col == 'activity':
            col_widths.append(1.4*inch)  # Activity names need moderate space
        elif col == 'trade_category':
            col_widths.append(1.1*inch)  # Trade categories are short
        else:
            col_widths.append(1.3*inch)  # Default width for other columns
    
    # If total width exceeds available space, scale down proportionally but keep minimum widths
    total_width = sum(col_widths)
    if total_width > available_width:
        scale_factor = available_width / total_width
        # Don't scale too aggressively - minimum scale factor of 0.7
        scale_factor = max(scale_factor, 0.7)
        col_widths = [width * scale_factor for width in col_widths]
    
    # Create the table with specified widths
    table = Table(table_data, colWidths=col_widths)
    
    # Create a dark color for the header (similar to #333)
    dark_header = colors.Color(0.2, 0.2, 0.2)
    # Create a light gray for zebra striping (similar to #f9f9f9)
    light_gray = colors.Color(0.98, 0.98, 0.98)
    
    # Basic table styling with improved appearance
    style_list = [
        # Header styling - dark background with white text
        ('BACKGROUND', (0, 0), (-1, 0), dark_header),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),  # Center header cells
        ('FONTSIZE', (0, 0), (-1, 0), 10),     # Slightly larger font for header
        
        # Grid lines
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),  # Thicker outer border
        
        # Text styling
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        
        # Padding - increased for better readability (8px)
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        
        # Extra padding for header row
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
    ]
    
    # Right-align numeric columns
    for i, col in enumerate(columns):
        if col == 'hours' or col == 'id':
            style_list.append(('ALIGN', (i, 1), (i, -1), 'RIGHT'))
    
    # Add zebra striping - alternating light gray and white backgrounds
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            style_list.append(('BACKGROUND', (0, i), (-1, i), colors.white))
        else:
            style_list.append(('BACKGROUND', (0, i), (-1, i), light_gray))
    
    table_style = TableStyle(style_list)
    
    # Apply the style
    table.setStyle(table_style)
    
    # Build the PDF document content
    elements = []

    # Add title
    elements.append(Paragraph(title, title_style))

    # Add timestamp with improved style
    timestamp = Paragraph(f"Generated: {datetime.now().strftime('%m/%d/%Y %H:%M:%S')}", 
                          subtitle_style)
    elements.append(timestamp)

    # Add the table with repeating headers on each page
    table.repeatRows = 1  # Repeat the header row on each page
    elements.append(table)
    
    # We already applied zebra striping earlier, no need to do it again
    # Removed duplicate zebra striping that was causing issues

    # Create a function to add header and footer to each page
    def add_header_footer(canvas, doc):
        canvas.saveState()
        
        # Add header
        header_text = title
        canvas.setFont('Helvetica-Bold', 12)
        canvas.setFillColor(colors.Color(0.2, 0.2, 0.6))  # Dark blue
        # Center the header
        text_width = canvas.stringWidth(header_text, 'Helvetica-Bold', 12)
        x_position = (doc.pagesize[0] - text_width) / 2
        y_position = doc.pagesize[1] - 0.3*inch
        canvas.drawString(x_position, y_position, header_text)
        
        # Add page number in header (top right)
        page_num = f"Page {canvas.getPageNumber()}"
        canvas.setFont('Helvetica', 10)
        canvas.setFillColor(colors.Color(0.4, 0.4, 0.4))  # Gray
        page_text_width = canvas.stringWidth(page_num, 'Helvetica', 10)
        page_x_position = doc.pagesize[0] - 0.5*inch - page_text_width
        canvas.drawString(page_x_position, y_position, page_num)
        
        # Add footer
        footer_text = "Construction Timesheet Management System © 2025"
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(colors.Color(0.75, 0.75, 0.75))
        # Position at bottom-right with 0.5 inch margin
        footer_text_width = canvas.stringWidth(footer_text, 'Helvetica', 7)
        footer_x_position = doc.pagesize[0] - 0.5*inch - footer_text_width
        footer_y_position = 0.3*inch
        canvas.drawString(footer_x_position, footer_y_position, footer_text)
        
        canvas.restoreState()

    # Build the PDF with the header and footer function
    doc.build(elements, onFirstPage=add_header_footer, onLaterPages=add_header_footer)
    buffer.seek(0)
    
    # Get PDF size and log it
    pdf_size = len(buffer.getvalue())
    print(f"DEBUG: Generated PDF size: {pdf_size} bytes")
    
    # Create a new buffer with the content
    pdf_data = buffer.getvalue()
    buffer.close()
    
    # Debug help - log the type and size before return
    print(f"DEBUG: PDF data type: {type(pdf_data)}, size: {len(pdf_data)} bytes")
    if len(pdf_data) == 0:
        print("ERROR: Generated PDF is empty!")
    
    return pdf_data

def generate_job_cost_csv(data, title="Job Cost Report"):
    """Generate a flat CSV report for job costing suitable for accounting software import."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write column headers for accounting software import
    headers = [
        'Date',
        'Job_Code',
        'Job_Description', 
        'Worker_Name',
        'Labor_Activity',
        'Trade_Category',
        'Hours',
        'Burden_Rate_Per_Hour',
        'Total_Labor_Cost'
    ]
    writer.writerow(headers)
    
    # Sort data by date first, then by job_code
    sorted_data = sorted(data, key=lambda x: (x['date'], x['job_code']))
    
    # Write each entry as a separate row
    for row in sorted_data:
        # Format date in US style (MM/DD/YYYY)
        formatted_date = row['date'].strftime('%m/%d/%Y') if hasattr(row['date'], 'strftime') else row['date']
        
        # Clean numeric values - remove currency symbols and ensure proper formatting
        burden_rate = float(row['burden_rate']) if row['burden_rate'] else 0.00
        total_cost = float(row['total_cost']) if 'total_cost' in row and row['total_cost'] else 0.00
        hours = float(row['hours']) if row['hours'] else 0.00
        
        # Get trade category if available
        trade_category = row.get('trade_category', '')
        
        writer.writerow([
            formatted_date,
            row['job_code'],
            row['job_description'],
            row['worker_name'],
            row['activity'],
            trade_category,
            f"{hours:.2f}",
            f"{burden_rate:.2f}",
            f"{total_cost:.2f}"
        ])
    
    output.seek(0)
    return output.getvalue()

def generate_job_cost_pdf(data, title="Job Cost Report"):
    """Generate a specialized PDF report for job costing with summary metrics."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    
    # Create a buffer for the PDF
    buffer = io.BytesIO()
    
    # Create the PDF document with landscape orientation
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=landscape(letter),
        leftMargin=0.25*inch,
        rightMargin=0.25*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )
    
    # Get styles
    styles = getSampleStyleSheet()
    title_style = styles['Heading1'].clone('CustomTitle')
    title_style.alignment = 1  # Center
    title_style.fontSize = 16
    title_style.spaceAfter = 12
    
    subtitle_style = styles['Heading2'].clone('Subtitle')
    subtitle_style.fontSize = 12
    subtitle_style.spaceAfter = 6
    
    # Group data by job
    jobs = {}
    total_hours = 0
    total_cost = 0
    
    for row in data:
        job_code = row['job_code']
        if job_code not in jobs:
            jobs[job_code] = {
                'description': row['job_description'],
                'entries': [],
                'total_hours': 0,
                'total_cost': 0
            }
        
        hours = float(row['hours'])
        cost = float(row['total_cost']) if 'total_cost' in row else 0
        
        jobs[job_code]['entries'].append(row)
        jobs[job_code]['total_hours'] += hours
        jobs[job_code]['total_cost'] += cost
        
        total_hours += hours
        total_cost += cost
    
    # Build PDF elements
    elements = []
    
    # Add title
    elements.append(Paragraph(title, title_style))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%m/%d/%Y %H:%M:%S')}", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    # Add summary metrics table
    elements.append(Paragraph("Summary Metrics", subtitle_style))
    summary_data = [
        ['Total Labor Cost', f'${total_cost:,.2f}'],
        ['Total Hours', f'{total_hours:.2f}'],
        ['Average Cost per Hour', f'${(total_cost/total_hours) if total_hours > 0 else 0:,.2f}'],
        ['Number of Jobs', str(len(jobs))]
    ]
    
    summary_table = Table(summary_data, colWidths=[2*inch, 1.5*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(summary_table)
    elements.append(Spacer(1, 20))
    
    # Add detailed breakdown by job
    elements.append(Paragraph("Detailed Breakdown by Job", subtitle_style))
    
    for job_code in sorted(jobs.keys()):
        job_data = jobs[job_code]
        
        # Job header
        elements.append(Paragraph(f"Job: {job_code} - {job_data['description']}", styles['Heading3']))
        
        # Job detail table
        job_table_data = [['Date', 'Worker', 'Activity', 'Hours', 'Burden Rate', 'Total Cost']]
        
        for entry in job_data['entries']:
            burden_rate = f"${float(entry['burden_rate']):,.2f}" if entry['burden_rate'] else "N/A"
            total_cost_entry = f"${float(entry['total_cost']):,.2f}" if 'total_cost' in entry else "$0.00"
            
            # Format date in US style (MM/DD/YYYY)
            formatted_date = entry['date'].strftime('%m/%d/%Y') if hasattr(entry['date'], 'strftime') else str(entry['date'])
            job_table_data.append([
                formatted_date,
                entry['worker_name'],
                entry['activity'],
                str(entry['hours']),
                burden_rate,
                total_cost_entry
            ])
        
        # Add subtotal row
        job_table_data.append([
            'SUBTOTAL', '', '', f'{job_data["total_hours"]:.2f}', '', f'${job_data["total_cost"]:,.2f}'
        ])
        
        job_table = Table(job_table_data, colWidths=[1*inch, 1.5*inch, 1.5*inch, 0.8*inch, 1*inch, 1*inch])
        job_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightblue),  # Subtotal row
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold')
        ]))
        
        elements.append(job_table)
        elements.append(Spacer(1, 12))
    
    # Add grand total
    grand_total_data = [['GRAND TOTAL', '', '', f'{total_hours:.2f}', '', f'${total_cost:,.2f}']]
    grand_total_table = Table(grand_total_data, colWidths=[1*inch, 1.5*inch, 1.5*inch, 0.8*inch, 1*inch, 1*inch])
    grand_total_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.darkgreen),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(grand_total_table)
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    pdf_data = buffer.getvalue()
    buffer.close()
    
    return pdf_data

def generate_payroll_pdf(data, title="Payroll Report"):
    """Generate a specialized PDF report for payroll with worker-centric layout."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from datetime import datetime
    
    # Create a buffer for the PDF
    buffer = io.BytesIO()
    
    def add_header_footer(canvas, doc):
        """Add header and footer to each page"""
        canvas.saveState()
        
        # Centered Header
        canvas.setFont('Helvetica-Bold', 14)
        canvas.drawCentredString(letter[0]/2, letter[1] - 0.3*inch, title)
        
        # Footer with page number (center) and date/time (right)
        canvas.setFont('Helvetica', 9)
        canvas.drawCentredString(letter[0]/2, 0.3*inch, f"Page {doc.page}")
        
        # Date/time in smaller font at bottom right
        canvas.setFont('Helvetica', 7)
        canvas.drawRightString(letter[0] - 0.5*inch, 0.3*inch, 
                              f"{datetime.now().strftime('%m/%d/%Y %H:%M:%S')}")
        
        canvas.restoreState()
    
    # Create the PDF document
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter,
        leftMargin=0.5*inch,
        rightMargin=0.5*inch,
        topMargin=0.75*inch,  # More space for header
        bottomMargin=0.75*inch  # More space for footer
    )
    
    # Get styles
    styles = getSampleStyleSheet()
    title_style = styles['Heading1'].clone('CustomTitle')
    title_style.alignment = 1  # Center
    title_style.fontSize = 16
    title_style.spaceAfter = 12
    
    worker_style = styles['Heading2'].clone('WorkerHeader')
    worker_style.fontSize = 14
    worker_style.spaceAfter = 6
    
    # Group data by worker, then by project
    workers = {}
    
    for row in data:
        worker_name = row['worker_name']
        project = row['job_description']
        
        if worker_name not in workers:
            workers[worker_name] = {}
        
        if project not in workers[worker_name]:
            workers[worker_name][project] = []
        
        workers[worker_name][project].append(row)
    
    # Build PDF elements
    elements = []
    
    # Process each worker
    worker_count = 0
    for worker_name in sorted(workers.keys()):
        worker_count += 1
        
        # Start new page for each worker (except first)
        if worker_count > 1:
            elements.append(PageBreak())
        
        # Add worker header
        elements.append(Paragraph(worker_name, worker_style))
        elements.append(Spacer(1, 6))
        
        # Add column headers
        header_data = [["    Date", "    Project", "    Activity", "    Hours", "    Approved"]]
        header_table = Table(header_data, colWidths=[1.5*inch, 2.5*inch, 2*inch, 1*inch, 1*inch])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        elements.append(header_table)
        elements.append(Spacer(1, 3))
        
        worker_total_hours = 0
        
        # Process each project for this worker
        for project in sorted(workers[worker_name].keys()):
            project_entries = workers[worker_name][project]
            project_total_hours = 0
            
            # Create table data for this project
            project_table_data = []
            
            for entry in project_entries:
                hours = float(entry['hours'])
                project_total_hours += hours
                
                # Format date
                formatted_date = entry['date'].strftime('%m/%d/%Y') if hasattr(entry['date'], 'strftime') else str(entry['date'])
                
                # Approved status
                approved_status = "Yes" if entry['approved'] else "No"
                
                # Limit project name to 35 characters
                display_project = project if len(project) <= 35 else project[:35] + "..."
                
                project_table_data.append([
                    f"    {formatted_date}",  # Indented
                    f"    {display_project}",       # Indented
                    f"    {entry['activity']}",  # Indented
                    f"    {hours:.2f}",     # Indented
                    f"    {approved_status}" # Indented
                ])
            
            # Add project subtotal
            project_table_data.append([
                f"    Project Total:",
                "",
                "",
                f"    {project_total_hours:.2f}",
                ""
            ])
            
            # Create table without grid
            project_table = Table(project_table_data, colWidths=[1.5*inch, 2.5*inch, 2*inch, 1*inch, 1*inch])
            project_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),  # Project total row
                ('SPACEAFTER', (0, 0), (-1, -1), 2),
            ]))
            
            elements.append(project_table)
            elements.append(Spacer(1, 6))
            
            worker_total_hours += project_total_hours
        
        # Add worker total
        worker_total_data = [[f"{worker_name.upper()} TOTAL: {worker_total_hours:.2f} hours", "", "", "", ""]]
        worker_total_table = Table(worker_total_data, colWidths=[1.5*inch, 2.5*inch, 2*inch, 1*inch, 1*inch])
        worker_total_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
        ]))
        
        elements.append(worker_total_table)
        elements.append(Spacer(1, 20))
    
    # Build PDF with header/footer function
    doc.build(elements, onFirstPage=add_header_footer, onLaterPages=add_header_footer)
    buffer.seek(0)
    
    pdf_data = buffer.getvalue()
    buffer.close()
    
    return pdf_data

def generate_payroll_csv(data, title="Payroll Report"):
    """Generate a flat QuickBooks-compatible payroll CSV report."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write only the CSV header row
    writer.writerow(['Employee_Name', 'Date', 'Job_Code', 'Job_Description', 'Activity_Code', 'Hours', 'Day_of_Week', 'Week_Ending'])
    
    # Filter to approved entries only and sort by worker name then date
    approved_entries = [row for row in data if row.get('approved', False)]
    sorted_entries = sorted(approved_entries, key=lambda x: (x['worker_name'], x['date']))
    
    for entry in sorted_entries:
        # Format activity name without spaces for QB compatibility
        activity_formatted = entry['activity'].replace(' ', '_').replace('-', '_')
        
        # Calculate day of week and week ending date
        entry_date = datetime.strptime(str(entry['date']), '%Y-%m-%d')
        day_of_week = entry_date.strftime('%A')
        
        # Calculate week ending (Sunday)
        days_until_sunday = (6 - entry_date.weekday()) % 7
        week_ending = entry_date + timedelta(days=days_until_sunday)
        week_ending_str = week_ending.strftime('%m/%d/%Y')
        
        # Format date as MM/DD/YYYY
        formatted_date = entry_date.strftime('%m/%d/%Y')
        
        writer.writerow([
            entry['worker_name'],
            formatted_date,
            entry['job_code'],
            entry['job_description'],
            activity_formatted,
            f"{float(entry['hours']):.2f}",
            day_of_week,
            week_ending_str
        ])
    
    output.seek(0)
    return output.getvalue()

def send_email_with_attachment(recipient_email, subject, body, attachment_data=None, attachment_filename=None, attachment_mimetype=None):
    """
    Send an email with an optional attachment.

    Args:
        recipient_email (str): The recipient's email address
        subject (str): Email subject
        body (str): Email body content (plain text)
        attachment_data (BytesIO, optional): Binary attachment data
        attachment_filename (str, optional): Name of the attachment file
        attachment_mimetype (str, optional): MIME type of the attachment

    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    import smtplib
    import os
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.application import MIMEApplication

    # Get email configuration from environment variables
    smtp_server = os.environ.get('SMTP_SERVER', 'mail.smtp2go.com')
    smtp_port = int(os.environ.get('SMTP_PORT', 2525))  # Using port 2525 for smtp2go
    smtp_username = os.environ.get('SMTP_USERNAME', 'Cmpro@cmpro')
    smtp_password = os.environ.get('SMTP_PASSWORD', 'w7n0w0IBE5QYvpHP')
    sender_email = os.environ.get('SENDER_EMAIL', 'scans@thehensoncompany.com')  # Using verified sender email

    # Validate required credentials
    if not smtp_username or not smtp_password:
        print("Error: SMTP credentials not configured. Set SMTP_USERNAME and SMTP_PASSWORD environment variables.")
        return False

    # Create the email message
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject

    # Attach the body content
    msg.attach(MIMEText(body, 'plain'))

    # Add attachment if provided
    if attachment_data and attachment_filename:
        # Default to 'octet-stream' if mimetype is not provided
        subtype = 'octet-stream'
        if attachment_mimetype:
            subtype = attachment_mimetype.split('/')[-1]
        
        attachment = MIMEApplication(attachment_data.read(), _subtype=subtype)
        attachment.add_header('Content-Disposition', 'attachment', filename=attachment_filename)
        msg.attach(attachment)
        # Reset file pointer in case the attachment needs to be used again
        attachment_data.seek(0)

    try:
        # Connect to the SMTP server
        print(f"Connecting to {smtp_server}:{smtp_port}...")
        server = smtplib.SMTP(smtp_server, smtp_port)
        
        print("Starting TLS...")
        server.starttls()  # Secure the connection
        
        print(f"Logging in as {smtp_username}...")
        server.login(smtp_username, smtp_password)

        # Send the email
        print(f"Sending email to {recipient_email}...")
        server.send_message(msg)
        server.quit()
        print("Email sent successfully!")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        # Add specific error handling for common SMTP errors
        if "authentication failed" in str(e).lower():
            print("Authentication failed. Please check your SMTP_USERNAME and SMTP_PASSWORD.")
        elif "connection refused" in str(e).lower():
            print(f"Connection to {smtp_server}:{smtp_port} refused. Please check your SMTP_SERVER and SMTP_PORT.")
        elif "timeout" in str(e).lower():
            print(f"Connection to {smtp_server}:{smtp_port} timed out. Please check your network settings.")
        return False

def format_date(date_obj):
    """Format a date for display."""
    return date_obj.strftime('%m/%d/%Y') # U.S. date format (MM/DD/YYYY)

def format_datetime(datetime_obj):
    """Format a datetime for display."""
    if datetime_obj:
        return datetime_obj.strftime('%m/%d/%Y %H:%M')
    return ''

def get_labor_activities_for_job(job_id):
    """Get labor activities for a specific job's trade type."""
    job = Job.query.get(job_id)
    if not job:
        return []

    activities = LaborActivity.query.filter_by(trade_category=job.trade_type).all()
    return activities

def geocode_address(address):
    """
    Geocode an address using Nominatim (OpenStreetMap).
    
    Args:
        address (str): The address to geocode
        
    Returns:
        dict: A dictionary with 'lat' and 'lon' keys, or None if geocoding failed
    """
    import urllib.parse
    import urllib.request
    import json
    import time
    
    # Don't try to geocode if address is empty
    if not address or address.strip() == '':
        return None
    
    try:
        # URL encode the address
        encoded_address = urllib.parse.quote(address)
        
        # Build the Nominatim API URL
        # Format: https://nominatim.openstreetmap.org/search?q={address}&format=json&limit=1
        url = f"https://nominatim.openstreetmap.org/search?q={encoded_address}&format=json&limit=1"
        
        # Set a user agent (required by Nominatim's ToS)
        headers = {
            'User-Agent': 'ConstructionTimesheetApp/1.0',
            'Accept': 'application/json'
        }
        
        # Create request
        req = urllib.request.Request(url, headers=headers)
        
        # Send request and get response
        with urllib.request.urlopen(req) as response:
            # Parse JSON response
            data = json.loads(response.read().decode())
            
            # Check if we got any results
            if data and len(data) > 0:
                result = data[0]
                return {
                    'lat': float(result['lat']),
                    'lon': float(result['lon']),
                    'display_name': result.get('display_name', address)
                }
            else:
                print(f"No geocoding results found for address: {address}")
                return None
    
    except Exception as e:
        print(f"Error geocoding address '{address}': {str(e)}")
        return None

def generate_device_audit_csv(data, title="Device Audit Log"):
    """Generate a CSV report for device audit logs."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write CSV header row
    writer.writerow(['Timestamp', 'Employee', 'Action', 'Device_ID', 'Latitude', 'Longitude', 'User_Agent'])
    
    # Sort entries by timestamp (most recent first)
    sorted_entries = sorted(data, key=lambda x: x['timestamp'], reverse=True)
    
    for entry in sorted_entries:
        # Format timestamp to readable format
        if isinstance(entry['timestamp'], str):
            # Parse the timestamp string
            try:
                timestamp_obj = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
            except:
                timestamp_obj = datetime.strptime(entry['timestamp'], '%Y-%m-%d %H:%M:%S.%f')
        else:
            timestamp_obj = entry['timestamp']
        
        formatted_timestamp = timestamp_obj.strftime('%m/%d/%Y %H:%M:%S')
        
        # Format coordinates (handle None/null values)
        latitude = f"{entry['latitude']:.6f}" if entry['latitude'] is not None else ""
        longitude = f"{entry['longitude']:.6f}" if entry['longitude'] is not None else ""
        
        # Truncate user agent for readability
        user_agent = entry.get('user_agent', '')
        if len(user_agent) > 80:
            user_agent = user_agent[:77] + '...'
        
        writer.writerow([
            formatted_timestamp,
            entry['employee_name'],
            entry['action'],
            entry.get('device_id', ''),
            latitude,
            longitude,
            user_agent
        ])
    
    output.seek(0)
    return output.getvalue()