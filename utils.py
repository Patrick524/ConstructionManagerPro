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

    # Create a buffer for the PDF
    buffer = io.BytesIO()

    # Create the PDF document with landscape orientation 
    # (better for reports with many columns)
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))

    # Get styles for paragraphs
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']

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
            # Format dates to USA style (Month Day, Year)
            if col == 'date' and isinstance(value, (datetime, date)):
                value = value.strftime('%m/%d/%Y')
            # Format booleans
            elif col == 'approved':
                value = 'Yes' if value else 'No'
            formatted_row.append(value)
        table_data.append(formatted_row)

    # Create the table
    table = Table(table_data)

    # Style the table
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ])
    table.setStyle(style)

    # Add alternate row coloring
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            style = TableStyle([('BACKGROUND', (0, i), (-1, i), colors.white)])
        else:
            style = TableStyle([('BACKGROUND', (0, i), (-1, i), colors.lightgrey)])
        table.setStyle(style)

    # Build the PDF document content
    elements = []

    # Add title
    elements.append(Paragraph(title, title_style))
    elements.append(Spacer(1, 12))

    # Add timestamp
    timestamp = Paragraph(f"Generated: {datetime.now().strftime('%m/%d/%Y %H:%M:%S')}", 
                          styles['Normal'])
    elements.append(timestamp)
    elements.append(Spacer(1, 12))

    # Add the table
    elements.append(table)

    # Build and return the PDF
    doc.build(elements)
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
    smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.environ.get('SMTP_PORT', 587))
    smtp_username = os.environ.get('SMTP_USERNAME')
    smtp_password = os.environ.get('SMTP_PASSWORD')
    sender_email = os.environ.get('SENDER_EMAIL', smtp_username)

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
        attachment = MIMEApplication(attachment_data.read(), _subtype=attachment_mimetype.split('/')[-1])
        attachment.add_header('Content-Disposition', 'attachment', filename=attachment_filename)
        msg.attach(attachment)
        # Reset file pointer in case the attachment needs to be used again
        attachment_data.seek(0)

    try:
        # Connect to the SMTP server
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Secure the connection
        server.login(smtp_username, smtp_password)

        # Send the email
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def format_date(date_obj):
    """Format a date for display."""
    return date_obj.strftime('%m/%d/%Y') # U.S. date format (MM/DD/YYYY)

def format_datetime(datetime_obj):
    """Format a datetime for display."""
    if datetime_obj:
        return datetime_obj.strftime('%Y-%m-%d %H:%M')
    return ''

def get_labor_activities_for_job(job_id):
    """Get labor activities for a specific job's trade type."""
    job = Job.query.get(job_id)
    if not job:
        return []

    activities = LaborActivity.query.filter_by(trade_category=job.trade_type).all()
    return activities