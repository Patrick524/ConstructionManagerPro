from datetime import datetime, timedelta, date
import csv
import io
from flask import url_for
from models import TimeEntry, User, Job, LaborActivity, WeeklyApprovalLock
from app import db

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
            formatted_row.append(value)
        table_data.append(formatted_row)

    # Create better column widths for a more balanced layout
    col_widths = []
    
    # Adjust widths based on column type
    for col in columns:
        if col == 'id':
            col_widths.append(0.7*inch)  # ID columns are narrow
        elif col == 'date':
            col_widths.append(1.0*inch)  # Date columns have fixed width
        elif col == 'hours':
            col_widths.append(0.8*inch)  # Hours columns are narrow
        elif col == 'approved':
            col_widths.append(0.9*inch)  # Boolean columns
        elif 'description' in col or col == 'job_description':
            col_widths.append(2.5*inch)  # Description columns need more space
        elif col == 'worker_name':
            col_widths.append(1.8*inch)  # Name columns need moderate space
        else:
            col_widths.append(1.5*inch)  # Default width for other columns
    
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

    # Add the table
    elements.append(table)

    # Create a function to add a footer to the bottom-right corner of each page
    def add_footer(canvas, doc):
        canvas.saveState()
        footer_text = "Construction Timesheet Management System © 2025"
        # Use a smaller font size (7pt)
        canvas.setFont('Helvetica', 7)
        # Use a lighter gray color
        canvas.setFillColor(colors.Color(0.75, 0.75, 0.75))
        # Position at bottom-right with 0.5 inch margin
        text_width = canvas.stringWidth(footer_text, 'Helvetica', 7)
        x_position = doc.pagesize[0] - 0.5*inch - text_width
        y_position = 0.3*inch
        canvas.drawString(x_position, y_position, footer_text)
        canvas.restoreState()

    # Build the PDF with the footer function
    doc.build(elements, onFirstPage=add_footer, onLaterPages=add_footer)
    buffer.seek(0)
    return buffer

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