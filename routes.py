import os
import csv
import io
from io import BytesIO
import base64
from datetime import datetime, timedelta, date
from functools import wraps
from flask import render_template, redirect, url_for, flash, request, jsonify, send_file, session, abort
from flask_login import login_user, logout_user, current_user, login_required
from app import app, db
from models import User, Job, LaborActivity, TimeEntry, WeeklyApprovalLock, ClockSession, Trade, job_workers, DeviceLog
from sqlalchemy import func
from forms import (LoginForm, RegistrationForm, TimeEntryForm, ApprovalForm,
                   JobForm, LaborActivityForm, UserManagementForm, ReportForm,
                   WeeklyTimesheetForm, ClockInForm, ClockOutForm, TradeForm,
                   JobWorkersForm, GPSComplianceReportForm)
import pandas as pd
import utils


# Context processor to provide the current datetime to all templates
@app.context_processor
def inject_now():
    """Inject the current datetime into all templates"""
    return {'now': datetime.utcnow()}


# Template filter to encode binary data as base64
@app.template_filter('b64encode')
def b64encode_filter(data):
    """Convert binary data to base64 string for embedding in templates"""
    if isinstance(data, bytes):
        return base64.b64encode(data).decode('utf-8')
    return base64.b64encode(data.encode('utf-8')).decode('utf-8')


# Helper function to get the Monday of a given week
def get_week_start(target_date):
    """
    Returns the date of the Monday at the start of the week containing target_date.
    
    Python's weekday() returns 0 for Monday, 1 for Tuesday, etc. So to get to the previous
    Monday, we just subtract the weekday value.
    
    Args:
        target_date: A date object
        
    Returns:
        A date object representing the Monday of the week
    """
    return target_date - timedelta(days=target_date.weekday())


def get_week_range_for_offset(week_offset=0):
    """
    Returns the start and end dates for a week based on an offset from the current week.
    
    Args:
        week_offset: Integer, number of weeks to offset from current week (negative for past, positive for future)
        
    Returns:
        Tuple of (start_date, end_date) as date objects representing Monday and Sunday of the week
    """
    today = datetime.today().date()
    print(f"DEBUG: Today's date is {today}")
    base_monday = today - timedelta(days=today.weekday())
    print(f"DEBUG: Base Monday for current week is {base_monday}")
    start = base_monday + timedelta(weeks=week_offset)
    end = start + timedelta(days=6)
    print(f"DEBUG: Week range with offset {week_offset} is {start} to {end}")
    return start, end


# Custom decorators for role-based access control
def worker_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_worker():
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


def foreman_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_foreman():
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


def foreman_or_admin_required(f):
    """Decorator that allows both foremen and admins to access the route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not (current_user.is_foreman() or current_user.is_admin()):
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


# Authentication routes
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        # Add debug logging for use_clock_in state
        if current_user.is_worker():
            print(
                f"DEBUG: Worker {current_user.name} (ID: {current_user.id}) logged in with use_clock_in = {current_user.use_clock_in}"
            )
            if current_user.use_clock_in:
                print(f"DEBUG: Redirecting worker to clock in/out screen")
                return redirect(url_for('worker_clock'))
            else:
                print(f"DEBUG: Redirecting worker to timesheet screen")
                return redirect(url_for('worker_timesheet'))
        elif current_user.is_foreman():
            return redirect(url_for('foreman_dashboard'))
        else:
            return redirect(url_for('admin_dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.lower() if form.email.data else ''
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')

            if next_page:
                return redirect(next_page)
            elif user.is_worker():
                # Add debug logging for post-login redirect
                print(
                    f"DEBUG: Post-login for worker {user.name} (ID: {user.id}) with use_clock_in = {user.use_clock_in}"
                )
                if user.use_clock_in:
                    print(
                        f"DEBUG: Redirecting worker to clock in/out screen (post-login)"
                    )
                    return redirect(url_for('worker_clock'))
                else:
                    print(
                        f"DEBUG: Redirecting worker to timesheet screen (post-login)"
                    )
                    return redirect(url_for('worker_timesheet'))
            elif user.is_foreman():
                return redirect(url_for('foreman_dashboard'))
            else:
                return redirect(url_for('admin_dashboard'))
        else:
            flash('Incorrect Email or Password. Please try again.',
                  'danger')

    # Ensure that errors are displayed if the form is submitted but invalid
    if request.method == 'POST' and not form.validate():
        flash('Please check your input and try again.', 'warning')
    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    # In a production environment, you might want to restrict registration
    # or require admin approval for new accounts
    if current_user.is_authenticated:
        return redirect(url_for('login'))

    form = RegistrationForm()
    if form.validate_on_submit():
        email = form.email.data.lower() if form.email.data else ''
        user = User(name=form.name.data,
                    email=email,
                    role=form.role.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        flash('Your account has been created! You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))


# Worker routes
@app.route('/worker/weekly', methods=['GET', 'POST'])
@login_required
@worker_required
def worker_weekly_timesheet():
    """Weekly timesheet view allowing workers to enter time for an entire week at once"""
    # Block access for manual time entry workers
    if not current_user.use_clock_in:
        # Manual time entry workers should be redirected to daily view
        flash(
            'Weekly timesheet view is currently unavailable for manual time entry. Please use the daily view.',
            'info')
        return redirect(url_for('worker_timesheet'))
    print("DEBUG: Weekly timesheet form submission - Request method:",
          request.method)
    print("DEBUG: Form data:", request.form)

    form = WeeklyTimesheetForm(current_user=current_user)

    # Check if we're loading a specific job's labor activities
    job_id = request.args.get('job_id')
    if job_id:
        job = Job.query.get_or_404(job_id)
        # Populate labor activities for this job's trade type
        form.labor_activity_id.choices = [
            (activity.id, activity.name)
            for activity in LaborActivity.query.filter_by(
                trade_category=job.trade_type).all()
        ]
    else:
        # Default empty list or all activities if no job selected
        form.labor_activity_id.choices = [
            (activity.id, activity.name)
            for activity in LaborActivity.query.all()
        ]

    # Default to current week if no week start provided
    if not form.week_start.data:
        today = date.today()
        # Always use this formula for current week start (Monday)
        form.week_start.data = today - timedelta(days=today.weekday())
        print(
            f"DEBUG: Setting current week start to: {form.week_start.data} (Today is {today})"
        )

    week_start = form.week_start.data
    week_end = week_start + timedelta(days=6)

    # Define days of the week for both validation and form processing
    days_of_week = [('monday', form.monday_hours),
                    ('tuesday', form.tuesday_hours),
                    ('wednesday', form.wednesday_hours),
                    ('thursday', form.thursday_hours),
                    ('friday', form.friday_hours),
                    ('saturday', form.saturday_hours),
                    ('sunday', form.sunday_hours)]

    # Debug the validation process
    if request.method == 'POST':
        print("DEBUG: Validating form...")
        is_valid = form.validate()
        print(f"DEBUG: Form validation result: {is_valid}")
        if not is_valid:
            print("DEBUG: Form errors:", form.errors)

    if form.validate_on_submit():
        print("DEBUG: Form validated successfully, proceeding with submission")
        # Check if any timesheet for this week is already approved/locked
        is_locked = WeeklyApprovalLock.query.filter_by(
            user_id=current_user.id,
            job_id=form.job_id.data,
            week_start=week_start).first()

        if is_locked:
            flash(
                'Cannot add or edit time entries for this week. It has already been approved.',
                'danger')
            return redirect(url_for('worker_weekly_timesheet'))

        # Check maximum 12 hours per day limit
        for i, (day_name, hours_field) in enumerate(days_of_week):
            # Calculate the date for this day
            entry_date = week_start + timedelta(days=i)

            # Get hours from current form
            current_hours = hours_field.data or 0

            # Get existing hours for this day from ALL jobs/activities
            # to properly enforce 12-hour daily maximum
            existing_hours = db.session.query(db.func.sum(
                TimeEntry.hours)).filter(
                    TimeEntry.user_id == current_user.id, 
                    TimeEntry.date == entry_date).scalar() or 0
            
            # Subtract hours from current job/activity to avoid double-counting when editing
            current_job_activity_hours = db.session.query(db.func.sum(
                TimeEntry.hours)).filter(
                    TimeEntry.user_id == current_user.id,
                    TimeEntry.date == entry_date,
                    TimeEntry.job_id == form.job_id.data,
                    TimeEntry.labor_activity_id == form.labor_activity_id.data).scalar() or 0
            existing_hours -= current_job_activity_hours

            total_hours = existing_hours + current_hours

            if total_hours > 12 and current_hours > 0:
                day_name_formatted = day_name.capitalize()
                flash(
                    f'Maximum 12 hours per day exceeded for {day_name_formatted}. You already have {existing_hours:.1f} hours recorded for this day with other jobs/activities.',
                    'danger')
                return redirect(url_for('worker_weekly_timesheet'))

        # First, delete any existing entries for this week with the same activity
        # This ensures we don't get duplicate entries if the user submits multiple times
        TimeEntry.query.filter(
            TimeEntry.user_id == current_user.id,
            TimeEntry.job_id == form.job_id.data,
            TimeEntry.labor_activity_id == form.labor_activity_id.data,
            TimeEntry.date >= week_start, TimeEntry.date <= week_end).delete()

        # Create time entries for each day of the week that has hours
        # Note: days_of_week is already defined above

        entries_created = 0

        for i, (day_name, hours_field) in enumerate(days_of_week):
            # With our improved FloatField, empty values are now safely converted to 0.0
            # So we only need to check for positive hours to create entries
            hours_value = hours_field.data or 0.0
            if hours_value > 0:
                # Calculate the date for this day
                entry_date = week_start + timedelta(days=i)

                # Create new entry
                new_entry = TimeEntry(
                    user_id=current_user.id,
                    job_id=form.job_id.data,
                    labor_activity_id=form.labor_activity_id.data,
                    date=entry_date,
                    hours=hours_value,  # Use the safely processed value
                    notes=form.notes.data)
                db.session.add(new_entry)
                entries_created += 1

        db.session.commit()

        if entries_created > 0:
            flash(
                f'Weekly timesheet saved successfully! Created {entries_created} time entries.',
                'success')
        else:
            flash('Weekly timesheet updated successfully!', 'success')

        # Pass the week_start to maintain the selected date when redirecting
        return redirect(
            url_for('worker_history',
                    start_date=week_start.strftime('%m/%d/%Y')))

    # Get job_id from URL parameters if provided
    if job_id and not form.job_id.data:
        form.job_id.data = int(job_id)

    # If labor_activity_id is in the URL, use it
    labor_activity_id = request.args.get('labor_activity_id')
    if labor_activity_id:
        form.labor_activity_id.data = int(labor_activity_id)

    # Check if this is a GET request or if form failed validation
    if request.method == 'GET' or not form.validate():
        # This is the key part - we're explicitly checking for GET requests to load existing data
        # Reset all hours fields to 0 by default
        form.monday_hours.data = 0.0
        form.tuesday_hours.data = 0.0
        form.wednesday_hours.data = 0.0
        form.thursday_hours.data = 0.0
        form.friday_hours.data = 0.0
        form.saturday_hours.data = 0.0
        form.sunday_hours.data = 0.0

        # Load entries for selected job/activity (for form population)
        if form.job_id.data and form.labor_activity_id.data:
            print(
                f"DEBUG: Searching for entries with job_id={form.job_id.data}, labor_activity_id={form.labor_activity_id.data}, user_id={current_user.id}"
            )
            print(f"DEBUG: Week range: {week_start} to {week_end}")

            job_activity_entries = TimeEntry.query.filter(
                TimeEntry.user_id == current_user.id,
                TimeEntry.job_id == form.job_id.data,
                TimeEntry.labor_activity_id == form.labor_activity_id.data,
                TimeEntry.date >= week_start,
                TimeEntry.date <= week_end).options(
                    db.joinedload(TimeEntry.labor_activity)).all()

            print(
                f"DEBUG: Found {len(job_activity_entries)} existing entries for selected job/activity"
            )

            # If there are existing entries, populate the form
            if job_activity_entries:
                print(f"DEBUG: Setting form values from existing entries")

                # Create a dictionary to store hours by day index
                day_entries = {}
                for entry in job_activity_entries:
                    print(
                        f"DEBUG: Entry date {entry.date}, hours {entry.hours}")
                    day_index = (entry.date - week_start).days
                    if 0 <= day_index <= 6:  # Make sure it's within the week
                        day_entries[day_index] = entry.hours
                        print(
                            f"DEBUG: Day index {day_index} = {entry.hours} hours"
                        )

                # Map each day to the form field
                if 0 in day_entries:
                    form.monday_hours.data = day_entries[0]
                if 1 in day_entries:
                    form.tuesday_hours.data = day_entries[1]
                if 2 in day_entries:
                    form.wednesday_hours.data = day_entries[2]
                if 3 in day_entries:
                    form.thursday_hours.data = day_entries[3]
                if 4 in day_entries:
                    form.friday_hours.data = day_entries[4]
                if 5 in day_entries:
                    form.saturday_hours.data = day_entries[5]
                if 6 in day_entries:
                    form.sunday_hours.data = day_entries[6]

                # Populate notes from any entry (they should be the same)
                if job_activity_entries:
                    form.notes.data = job_activity_entries[0].notes

                print(
                    f"DEBUG: Form values after population: M={form.monday_hours.data}, T={form.tuesday_hours.data}, W={form.wednesday_hours.data}, Total: {sum([form.monday_hours.data or 0, form.tuesday_hours.data or 0, form.wednesday_hours.data or 0, form.thursday_hours.data or 0, form.friday_hours.data or 0, form.saturday_hours.data or 0, form.sunday_hours.data or 0])}"
                )
            else:
                print("DEBUG: No existing entries found to populate form")
    # Handle the case where job_id is set but labor_activity_id is not
    elif form.job_id.data and request.method == 'GET':
        # If just job_id is set but not labor_activity_id, try to find any entries for this job
        # to determine which labor activity to show by default
        print(
            f"DEBUG: Searching for any job entries with job_id={form.job_id.data}"
        )
        job_entries = TimeEntry.query.filter(
            TimeEntry.user_id == current_user.id,
            TimeEntry.job_id == form.job_id.data, TimeEntry.date >= week_start,
            TimeEntry.date <= week_end).options(
                db.joinedload(TimeEntry.labor_activity)).all()

        print(f"DEBUG: Found {len(job_entries)} job entries")

        # Set all hours fields to 0 by default
        form.monday_hours.data = 0.0
        form.tuesday_hours.data = 0.0
        form.wednesday_hours.data = 0.0
        form.thursday_hours.data = 0.0
        form.friday_hours.data = 0.0
        form.saturday_hours.data = 0.0
        form.sunday_hours.data = 0.0

        if job_entries:
            # Group by labor_activity_id
            entries_by_activity = {}
            for entry in job_entries:
                if entry.labor_activity_id not in entries_by_activity:
                    entries_by_activity[entry.labor_activity_id] = []
                entries_by_activity[entry.labor_activity_id].append(entry)

            print(f"DEBUG: Grouped into {len(entries_by_activity)} activities")

            # If entries exist, set the labor_activity_id to the first group and populate form
            if entries_by_activity:
                # Get the first activity and its entries
                activity_id, entries = next(iter(entries_by_activity.items()))
                form.labor_activity_id.data = activity_id
                print(f"DEBUG: Setting labor_activity_id to {activity_id}")

                # Create a dictionary to store hours by day index
                day_entries = {}
                for entry in entries:
                    print(
                        f"DEBUG: Entry date {entry.date}, hours {entry.hours}")
                    day_index = (entry.date - week_start).days
                    if 0 <= day_index <= 6:  # Make sure it's within the week
                        day_entries[day_index] = entry.hours
                        print(
                            f"DEBUG: Day index {day_index} = {entry.hours} hours"
                        )

                # Map each day to the form field
                if 0 in day_entries:
                    form.monday_hours.data = day_entries[0]
                if 1 in day_entries:
                    form.tuesday_hours.data = day_entries[1]
                if 2 in day_entries:
                    form.wednesday_hours.data = day_entries[2]
                if 3 in day_entries:
                    form.thursday_hours.data = day_entries[3]
                if 4 in day_entries:
                    form.friday_hours.data = day_entries[4]
                if 5 in day_entries:
                    form.saturday_hours.data = day_entries[5]
                if 6 in day_entries:
                    form.sunday_hours.data = day_entries[6]

                # Populate notes from any entry (they should be the same)
                if entries:
                    form.notes.data = entries[0].notes

                print(
                    f"DEBUG: Form values after population from job entries: M={form.monday_hours.data}, T={form.tuesday_hours.data}, W={form.wednesday_hours.data}, Total: {sum([form.monday_hours.data or 0, form.tuesday_hours.data or 0, form.wednesday_hours.data or 0, form.thursday_hours.data or 0, form.friday_hours.data or 0, form.saturday_hours.data or 0, form.sunday_hours.data or 0])}"
                )
            else:
                print("DEBUG: No grouped activities found to populate form")
        else:
            print("DEBUG: No job entries found to populate form")

    # Get all time entries for the week regardless of job
    all_week_entries = TimeEntry.query.filter(
        TimeEntry.user_id == current_user.id, TimeEntry.date >= week_start,
        TimeEntry.date
        <= week_end).options(db.joinedload(TimeEntry.job),
                             db.joinedload(TimeEntry.labor_activity)).order_by(
                                 TimeEntry.date, TimeEntry.job_id,
                                 TimeEntry.labor_activity_id).all()

    print(f"DEBUG: Found {len(all_week_entries)} total entries for the week")

    return render_template('worker/weekly_timesheet.html',
                           form=form,
                           all_week_entries=all_week_entries,
                           week_start=week_start)


@app.route('/worker/timesheet', methods=['GET', 'POST'])
@app.route('/worker/timesheet/edit/<int:entry_id>', methods=['GET', 'POST'])
@login_required
@worker_required
def worker_timesheet(entry_id=None):
    # Pass current_user to the form to filter jobs by assignment
    form = TimeEntryForm(current_user=current_user)

    # If entry_id is provided, this is an edit request
    editing = False
    entry_to_edit = None
    
    # No need to manually set job choices as the form now handles this based on user role

    if entry_id:
        # Editing an existing entry - fetch strictly by primary key
        entry_to_edit = db.session.get(TimeEntry, entry_id)
        if not entry_to_edit:
            abort(404)
        
        # Authorization check
        if entry_to_edit.user_id != current_user.id:
            abort(403)

        editing = True

        # Pre-populate the form with the entry's data if this is a GET request
        if request.method == 'GET':
            print(f"DEBUG EDIT: Loading entry {entry_to_edit.id} - Job: {entry_to_edit.job_id}, Hours: {entry_to_edit.hours}, Activity: {entry_to_edit.labor_activity_id}")
            form.job_id.data = entry_to_edit.job_id
            form.date.data = entry_to_edit.date
            form.labor_activity_1.data = entry_to_edit.labor_activity_id
            form.hours_1.data = entry_to_edit.hours
            form.notes.data = entry_to_edit.notes
            print(f"DEBUG EDIT: Form populated - Job: {form.job_id.data}, Hours: {form.hours_1.data}, Activity: {form.labor_activity_1.data}")
    # Default date for new entries - check if user is viewing a specific week
    elif not form.date.data:
        from datetime import timezone, timedelta
        
        # Check if coming from history page with a specific week
        start_date_param = request.args.get('start_date')
        if start_date_param:
            try:
                # Parse the start_date parameter from history page
                viewed_week_start = datetime.strptime(start_date_param, '%m/%d/%Y').date()
                form.date.data = viewed_week_start  # Default to Monday of viewed week
            except (ValueError, TypeError):
                # Fall back to today's date if parsing fails
                pacific_tz = timezone(timedelta(hours=-7))  # PDT is UTC-7
                pacific_now = datetime.now(pacific_tz)
                form.date.data = pacific_now.date()
        else:
            # Use Pacific timezone for accurate local date
            pacific_tz = timezone(timedelta(hours=-7))  # PDT is UTC-7
            pacific_now = datetime.now(pacific_tz)
            form.date.data = pacific_now.date()

    if form.validate_on_submit():
        # Check if timesheet for this date is already approved/locked
        week_start = get_week_start(form.date.data)
        is_locked = WeeklyApprovalLock.query.filter_by(
            user_id=current_user.id,
            job_id=form.job_id.data,
            week_start=week_start).first()

        if is_locked:
            flash(
                'Cannot add or edit time entries for this week. It has already been approved.',
                'danger')
            # Create a fresh form instance with preserved data
            fresh_form = TimeEntryForm(current_user=current_user, formdata=request.form)
            # Re-render the form with preserved values instead of redirecting
            return render_template('worker/timesheet.html', form=fresh_form, editing=editing, entry_to_edit=entry_to_edit)

        # Extract all labor activities from the form and calculate total hours
        total_hours_for_day = 0
        labor_activities = []
        for key in request.form.keys():
            if key.startswith('labor_activity_') and key != 'labor_activity_1':
                index = key.split('_')[-1]
                activity_id = request.form.get(f'labor_activity_{index}')
                hours = request.form.get(f'hours_{index}')
                hours_value = float(hours) if hours and hours.strip() else 0.0
                if hours_value > 0:
                    total_hours_for_day += hours_value

        # Add hours from first activity if valid
        hours_value = form.hours_1.data or 0.0
        if hours_value > 0:
            total_hours_for_day += hours_value

        # Get existing hours for this day from ALL jobs/activities
        # to properly enforce 12-hour daily maximum
        existing_hours = db.session.query(db.func.sum(TimeEntry.hours)).filter(
            TimeEntry.user_id == current_user.id,
            TimeEntry.date == form.date.data
        ).scalar() or 0
        
        # If editing an existing entry, subtract its current hours to avoid double-counting
        if editing and entry_to_edit:
            existing_hours -= entry_to_edit.hours

        # Calculate grand total including existing entries
        grand_total = total_hours_for_day + existing_hours

        # Check if total exceeds 12 hours
        if grand_total > 12 and total_hours_for_day > 0:
            flash(
                f'Maximum 12 hours per day exceeded. You already have {existing_hours:.1f} hours recorded for this day with other jobs. The total would be {grand_total:.1f} hours.',
                'danger')
            # Create a fresh form instance with preserved data
            fresh_form = TimeEntryForm(current_user=current_user, formdata=request.form)
            # Re-render the form with preserved values instead of redirecting
            return render_template('worker/timesheet.html', form=fresh_form, editing=editing, entry_to_edit=entry_to_edit)

        # Extract all labor activities from the form
        labor_activities = []
        for key in request.form.keys():
            if key.startswith('labor_activity_') and key != 'labor_activity_1':
                index = key.split('_')[-1]
                activity_id = request.form.get(f'labor_activity_{index}')
                hours = request.form.get(f'hours_{index}')

                # With our improved FloatField handling, this is now cleaner
                hours_value = float(hours) if hours and hours.strip() else 0.0
                if activity_id and hours_value > 0:
                    labor_activities.append((int(activity_id), hours_value))

        # Add the first activity if it's valid
        # With our improved FloatField, we can directly access the data
        hours_value = form.hours_1.data or 0.0
        if form.labor_activity_1.data and hours_value > 0:
            labor_activities.append((form.labor_activity_1.data, hours_value))

        # Ensure we have at least one valid labor activity
        if not labor_activities:
            flash('You must enter at least one labor activity with hours.',
                  'danger')
            # Create a fresh form instance with preserved data
            fresh_form = TimeEntryForm(current_user=current_user, formdata=request.form)
            # Re-render the form with preserved values instead of redirecting
            return render_template('worker/timesheet.html', form=fresh_form, editing=editing, entry_to_edit=entry_to_edit)

        # Get all activity IDs that will be submitted
        activity_ids = [act_id for act_id, _ in labor_activities]

        # Handle editing vs new entry creation differently
        if editing and entry_to_edit and len(labor_activities) == 1:
            # Simple edit case: update the existing entry in place
            activity_id, hours = labor_activities[0]
            entry_to_edit.job_id = form.job_id.data
            entry_to_edit.labor_activity_id = activity_id
            entry_to_edit.date = form.date.data
            entry_to_edit.hours = hours
            entry_to_edit.notes = form.notes.data
            print(f"DEBUG EDIT: Updated entry {entry_to_edit.id} - Job: {entry_to_edit.job_id}, Hours: {entry_to_edit.hours}, Activity: {entry_to_edit.labor_activity_id}")
        else:
            # Complex case: delete original and recreate (for multiple activities or new entries)
            if editing and entry_to_edit:
                # Delete the original entry when editing becomes complex
                db.session.delete(entry_to_edit)
                
            # For new entries, delete existing entries to avoid duplicates
            if not editing:
                TimeEntry.query.filter(TimeEntry.user_id == current_user.id,
                                       TimeEntry.job_id == form.job_id.data,
                                       TimeEntry.labor_activity_id.in_(activity_ids),
                                       TimeEntry.date == form.date.data).delete()

            # Create new entries for each activity
            for activity_id, hours in labor_activities:
                new_entry = TimeEntry(user_id=current_user.id,
                                      job_id=form.job_id.data,
                                      labor_activity_id=activity_id,
                                      date=form.date.data,
                                      hours=hours,
                                      notes=form.notes.data)
                db.session.add(new_entry)

        db.session.commit()
        flash('Time entry saved successfully!', 'success')
        # Pass the date to maintain the selected date when redirecting
        week_start = get_week_start(form.date.data)
        return redirect(
            url_for('worker_history',
                    start_date=week_start.strftime('%m/%d/%Y')))

    # Get labor activities for the selected job's trade type
    activities = LaborActivity.query.all()

    return render_template('worker/timesheet.html',
                           form=form,
                           activities=activities,
                           editing=editing,
                           entry_to_edit=entry_to_edit)


@app.route('/worker/history')
@login_required
@worker_required
def worker_history():
    # Get date range parameters from query string
    start_date_str = request.args.get('start_date')
    week_offset_str = request.args.get('week_offset', '0')

    try:
        week_offset = int(week_offset_str)
    except ValueError:
        week_offset = 0
        print(
            f"WARNING: Invalid week_offset value: {week_offset_str}, defaulting to 0"
        )

    # If a specific start_date is provided, parse it and find its week offset
    if start_date_str:
        try:
            # Try both common formats: %m/%d/%Y and %Y-%m-%d
            if '/' in start_date_str:
                parsed_date = datetime.strptime(start_date_str,
                                                '%m/%d/%Y').date()
            elif '-' in start_date_str:
                parsed_date = datetime.strptime(start_date_str,
                                                '%Y-%m-%d').date()
            else:
                print(
                    f"WARNING: Invalid date format in start_date: {start_date_str}"
                )
                parsed_date = None

            # Use the parsed date to calculate the appropriate week
            if parsed_date:
                # Always align to Monday
                monday_date = get_week_start(parsed_date)
                print(
                    f"DEBUG: Aligned date {parsed_date} to Monday: {monday_date}"
                )
                # Use this explicitly provided date
                start_date, end_date = monday_date, monday_date + timedelta(
                    days=6)
            else:
                # Fall back to the current week with offset
                start_date, end_date = get_week_range_for_offset(week_offset)
        except ValueError as e:
            print(
                f"WARNING: Error parsing start_date '{start_date_str}': {str(e)}"
            )
            # Fall back to the current week with offset
            start_date, end_date = get_week_range_for_offset(week_offset)
    else:
        # No specific date provided, use the week_offset
        start_date, end_date = get_week_range_for_offset(week_offset)

    print(
        f"DEBUG: Week calculation - date range: {start_date} to {end_date}, week_offset: {week_offset}"
    )

    # Get time entries for the date range
    entries = TimeEntry.query.filter(
        TimeEntry.user_id == current_user.id, TimeEntry.date >= start_date,
        TimeEntry.date <= end_date).order_by(TimeEntry.date.desc()).all()

    # Group entries by date for display
    entries_by_date = {}
    for entry in entries:
        if entry.date not in entries_by_date:
            entries_by_date[entry.date] = []
        entries_by_date[entry.date].append(entry)
    
    # Debug: Print the entries_by_date structure
    print(f"DEBUG: entries_by_date keys: {list(entries_by_date.keys())}")
    for date, date_entries in entries_by_date.items():
        print(f"DEBUG: Date {date} has {len(date_entries)} entries")

    # Get weekly approval status
    week_start = get_week_start(start_date)
    approved_weeks = WeeklyApprovalLock.query.filter_by(
        user_id=current_user.id, week_start=week_start).all()

    approved_jobs = [lock.job_id for lock in approved_weeks]

    return render_template('worker/history.html',
                           entries_by_date=entries_by_date,
                           start_date=start_date,
                           end_date=end_date,
                           approved_jobs=approved_jobs)


@app.route('/worker/clock', methods=['GET'])
@login_required
@worker_required
def worker_clock():
    """Clock in/out interface for workers who use the clock system"""
    # Check if user is configured to use clock in/out
    if not current_user.use_clock_in:
        flash(
            'You are not configured to use the clock in/out system. Please use the timesheet interface.',
            'warning')
        return redirect(url_for('worker_timesheet'))

    try:
        # Get active session (if any) - use only() to select specific columns we need
        # This is more resilient during schema transitions
        from sqlalchemy.orm import load_only

        active_session = ClockSession.query.options(
            load_only(ClockSession.id, ClockSession.user_id,
                      ClockSession.job_id, ClockSession.labor_activity_id,
                      ClockSession.clock_in, ClockSession.clock_out,
                      ClockSession.notes, ClockSession.is_active)).filter_by(
                          user_id=current_user.id, is_active=True).first()

        # Get today's sessions (active and completed)
        today_start = datetime.combine(date.today(), datetime.min.time())
        today_end = datetime.combine(date.today(), datetime.max.time())

        today_sessions = ClockSession.query.options(
            load_only(ClockSession.id, ClockSession.user_id,
                      ClockSession.job_id, ClockSession.labor_activity_id,
                      ClockSession.clock_in, ClockSession.clock_out,
                      ClockSession.notes, ClockSession.is_active)).filter(
                          ClockSession.user_id == current_user.id,
                          ClockSession.clock_in >= today_start,
                          ClockSession.clock_in <= today_end).order_by(
                              ClockSession.clock_in.desc()).all()

        # Calculate today's hours from completed sessions
        today_hours = sum(session.get_duration_hours()
                          for session in today_sessions
                          if not session.is_active)

        # Get recent sessions (completed, not including today)
        recent_sessions = ClockSession.query.options(
            load_only(ClockSession.id, ClockSession.user_id,
                      ClockSession.job_id, ClockSession.labor_activity_id,
                      ClockSession.clock_in, ClockSession.clock_out,
                      ClockSession.notes, ClockSession.is_active)).filter(
                          ClockSession.user_id == current_user.id,
                          ClockSession.is_active == False,
                          ClockSession.clock_in < today_start).order_by(
                              ClockSession.clock_in.desc()).limit(5).all()

        # Prepare forms
        clock_in_form = ClockInForm(current_user=current_user)
        clock_out_form = ClockOutForm()
    except Exception as e:
        # Log the error
        app.logger.error(
            f"Error in worker_clock for user {current_user.id}: {str(e)}")
        # Handle gracefully with a fallback
        flash(
            'There was an issue loading your clock sessions. Please try again later.',
            'warning')
        return redirect(url_for('worker_timesheet'))

    return render_template('worker/clock.html',
                           active_session=active_session,
                           today_sessions=today_sessions,
                           recent_sessions=recent_sessions,
                           today_hours=today_hours,
                           session_count=len(
                               [s for s in today_sessions if not s.is_active]),
                           clock_in_form=clock_in_form,
                           clock_out_form=clock_out_form)


@app.route('/api/device-log', methods=['POST'])
@login_required
def log_device_action():
    """Silent device logging endpoint for audit trail"""
    try:
        data = request.get_json()
        
        device_log = DeviceLog(
            user_id=current_user.id,
            action=data.get('action'),  # 'IN' or 'OUT'
            device_id=data.get('deviceId'),
            ua=data.get('userAgent'),
            lat=data.get('lat'),
            lng=data.get('lng')
        )
        
        db.session.add(device_log)
        db.session.commit()
        
        return jsonify({'success': True}), 200
        
    except Exception as e:
        # Log error but don't block the main action
        app.logger.error(f"Device logging error for user {current_user.id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/worker/clock-in', methods=['POST'])
@login_required
@worker_required
def clock_in():
    """Handle clock in submissions"""
    # Check if user is configured to use clock in/out
    if not current_user.use_clock_in:
        flash('You are not configured to use the clock in/out system.',
              'warning')
        return redirect(url_for('worker_timesheet'))

    # Check if already clocked in - use only critical columns for resilience to schema changes
    try:
        from sqlalchemy.orm import load_only
        active_session = ClockSession.query.options(
            load_only(ClockSession.id, ClockSession.user_id,
                      ClockSession.is_active)).filter_by(
                          user_id=current_user.id, is_active=True).first()
    except Exception as e:
        app.logger.error(
            f"Error querying active sessions in clock_in for user {current_user.id}: {str(e)}"
        )
        active_session = None

    if active_session:
        flash(
            'You are already clocked in! Please clock out of your current session first.',
            'warning')
        return redirect(url_for('worker_clock'))

    form = ClockInForm(current_user=current_user)

    if form.validate_on_submit():
        # Get location data from form
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        accuracy = request.form.get('accuracy')

        # Get job information for distance calculation
        job = Job.query.get(form.job_id.data)
        distance_m = None
        distance_miles = None

        # Calculate distance if we have both user location and job coordinates
        if latitude and longitude and job.latitude and job.longitude:
            try:
                # Convert string values to float
                lat1 = float(latitude)
                lon1 = float(longitude)
                lat2 = float(job.latitude)
                lon2 = float(job.longitude)

                # Calculate the distance
                distance_m = utils.calculate_distance(lat1, lon1, lat2, lon2)
                # Convert to miles (1 meter = 1/1609.34 miles)
                distance_miles = round(distance_m / 1609.34,
                                       2) if distance_m is not None else None
            except (ValueError, TypeError) as e:
                print(f"Error calculating distance: {str(e)}")
                # Continue without distance if calculation fails
                distance_miles = None

        # Create new clock session
        session = ClockSession(
            user_id=current_user.id,
            job_id=form.job_id.data,
            labor_activity_id=form.labor_activity_id.data,
            notes=form.notes.data,
            clock_in=datetime.utcnow(),
            is_active=True,
            # Store location data
            clock_in_latitude=float(latitude) if latitude else None,
            clock_in_longitude=float(longitude) if longitude else None,
            clock_in_accuracy=float(accuracy) if accuracy else None,
            clock_in_distance_mi=distance_miles)

        db.session.add(session)
        db.session.commit()

        # Return JSON response if it's an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'ok':
                True,
                'distance_m':
                round(distance_m) if distance_m is not None else None,
                'distance_mi':
                distance_miles,
                'message':
                'Clocked in successfully'
            })

        # Otherwise, use the regular flash message and redirect
        if distance_m is not None:
            flash(
                f'You have successfully clocked in! Distance from job site: {distance_miles} miles.',
                'success')
        else:
            flash('You have successfully clocked in!', 'success')

        return redirect(url_for('worker_clock'))

    # If form validation fails
    for field, errors in form.errors.items():
        for error in errors:
            flash(f"Error in {getattr(form, field).label.text}: {error}",
                  "danger")

    # Return JSON error if it's an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': False, 'message': 'Form validation failed'}), 400

    return redirect(url_for('worker_clock'))


@app.route('/api/job/<int:job_id>')
@login_required
def get_job_details(job_id):
    try:
        # Use only essential columns to be resilient to schema changes
        from sqlalchemy.orm import load_only

        job = Job.query.options(
            load_only(Job.id, Job.description, Job.location, Job.latitude,
                      Job.longitude, Job.foreman_id)).get(job_id)

        if not job:
            return jsonify({'error': f'Job with ID {job_id} not found'}), 404

        # Handle possible None values gracefully
        return jsonify({
            'description': job.description or '',
            'location': job.location or '',
            'foreman_name': job.foreman.name if job.foreman else '',
            'latitude': job.latitude,
            'longitude': job.longitude
        })
    except Exception as e:
        app.logger.error(
            f"Error in get_job_details for job_id {job_id}: {str(e)}")
        return jsonify({
            'error': 'An error occurred while fetching job details',
            'message': str(e)
        }), 500


@app.route('/worker/clock-out', methods=['POST'])
@login_required
@worker_required
def clock_out():
    """Handle clock out submissions"""
    # Check if user is configured to use clock in/out
    if not current_user.use_clock_in:
        flash('You are not configured to use the clock in/out system.',
              'warning')
        return redirect(url_for('worker_timesheet'))

    # Get active session - use only critical columns for resilience to schema changes
    try:
        from sqlalchemy.orm import load_only
        active_session = ClockSession.query.options(
            load_only(ClockSession.id, ClockSession.user_id,
                      ClockSession.job_id, ClockSession.labor_activity_id,
                      ClockSession.clock_in, ClockSession.notes,
                      ClockSession.is_active)).filter_by(
                          user_id=current_user.id, is_active=True).first()
    except Exception as e:
        app.logger.error(
            f"Error querying active sessions in clock_out for user {current_user.id}: {str(e)}"
        )
        active_session = None

    if not active_session:
        flash('You are not currently clocked in to any job!', 'warning')
        return redirect(url_for('worker_clock'))

    form = ClockOutForm()

    if form.validate_on_submit():
        # Update notes if provided
        if form.notes.data:
            active_session.notes = form.notes.data

        # Get location data from form
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        accuracy = request.form.get('accuracy')

        # Get job information for distance calculation
        job = Job.query.get(active_session.job_id)
        distance_m = None
        distance_miles = None

        # Calculate distance if we have both user location and job coordinates
        if latitude and longitude and job.latitude and job.longitude:
            try:
                # Convert string values to float
                lat1 = float(latitude)
                lon1 = float(longitude)
                lat2 = float(job.latitude)
                lon2 = float(job.longitude)

                # Calculate the distance
                distance_m = utils.calculate_distance(lat1, lon1, lat2, lon2)
                # Convert to miles (1 meter = 1/1609.34 miles)
                distance_miles = round(distance_m / 1609.34,
                                       2) if distance_m is not None else None
            except (ValueError, TypeError) as e:
                print(f"Error calculating distance: {str(e)}")
                # Continue without distance if calculation fails
                distance_miles = None

        # Store location data
        if latitude:
            active_session.clock_out_latitude = float(latitude)
        if longitude:
            active_session.clock_out_longitude = float(longitude)
        if accuracy:
            active_session.clock_out_accuracy = float(accuracy)
        if distance_m is not None:
            active_session.clock_out_distance_mi = distance_miles

        # Clock out
        active_session.clock_out_session()

        # Create a time entry based on this clock session
        time_entry = active_session.create_time_entry()
        if time_entry:
            db.session.add(time_entry)

        db.session.commit()

        hours = active_session.get_duration_hours()

        # Return JSON response if it's an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'ok':
                True,
                'distance_m':
                round(distance_m) if distance_m is not None else None,
                'distance_mi':
                distance_miles,
                'hours':
                round(hours, 2),
                'message':
                'Clocked out successfully'
            })

        # Otherwise, use the regular flash message and redirect
        if distance_m is not None:
            flash(
                f'You have successfully clocked out! {hours:.2f} hours recorded. Distance from job site: {distance_miles} miles.',
                'success')
        else:
            flash(
                f'You have successfully clocked out! {hours:.2f} hours recorded.',
                'success')

        return redirect(url_for('worker_clock'))

    # If form validation fails
    for field, errors in form.errors.items():
        for error in errors:
            flash(f"Error in {getattr(form, field).label.text}: {error}",
                  "danger")

    # Return JSON error if it's an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': False, 'message': 'Form validation failed'}), 400

    return redirect(url_for('worker_clock'))


# Foreman routes
@app.route('/foreman/dashboard')
@login_required
@foreman_required
def foreman_dashboard():
    # Get date range parameters from query string
    start_date_str = request.args.get('start_date')
    week_offset_str = request.args.get('week_offset', '0')

    try:
        week_offset = int(week_offset_str)
    except ValueError:
        week_offset = 0
        print(
            f"WARNING: Invalid week_offset value: {week_offset_str}, defaulting to 0"
        )

    # If a specific start_date is provided, parse it and find its week offset
    if start_date_str:
        try:
            # Try both common formats: %m/%d/%Y and %Y-%m-%d
            if '/' in start_date_str:
                parsed_date = datetime.strptime(start_date_str,
                                                '%m/%d/%Y').date()
            elif '-' in start_date_str:
                parsed_date = datetime.strptime(start_date_str,
                                                '%Y-%m-%d').date()
            else:
                print(
                    f"WARNING: Invalid date format in start_date: {start_date_str}"
                )
                parsed_date = None

            # Use the parsed date to calculate the appropriate week
            if parsed_date:
                # Always align to Monday
                monday_date = get_week_start(parsed_date)
                print(
                    f"DEBUG: Aligned date {parsed_date} to Monday: {monday_date}"
                )
                # Use this explicitly provided date
                start_date, end_date = monday_date, monday_date + timedelta(
                    days=6)
            else:
                # Fall back to the current week with offset
                start_date, end_date = get_week_range_for_offset(week_offset)
        except ValueError as e:
            print(
                f"WARNING: Error parsing start_date '{start_date_str}': {str(e)}"
            )
            # Fall back to the current week with offset
            start_date, end_date = get_week_range_for_offset(week_offset)
    else:
        # No specific date provided, use the week_offset
        start_date, end_date = get_week_range_for_offset(week_offset)

    print(
        f"DEBUG: Week calculation for foreman dashboard - date range: {start_date} to {end_date}, week_offset: {week_offset}"
    )

    # Get all active jobs
    jobs = Job.query.filter_by(status='active').all()

    # For each job, get all workers with time entries
    job_data = []
    for job in jobs:
        # Get unique workers who submitted time for this job in the date range
        workers_query = db.session.query(User).join(TimeEntry, User.id == TimeEntry.user_id).\
            filter(
                TimeEntry.job_id == job.id,
                TimeEntry.date >= start_date,
                TimeEntry.date <= end_date,
                User.role == 'worker'
            ).distinct()

        workers = workers_query.all()

        # Get weekly approval status for each worker
        workers_data = []
        for worker in workers:
            # Check if the week is approved for this worker/job
            is_approved = WeeklyApprovalLock.query.filter_by(
                user_id=worker.id, job_id=job.id,
                week_start=start_date).first() is not None

            # Count total hours for the week
            total_hours = db.session.query(db.func.sum(TimeEntry.hours)).\
                filter(
                    TimeEntry.user_id == worker.id,
                    TimeEntry.job_id == job.id,
                    TimeEntry.date >= start_date,
                    TimeEntry.date <= end_date
                ).scalar() or 0

            # Check if all 7 days of the week have entries
            days_with_entries = db.session.query(TimeEntry.date).\
                filter(
                    TimeEntry.user_id == worker.id,
                    TimeEntry.job_id == job.id,
                    TimeEntry.date >= start_date,
                    TimeEntry.date <= end_date
                ).distinct().count()

            # Check if worker has any entries with notes for this job and week
            has_notes = db.session.query(TimeEntry).\
                filter(
                    TimeEntry.user_id == worker.id,
                    TimeEntry.job_id == job.id,
                    TimeEntry.date >= start_date,
                    TimeEntry.date <= end_date,
                    TimeEntry.notes.isnot(None),
                    db.func.trim(TimeEntry.notes) != ''
                ).first() is not None

            workers_data.append({
                'worker': worker,
                'is_approved': is_approved,
                'total_hours': total_hours,
                'days_with_entries': days_with_entries,
                'has_all_days':
                days_with_entries >= 5,  # Standard work week is 5 days
                'has_notes':
                has_notes  # Flag to indicate if worker has any notes
            })

        job_data.append({'job': job, 'workers': workers_data})

    return render_template('foreman/dashboard.html',
                           job_data=job_data,
                           start_date=start_date,
                           end_date=end_date)


@app.route('/foreman/enter_time/<int:job_id>/<int:user_id>',
           methods=['GET', 'POST'])
@login_required
@foreman_or_admin_required
def foreman_enter_time(job_id, user_id):
    """Allow foremen to enter time on behalf of a worker"""
    print(f"DEBUG: foreman_enter_time called - method={request.method}, job_id={job_id}, user_id={user_id}")
    # Get the worker and job
    worker = User.query.get_or_404(user_id)
    job = Job.query.get_or_404(job_id)

    # Use the same weekly timesheet form as workers, but pass the worker user
    # instead of current_user (foreman) since we're entering time on behalf of the worker
    form = WeeklyTimesheetForm(current_user=worker)
    form.job_id.data = job_id

    # Populate labor activity choices based on job trade
    labor_activities = LaborActivity.query.filter_by(
        trade_category=job.trade_type).all()
    form.labor_activity_id.choices = [('ALL', 'ALL (View All Activities)')] + [(activity.id, activity.name)
                                      for activity in labor_activities]

    # Get week start from query parameters or default to current week
    selected_week = request.args.get('week_start')
    if selected_week:
        try:
            # Try both common formats: %m/%d/%Y and %Y-%m-%d
            if '/' in selected_week:
                parsed_date = datetime.strptime(selected_week,
                                                '%m/%d/%Y').date()
            elif '-' in selected_week:
                parsed_date = datetime.strptime(selected_week,
                                                '%Y-%m-%d').date()
            else:
                print(
                    f"WARNING: Invalid date format in week_start: {selected_week}"
                )
                parsed_date = None

            # Always align to Monday
            if parsed_date:
                form.week_start.data = get_week_start(parsed_date)
                print(
                    f"DEBUG: Aligned date {parsed_date} to Monday: {form.week_start.data}"
                )
            else:
                # Fall back to current week
                today = date.today()
                form.week_start.data = get_week_start(today)
        except ValueError as e:
            print(
                f"WARNING: Error parsing week_start '{selected_week}': {str(e)}"
            )
            # Fall back to current week
            today = date.today()
            form.week_start.data = get_week_start(today)
    elif not form.week_start.data:
        # Default to current week
        today = date.today()
        form.week_start.data = get_week_start(today)

    week_start = form.week_start.data
    week_end = week_start + timedelta(days=6)

    # Check if this week is already approved
    existing_approval = WeeklyApprovalLock.query.filter_by(
        user_id=user_id, job_id=job_id, week_start=week_start).first()

    if existing_approval:
        flash(
            f'This week was already approved by {existing_approval.approver.name} on {existing_approval.approved_at.strftime("%m/%d/%Y %H:%M")}. Time entries cannot be modified.',
            'warning')
        # Pass the week_start to maintain the selected date when redirecting
        return redirect(
            url_for('foreman_dashboard',
                    start_date=week_start.strftime('%m/%d/%Y')))

    # Get existing entries for display purposes - ALL activities for the week
    all_existing_entries = TimeEntry.query.filter(
        TimeEntry.user_id == user_id,
        TimeEntry.job_id == job_id,
        TimeEntry.date >= week_start,
        TimeEntry.date <= week_end
    ).options(db.joinedload(TimeEntry.labor_activity)).order_by(TimeEntry.date, TimeEntry.labor_activity_id).all()

    if form.validate_on_submit():
        # Handle "ALL" view - allow quick daily total adjustments
        if form.labor_activity_id.data == 'ALL':
            # Get General Work labor activity for this job's trade
            general_work_activity = LaborActivity.query.filter_by(
                name='General Work',
                trade_category=job.trade_type
            ).first()
            
            if not general_work_activity:
                flash('General Work labor activity not found for this trade type.', 'danger')
                return render_template('foreman/enter_time.html',
                                     form=form,
                                     worker=worker,
                                     job=job,
                                     week_start=week_start,
                                     week_end=week_end,
                                     existing_entries=existing_entries,
                                     all_existing_entries=all_existing_entries)
            
            # Handle daily total adjustments by calculating differences and creating General Work entries
            monday = form.week_start.data
            dates = [monday + timedelta(days=i) for i in range(7)]
            hours = [
                form.monday_hours.data or 0,
                form.tuesday_hours.data or 0,
                form.wednesday_hours.data or 0,
                form.thursday_hours.data or 0,
                form.friday_hours.data or 0,
                form.saturday_hours.data or 0,
                form.sunday_hours.data or 0
            ]
            
            for i, (date, target_hours) in enumerate(zip(dates, hours)):
                # Calculate current total for this day across all activities
                current_total = db.session.query(func.sum(TimeEntry.hours)).filter(
                    TimeEntry.user_id == user_id,
                    TimeEntry.job_id == job_id,
                    TimeEntry.date == date
                ).scalar() or 0
                
                # Calculate difference
                difference = target_hours - current_total
                
                if difference > 0:
                    # Add additional time as General Work
                    new_entry = TimeEntry(
                        user_id=user_id,
                        job_id=job_id,
                        labor_activity_id=general_work_activity.id,
                        date=date,
                        hours=difference,
                        notes=form.notes.data
                    )
                    db.session.add(new_entry)
                elif difference < 0:
                    # If target is less than current, try to reduce existing General Work entries first
                    general_work_entries = TimeEntry.query.filter(
                        TimeEntry.user_id == user_id,
                        TimeEntry.job_id == job_id,
                        TimeEntry.labor_activity_id == general_work_activity.id,
                        TimeEntry.date == date
                    ).all()
                    
                    reduction_needed = abs(difference)
                    for entry in general_work_entries:
                        if reduction_needed <= 0:
                            break
                        if entry.hours <= reduction_needed:
                            # Remove entire entry
                            reduction_needed -= entry.hours
                            db.session.delete(entry)
                        else:
                            # Reduce entry hours
                            entry.hours -= reduction_needed
                            reduction_needed = 0
            
            try:
                db.session.commit()
                flash(f'Daily total adjustments saved successfully for {worker.name}. Additional time added as General Work.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error saving daily adjustments: {str(e)}', 'danger')
            
            # Redirect back to foreman dashboard with the same week
            if current_user.is_admin():
                return redirect(url_for('admin_review_time', start_date=week_start.strftime('%Y-%m-%d')))
            else:
                return redirect(url_for('foreman_dashboard', start_date=week_start.strftime('%m/%d/%Y')))
        
        # Get the dates for each day of the week
        monday = form.week_start.data
        dates = [monday + timedelta(days=i) for i in range(7)]

        # Get the hours for each day
        hours_values = [
            form.monday_hours.data, form.tuesday_hours.data,
            form.wednesday_hours.data, form.thursday_hours.data,
            form.friday_hours.data, form.saturday_hours.data,
            form.sunday_hours.data
        ]

        # First, check maximum 12 hours per day limit BEFORE deletion
        for i, date_val in enumerate(dates):
            # Get hours from current form for this day
            current_hours = hours_values[i] if hours_values[i] not in [
                None, ''
            ] else 0

            if current_hours and float(current_hours) > 0:
                # Get existing hours for this day from ALL jobs/activities
                existing_hours = db.session.query(db.func.sum(
                    TimeEntry.hours)).filter(
                        TimeEntry.user_id == user_id, 
                        TimeEntry.date == date_val).scalar() or 0
                
                # Subtract hours from current job/activity to avoid double-counting when editing
                current_job_activity_hours = db.session.query(db.func.sum(
                    TimeEntry.hours)).filter(
                        TimeEntry.user_id == user_id,
                        TimeEntry.date == date_val,
                        TimeEntry.job_id == job_id,
                        TimeEntry.labor_activity_id == form.labor_activity_id.data).scalar() or 0
                existing_hours -= current_job_activity_hours

                total_hours = existing_hours + float(current_hours)

                print(f"DEBUG: Day {i} ({date_val}): current_hours={current_hours}, existing_hours={existing_hours}, total_hours={total_hours}")

                if total_hours > 12:
                    day_name = [
                        'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
                        'Saturday', 'Sunday'
                    ][i]
                    print(f"DEBUG: Validation failed - total_hours {total_hours} > 12 for {worker.name} on {day_name}")
                    flash(
                        f'Maximum 12 hours per day exceeded for {worker.name} on {day_name}. They already have {existing_hours:.1f} hours recorded for this day. The total would be {total_hours:.1f} hours.',
                        'danger')
                    # Show the error on the same page instead of redirecting
                    return render_template('foreman/enter_time.html',
                                         form=form,
                                         worker=worker,
                                         job=job,
                                         week_start=week_start,
                                         week_end=week_end,
                                         existing_entries=existing_entries,
                                         all_existing_entries=all_existing_entries)

        # After validation passes, delete any existing entries for this week with the same activity
        # This ensures we don't get duplicate entries if the foreman submits multiple times
        TimeEntry.query.filter(
            TimeEntry.user_id == user_id, TimeEntry.job_id == job_id,
            TimeEntry.labor_activity_id == form.labor_activity_id.data,
            TimeEntry.date >= dates[0], TimeEntry.date <= dates[6]).delete()

        # Now create new entries for days with hours > 0
        for i, date_val in enumerate(dates):
            # Convert None or empty string to 0 to avoid comparison errors
            hours_value = hours_values[i] if hours_values[i] not in [None, ''
                                                                     ] else 0
            if hours_value and float(hours_value) > 0:
                # Create a new entry
                entry = TimeEntry(
                    user_id=user_id,
                    job_id=job_id,
                    labor_activity_id=form.labor_activity_id.data,
                    date=date_val,
                    hours=float(hours_value),  # Use the converted value
                    notes=form.notes.data)
                db.session.add(entry)

        db.session.commit()
        flash(
            f'Time entries for {worker.name} on {job.job_code} successfully saved!',
            'success')
        # Pass the week_start to maintain the selected date when redirecting
        # Check if current user is admin and redirect appropriately
        if current_user.is_admin():
            return redirect(
                url_for('admin_review_time',
                        start_date=week_start.strftime('%Y-%m-%d')))
        else:
            return redirect(
                url_for('foreman_dashboard',
                        start_date=week_start.strftime('%m/%d/%Y')))

    # Initialize for template context
    existing_entries = []

    # Check if this is a GET request or if form failed validation
    if request.method == 'GET' or not form.validate():
        # Set all hours fields to 0 by default
        form.monday_hours.data = 0.0
        form.tuesday_hours.data = 0.0
        form.wednesday_hours.data = 0.0
        form.thursday_hours.data = 0.0
        form.friday_hours.data = 0.0
        form.saturday_hours.data = 0.0
        form.sunday_hours.data = 0.0

        # Load existing entries for this week with eager loading of labor_activity
        if form.labor_activity_id.data and form.labor_activity_id.data != 'ALL':
            # If specific labor activity is selected, get entries for that activity only
            existing_entries = TimeEntry.query.filter(
                TimeEntry.user_id == user_id, TimeEntry.job_id == job_id,
                TimeEntry.labor_activity_id == form.labor_activity_id.data,
                TimeEntry.date >= week_start,
                TimeEntry.date <= week_end).options(
                    db.joinedload(TimeEntry.labor_activity)).all()

            if existing_entries:
                # Create a dictionary to store hours by day index
                day_entries = {}
                for entry in existing_entries:
                    day_index = (entry.date - week_start).days
                    if 0 <= day_index <= 6:  # Make sure it's within the week
                        day_entries[day_index] = entry.hours

                # Map each day to the form field
                if 0 in day_entries:
                    form.monday_hours.data = day_entries[0]
                if 1 in day_entries:
                    form.tuesday_hours.data = day_entries[1]
                if 2 in day_entries:
                    form.wednesday_hours.data = day_entries[2]
                if 3 in day_entries:
                    form.thursday_hours.data = day_entries[3]
                if 4 in day_entries:
                    form.friday_hours.data = day_entries[4]
                if 5 in day_entries:
                    form.saturday_hours.data = day_entries[5]
                if 6 in day_entries:
                    form.sunday_hours.data = day_entries[6]

                # Populate notes field
                form.notes.data = existing_entries[0].notes
        else:
            # If no labor activity selected or "ALL" is selected, set default to "ALL"
            form.labor_activity_id.data = 'ALL'
            
            # For "ALL" view, get all entries but don't populate the form fields
            # The form will be handled by JavaScript to show totals across all activities
            existing_entries = TimeEntry.query.filter(
                TimeEntry.user_id == user_id, TimeEntry.job_id == job_id,
                TimeEntry.date >= week_start,
                TimeEntry.date <= week_end).options(
                    db.joinedload(TimeEntry.labor_activity)).all()

            if existing_entries:
                # Calculate total hours per day across all activities for "ALL" view
                daily_totals = {}
                for entry in existing_entries:
                    day_index = (entry.date - week_start).days
                    if 0 <= day_index <= 6:  # Make sure it's within the week
                        if day_index not in daily_totals:
                            daily_totals[day_index] = 0
                        daily_totals[day_index] += entry.hours

                # Map total hours to form fields for "ALL" view
                if 0 in daily_totals:
                    form.monday_hours.data = daily_totals[0]
                if 1 in daily_totals:
                    form.tuesday_hours.data = daily_totals[1]
                if 2 in daily_totals:
                    form.wednesday_hours.data = daily_totals[2]
                if 3 in daily_totals:
                    form.thursday_hours.data = daily_totals[3]
                if 4 in daily_totals:
                    form.friday_hours.data = daily_totals[4]
                if 5 in daily_totals:
                    form.saturday_hours.data = daily_totals[5]
                if 6 in daily_totals:
                    form.sunday_hours.data = daily_totals[6]

    return render_template('foreman/enter_time.html',
                           form=form,
                           worker=worker,
                           job=job,
                           week_start=week_start,
                           week_end=week_end,
                           existing_entries=existing_entries,
                           all_existing_entries=all_existing_entries)


@app.route('/foreman/approve/<int:job_id>/<int:user_id>',
           methods=['GET', 'POST'])
@login_required
@foreman_or_admin_required
def approve_timesheet(job_id, user_id):
    # Get the worker and job
    worker = User.query.get_or_404(user_id)
    job = Job.query.get_or_404(job_id)

    form = ApprovalForm()
    # Populate the form dropdown options
    form.job_id.choices = [(job.id, f"{job.job_code} - {job.description}")]
    form.user_id.choices = [(worker.id, worker.name)]
    form.job_id.data = job_id
    form.user_id.data = user_id

    # Get start_date from URL if provided
    url_start_date = request.args.get('start_date')

    # Default to current week if no week start provided
    if not form.week_start.data:
        if url_start_date:
            # Use the start_date from URL with robust parsing
            try:
                # Try both common formats: %m/%d/%Y and %Y-%m-%d
                if '/' in url_start_date:
                    parsed_date = datetime.strptime(url_start_date,
                                                    '%m/%d/%Y').date()
                elif '-' in url_start_date:
                    parsed_date = datetime.strptime(url_start_date,
                                                    '%Y-%m-%d').date()
                else:
                    print(
                        f"WARNING: Invalid date format in start_date: {url_start_date}"
                    )
                    parsed_date = None

                # Always align to Monday
                if parsed_date:
                    form.week_start.data = get_week_start(parsed_date)
                    print(
                        f"DEBUG: Aligned date {parsed_date} to Monday: {form.week_start.data}"
                    )
                else:
                    # Fall back to current week
                    today = date.today()
                    form.week_start.data = get_week_start(today)
            except ValueError as e:
                print(
                    f"WARNING: Error parsing start_date '{url_start_date}': {str(e)}"
                )
                # Fall back to current week
                today = date.today()
                form.week_start.data = get_week_start(today)
        else:
            today = date.today()
            form.week_start.data = get_week_start(today)

    week_start = form.week_start.data
    week_end = week_start + timedelta(days=6)

    # Check if this week is already approved
    existing_approval = WeeklyApprovalLock.query.filter_by(
        user_id=user_id, job_id=job_id, week_start=week_start).first()

    if existing_approval:
        flash(
            f'This week was already approved by {existing_approval.approver.name} on {existing_approval.approved_at.strftime("%m/%d/%Y %H:%M")}',
            'warning')
        # Pass the week_start to maintain the selected date when redirecting
        # Check if current user is admin and redirect appropriately
        if current_user.is_admin():
            return redirect(
                url_for('admin_review_time',
                        start_date=week_start.strftime('%Y-%m-%d')))
        else:
            return redirect(
                url_for('foreman_dashboard',
                        start_date=week_start.strftime('%m/%d/%Y')))

    # Get all time entries for the week
    entries = TimeEntry.query.filter(
        TimeEntry.user_id == user_id, TimeEntry.job_id == job_id,
        TimeEntry.date >= week_start, TimeEntry.date
        <= week_end).order_by(TimeEntry.date).all()

    # Check if weekdays (Monday through Friday) have entries
    days_with_entries = set(entry.date for entry in entries)
    weekdays = {week_start + timedelta(days=i) for i in range(5)}  # Only Monday through Friday
    missing_days = weekdays - days_with_entries

    if form.validate_on_submit():
        # Show a notification about missing days, but still allow approval
        if missing_days:
            missing_day_list = ", ".join(
                [d.strftime('%a %m/%d') for d in sorted(missing_days)])
            flash(f'Note: Worker has no time entries for: {missing_day_list}',
                  'warning')

        # Approve all time entries
        for entry in entries:
            entry.approved = True
            entry.approved_by = current_user.id
            entry.approved_at = datetime.utcnow()

        # Create weekly approval lock
        approval = WeeklyApprovalLock(user_id=user_id,
                                      job_id=job_id,
                                      week_start=week_start,
                                      approved_by=current_user.id)
        db.session.add(approval)
        db.session.commit()

        flash(
            f'Timesheet for {worker.name} on job {job.job_code} successfully approved!',
            'success')
        # Pass the week_start to maintain the selected date when redirecting
        # Check if current user is admin and redirect appropriately
        if current_user.is_admin():
            return redirect(
                url_for('admin_review_time',
                        start_date=week_start.strftime('%Y-%m-%d')))
        else:
            return redirect(
                url_for('foreman_dashboard',
                        start_date=week_start.strftime('%m/%d/%Y')))

    # Group entries by date for display - convert weekdays to sorted list for proper chronological order
    weekdays_sorted = sorted(weekdays)  # Sort Monday through Friday chronologically
    entries_by_date = {}
    
    # First, initialize with weekdays in chronological order
    for day in weekdays_sorted:
        entries_by_date[day] = []

    # Then add any entries that fall outside the expected week range
    for entry in entries:
        if entry.date in entries_by_date:
            entries_by_date[entry.date].append(entry)
        else:
            # Handle entries that fall outside the expected week range
            entries_by_date[entry.date] = [entry]
    
    # Create ordered dictionary to ensure chronological display in template
    from collections import OrderedDict
    entries_by_date_ordered = OrderedDict()
    
    # Add weekdays first in chronological order
    for day in weekdays_sorted:
        if day in entries_by_date:
            entries_by_date_ordered[day] = entries_by_date[day]
    
    # Add any other dates in chronological order
    other_dates = sorted([d for d in entries_by_date.keys() if d not in weekdays_sorted])
    for day in other_dates:
        entries_by_date_ordered[day] = entries_by_date[day]

    # Calculate daily and weekly totals
    daily_totals = {
        day: sum(entry.hours for entry in day_entries)
        for day, day_entries in entries_by_date.items()
    }
    weekly_total = sum(daily_totals.values())

    return render_template('foreman/approve.html',
                           form=form,
                           worker=worker,
                           job=job,
                           entries_by_date=entries_by_date_ordered,
                           daily_totals=daily_totals,
                           weekly_total=weekly_total,
                           missing_days=missing_days,
                           week_start=week_start,
                           week_end=week_end)


# Admin routes
@app.route('/admin/review-time')
@login_required
@admin_required
def admin_review_time():
    """Admin time review page - similar to foreman dashboard but for unassigned jobs"""
    # Get date range parameters from query string
    start_date_str = request.args.get('start_date')
    week_offset_str = request.args.get('week_offset', '0')
    show_all_jobs = request.args.get('show_all_jobs', 'false').lower() == 'true'

    try:
        week_offset = int(week_offset_str)
    except ValueError:
        week_offset = 0

    # Initialize default values
    today = date.today()
    current_monday = get_week_start(today)
    start_date = current_monday + timedelta(weeks=week_offset)
    end_date = start_date + timedelta(days=6)

    # If a specific start_date is provided, parse it and override the default
    if start_date_str:
        try:
            if '/' in start_date_str:
                parsed_date = datetime.strptime(start_date_str, '%m/%d/%Y').date()
            elif '-' in start_date_str:
                parsed_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            else:
                parsed_date = None

            if parsed_date:
                # Align to Monday and override defaults
                monday_date = get_week_start(parsed_date)
                start_date = monday_date
                end_date = monday_date + timedelta(days=6)
                print(f"DEBUG: Admin review time - using provided date: {start_date} to {end_date}")
        except ValueError:
            # If parsing fails, keep the default values
            print(f"DEBUG: Admin review time - date parsing failed, using defaults: {start_date} to {end_date}")

    print(f"DEBUG: Admin review time - final date range: {start_date} to {end_date}, week_offset: {week_offset}")

    # Query for time entries within the date range
    # Use explicit joins to ensure we get the relationships loaded properly
    entries_query = TimeEntry.query.join(Job, TimeEntry.job_id == Job.id).join(User, TimeEntry.user_id == User.id).filter(
        TimeEntry.date >= start_date,
        TimeEntry.date <= end_date
    )

    # Apply job filter based on toggle
    if not show_all_jobs:
        # Default: Show only unassigned jobs (foreman_id is None)
        entries_query = entries_query.filter(Job.foreman_id.is_(None))
        print(f"DEBUG: Admin review time - filtering for unassigned jobs only")
    else:
        print(f"DEBUG: Admin review time - showing all jobs")

    # Print the SQL query for debugging
    print(f"DEBUG: SQL Query: {str(entries_query.statement.compile(compile_kwargs={'literal_binds': True}))}")

    # Get all entries and group by job and user
    entries = entries_query.order_by(TimeEntry.date, Job.job_code, User.name).all()
    print(f"DEBUG: Admin review time - found {len(entries)} time entries for date range {start_date} to {end_date}")
    
    # Debug: Show first few entries
    for i, entry in enumerate(entries[:5]):
        print(f"DEBUG: Entry {i+1}: Job {entry.job.job_code} (foreman_id={entry.job.foreman_id}), Worker {entry.user.name}, Date {entry.date}, Hours {entry.hours}")
        
    # Also check what jobs exist in the date range
    all_jobs_in_range = Job.query.join(TimeEntry, Job.id == TimeEntry.job_id).filter(
        TimeEntry.date >= start_date,
        TimeEntry.date <= end_date
    ).distinct().all()
    print(f"DEBUG: Jobs with time entries in date range:")
    for job in all_jobs_in_range:
        print(f"DEBUG: Job {job.job_code} - foreman_id: {job.foreman_id}")

    # Use the same data structure as foreman dashboard
    # Get all jobs that have time entries in the date range
    jobs_with_entries = Job.query.join(TimeEntry, Job.id == TimeEntry.job_id).filter(
        TimeEntry.date >= start_date,
        TimeEntry.date <= end_date
    ).distinct()

    # Apply job filter based on toggle
    if not show_all_jobs:
        # Default: Show only unassigned jobs (foreman_id is None)
        jobs_with_entries = jobs_with_entries.filter(Job.foreman_id.is_(None))

    jobs = jobs_with_entries.all()

    # For each job, get all workers with time entries (same structure as foreman dashboard)
    job_data = []
    for job in jobs:
        # Get unique workers who submitted time for this job in the date range
        workers_query = db.session.query(User).join(TimeEntry, User.id == TimeEntry.user_id).\
            filter(
                TimeEntry.job_id == job.id,
                TimeEntry.date >= start_date,
                TimeEntry.date <= end_date,
                User.role == 'worker'
            ).distinct()

        workers = workers_query.all()

        # Get weekly approval status for each worker (same as foreman dashboard)
        workers_data = []
        for worker in workers:
            # Check if the week is approved for this worker/job
            is_approved = WeeklyApprovalLock.query.filter_by(
                user_id=worker.id, job_id=job.id,
                week_start=start_date).first() is not None

            # Count total hours for the week
            total_hours = db.session.query(db.func.sum(TimeEntry.hours)).\
                filter(
                    TimeEntry.user_id == worker.id,
                    TimeEntry.job_id == job.id,
                    TimeEntry.date >= start_date,
                    TimeEntry.date <= end_date
                ).scalar() or 0

            # Check if all 7 days of the week have entries
            days_with_entries = db.session.query(TimeEntry.date).\
                filter(
                    TimeEntry.user_id == worker.id,
                    TimeEntry.job_id == job.id,
                    TimeEntry.date >= start_date,
                    TimeEntry.date <= end_date
                ).distinct().count()

            # Check if worker has any entries with notes for this job and week
            has_notes = db.session.query(TimeEntry).\
                filter(
                    TimeEntry.user_id == worker.id,
                    TimeEntry.job_id == job.id,
                    TimeEntry.date >= start_date,
                    TimeEntry.date <= end_date,
                    TimeEntry.notes.isnot(None),
                    db.func.trim(TimeEntry.notes) != ''
                ).first() is not None

            workers_data.append({
                'worker': worker,
                'is_approved': is_approved,
                'total_hours': total_hours,
                'days_with_entries': days_with_entries,
                'has_all_days': days_with_entries >= 5,  # Standard work week is 5 days
                'has_notes': has_notes  # Flag to indicate if worker has any notes
            })

        # Add is_unassigned flag for template
        job_item = {
            'job': job, 
            'workers': workers_data,
            'is_unassigned': job.foreman_id is None
        }
        job_data.append(job_item)

    return render_template('admin/review_time.html',
                           job_data=job_data,
                           start_date=start_date,
                           end_date=end_date,
                           show_all_jobs=show_all_jobs)


@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    # Get counts for dashboard widgets
    active_jobs_count = Job.query.filter_by(status='active').count()
    total_workers = User.query.filter_by(role='worker').count()

    # Get recent time approvals
    recent_approvals = WeeklyApprovalLock.query.order_by(
        WeeklyApprovalLock.approved_at.desc()).limit(10).all()

    # Get start_date from URL if provided for week navigation
    url_start_date = request.args.get('start_date')

    if url_start_date:
        # Parse the start_date from URL with robust parsing
        try:
            # Try both common formats: %m/%d/%Y and %Y-%m-%d
            if '/' in url_start_date:
                parsed_date = datetime.strptime(url_start_date,
                                                '%m/%d/%Y').date()
            elif '-' in url_start_date:
                parsed_date = datetime.strptime(url_start_date,
                                                '%Y-%m-%d').date()
            else:
                print(
                    f"WARNING: Invalid date format in start_date: {url_start_date}"
                )
                parsed_date = None

            # Always align to Monday and get the week range
            if parsed_date:
                monday_date = get_week_start(parsed_date)
                start_date = monday_date
                end_date = monday_date + timedelta(days=6)
                print(
                    f"DEBUG: Admin dashboard - using provided date: {start_date} to {end_date}"
                )
            else:
                # Fall back to current week if parse fails
                start_date, end_date = get_week_range_for_offset(0)
                print(
                    f"DEBUG: Admin dashboard - date parse failed, using current week: {start_date} to {end_date}"
                )
        except ValueError as e:
            print(f"ERROR: Date parsing error: {e}")
            # Fall back to current week
            start_date, end_date = get_week_range_for_offset(0)
            print(
                f"DEBUG: Admin dashboard - date parse error, using current week: {start_date} to {end_date}"
            )
    else:
        # No date provided, use current week
        start_date, end_date = get_week_range_for_offset(0)
        print(
            f"DEBUG: Admin dashboard - calculating for current week: {start_date} to {end_date}"
        )

    weekly_hours = db.session.query(db.func.sum(TimeEntry.hours)).\
        filter(
            TimeEntry.date >= start_date,
            TimeEntry.date <= end_date
        ).scalar() or 0

    # Get hours by job for the current week (for chart)
    job_hours_query = db.session.query(
        Job.job_code,
        db.func.sum(TimeEntry.hours).label('total_hours')).join(
            TimeEntry, Job.id == TimeEntry.job_id).filter(
                TimeEntry.date >= start_date, TimeEntry.date
                <= end_date).group_by(Job.job_code).all()

    # Convert to JSON-friendly format
    job_hours = []
    if job_hours_query:
        job_labels = [job.job_code for job in job_hours_query]
        job_values = [float(job.total_hours) for job in job_hours_query]
        job_hours = list(zip(job_labels, job_values))

    # Get hours by trade category for the current week (for chart)
    trade_hours_query = db.session.query(
        LaborActivity.trade_category,
        db.func.sum(TimeEntry.hours).label('total_hours')).join(
            TimeEntry, LaborActivity.id == TimeEntry.labor_activity_id).filter(
                TimeEntry.date >= start_date, TimeEntry.date
                <= end_date).group_by(LaborActivity.trade_category).all()

    # Convert to JSON-friendly format
    trade_hours = []
    if trade_hours_query:
        trade_labels = [
            trade.trade_category.capitalize() for trade in trade_hours_query
        ]
        trade_values = [
            float(trade.total_hours) for trade in trade_hours_query
        ]
        trade_hours = list(zip(trade_labels, trade_values))

    return render_template('admin/dashboard.html',
                           active_jobs_count=active_jobs_count,
                           total_workers=total_workers,
                           weekly_hours=weekly_hours,
                           recent_approvals=recent_approvals,
                           job_hours=job_hours,
                           trade_hours=trade_hours,
                           start_date=start_date,
                           end_date=end_date)


@app.route('/admin/job-workers', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_job_workers():
    """Manage worker assignments to jobs"""
    form = JobWorkersForm()

    # If form is submitted and valid, update worker assignments
    if form.validate_on_submit():
        job_id = form.job_id.data
        job = Job.query.get_or_404(job_id)
        selected_worker_ids = form.workers.data

        # Convert worker IDs to integers if they're not already
        if selected_worker_ids:
            selected_worker_ids = [
                int(worker_id) for worker_id in selected_worker_ids
            ]
        else:
            selected_worker_ids = []

        # A different approach - work with the User objects directly
        # First, clear existing assignments using the SQLAlchemy relationship
        # The relationship has a lazy='dynamic' setting, so we need to use all() to get the actual workers
        current_workers = job.assigned_workers.all()
        for worker in current_workers:
            # Remove the job from the worker's assigned_jobs
            worker.assigned_jobs.remove(job)
        
        # Now add the new assignments
        selected_workers = User.query.filter(User.id.in_(selected_worker_ids)).all()
        print(f"DEBUG: Selected worker IDs: {selected_worker_ids}")
        print(f"DEBUG: Found {len(selected_workers)} workers")
        
        for worker in selected_workers:
            # Add the job to the worker's assigned_jobs
            worker.assigned_jobs.append(job)
            print(f"DEBUG: Assigning worker {worker.id} to job {job.id}")

        try:
            db.session.commit()
            
            # Verify assignments after commit
            job = Job.query.get(job_id)  # Refresh job from database
            print(f"DEBUG: After commit - job has {job.assigned_workers.count()} workers")
            
            flash(
                f"Worker assignments for job '{job.job_code}' updated successfully!",
                'success')
        except Exception as e:
            db.session.rollback()
            print(f"DEBUG: Database error: {str(e)}")
            flash(f"Error updating worker assignments: {str(e)}", 'danger')

        return redirect(url_for('manage_job_workers', job_id=job_id))

    # If job_id is provided in query params, pre-populate the form
    selected_job_id = request.args.get('job_id', type=int)
    if selected_job_id:
        job = Job.query.get_or_404(selected_job_id)
        form.job_id.data = selected_job_id

        # Use the SQLAlchemy relationship to get assigned workers
        # This is more consistent with the SQLAlchemy ORM pattern
        form.workers.data = [worker.id for worker in job.assigned_workers]

    return render_template('admin/job_workers.html',
                           form=form,
                           title="Manage Worker Assignments")


@app.route('/api/job/<int:job_id>/assigned-users')
@login_required
@admin_required
def get_job_assigned_users(job_id):
    """API endpoint to get users assigned to a specific job"""
    try:
        job = Job.query.get_or_404(job_id)
        
        # Get assigned users
        assigned_users = []
        for user in job.assigned_workers.order_by(User.name):
            assigned_users.append({
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'role': user.role
            })
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'job_code': job.job_code,
            'users': assigned_users
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/admin/jobs', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_jobs():
    form = JobForm()

    # Custom validation for checkbox trades
    selected_trade_ids = request.form.getlist('trades')
    if request.method == 'POST' and not selected_trade_ids:
        form.trades.errors.append("At least one trade must be selected")
    
    if form.validate_on_submit() and selected_trade_ids:
        # Check if we're editing an existing job
        job_id = request.args.get('edit')

        # Get status_filter to preserve it across redirects
        status_filter = request.args.get('status_filter', 'active')

        if job_id:
            job = Job.query.get_or_404(job_id)
            job.job_code = form.job_code.data
            job.description = form.description.data
            job.location = form.location.data
            # Save latitude and longitude from the form
            job.latitude = form.latitude.data
            job.longitude = form.longitude.data
            job.status = form.status.data
            job.trade_type = form.trade_type.data
            # Handle foreman assignment
            job.foreman_id = form.foreman_id.data if form.foreman_id.data else None
            
            # Update job trades (many-to-many)
            from models import Trade
            # Clear existing trades properly
            job.trades = []
            
            # Get trades from checkbox array
            selected_trade_ids = request.form.getlist('trades')
            for trade_id_str in selected_trade_ids:
                try:
                    trade_id = int(trade_id_str)
                    trade = Trade.query.filter_by(id=trade_id, is_active=True).first()
                    if trade:
                        job.trades.append(trade)
                except (ValueError, TypeError):
                    continue  # Skip invalid trade IDs
            
            flash('Job updated successfully!', 'success')
        else:
            # Create new job
            job = Job(job_code=form.job_code.data,
                      description=form.description.data,
                      location=form.location.data,
                      latitude=form.latitude.data,
                      longitude=form.longitude.data,
                      status=form.status.data,
                      trade_type=form.trade_type.data,
                      foreman_id=form.foreman_id.data if form.foreman_id.data else None)
            db.session.add(job)
            db.session.flush()  # Get the job ID

            # Add job trades (many-to-many)
            from models import Trade
            # Get trades from checkbox array
            selected_trade_ids = request.form.getlist('trades')
            for trade_id_str in selected_trade_ids:
                try:
                    trade_id = int(trade_id_str)
                    trade = Trade.query.filter_by(id=trade_id, is_active=True).first()
                    if trade:
                        job.trades.append(trade)
                except (ValueError, TypeError):
                    continue  # Skip invalid trade IDs

            # Assign all workers to this new job
            workers = User.query.filter_by(role='worker').all()
            for worker in workers:
                job.assigned_workers.append(worker)

            flash('New job created successfully!', 'success')

        db.session.commit()
        # Pass the status_filter back to the redirect to maintain the selected filter
        return redirect(url_for('manage_jobs', status_filter=status_filter))

    # Check if we're editing a job
    job_id = request.args.get('edit')
    if job_id:
        job = Job.query.get_or_404(job_id)
        form.job_code.data = job.job_code
        form.description.data = job.description
        form.location.data = job.location
        # Load latitude and longitude for the map preview
        form.latitude.data = job.latitude
        form.longitude.data = job.longitude
        form.status.data = job.status
        form.trade_type.data = job.trade_type
        form.foreman_id.data = job.foreman_id if job.foreman_id else ''
        # Load current trades for editing
        form.trades.data = [trade.id for trade in job.trades]

    # Get jobs filtered by status if specified
    status_filter = request.args.get('status_filter', 'active')

    # Build the query based on the filter
    jobs_query = Job.query

    if status_filter == 'active':
        jobs_query = jobs_query.filter(Job.status == 'active')
    elif status_filter == 'complete':
        jobs_query = jobs_query.filter(Job.status == 'complete')
    # For 'all', no filter is applied

    # Get the filtered jobs ordered by creation date
    jobs = jobs_query.order_by(Job.created_at.desc()).all()

    # Get the job being edited if applicable
    edit_job = None
    if job_id:
        edit_job = Job.query.get_or_404(job_id)

    return render_template('admin/jobs.html',
                           form=form,
                           jobs=jobs,
                           editing=bool(job_id),
                           edit_job=edit_job,
                           status_filter=status_filter)


@app.route('/admin/jobs/delete/<int:job_id>', methods=['POST'])
@login_required
@admin_required
def delete_job(job_id):
    job = Job.query.get_or_404(job_id)

    # Get status_filter to preserve it across redirects
    status_filter = request.args.get('status_filter', 'active')

    # Check if there are any time entries associated with this job
    time_entries = TimeEntry.query.filter_by(job_id=job_id).count()

    if time_entries > 0:
        flash(
            f'Cannot delete job "{job.job_code}". It has {time_entries} time entries associated with it. Mark it as "Complete" instead.',
            'danger')
        return redirect(url_for('manage_jobs', status_filter=status_filter))

    # Check if there are any weekly approval locks for this job
    approvals = WeeklyApprovalLock.query.filter_by(job_id=job_id).count()

    if approvals > 0:
        flash(
            f'Cannot delete job "{job.job_code}". It has {approvals} weekly approvals associated with it. Mark it as "Complete" instead.',
            'danger')
        return redirect(url_for('manage_jobs', status_filter=status_filter))

    # If no time entries or approvals, safe to delete
    job_code = job.job_code  # Store for the flash message
    db.session.delete(job)
    db.session.commit()

    flash(f'Job "{job_code}" has been deleted successfully.', 'success')
    return redirect(url_for('manage_jobs', status_filter=status_filter))


@app.route('/admin/activities', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_activities():
    # Initialize forms
    activity_form = LaborActivityForm()
    trade_form = TradeForm()
    editing_trade = request.args.get('edit_trade')

    # Get active trades for both dropdowns
    active_trades = Trade.query.filter_by(is_active=True).order_by(
        Trade.name).all()

    # 1. Dynamically populate trade_id choices from the database - only active trades
    activity_form.trade_id.choices = [(0, '-- Select Trade --')] + [
        (trade.id, trade.name) for trade in active_trades
    ]

    # 2. Dynamically populate trade_category choices based on active trades
    # First, get unique categories from active trades, falling back to defaults if none found
    unique_categories = set(trade.name.lower() for trade in active_trades)
    if not unique_categories:
        # Fallback categories if no trades exist
        unique_categories = {
            'drywall', 'electrical', 'plumbing', 'carpentry', 'painting',
            'masonry', 'other'
        }

    # Always include "other" category
    if 'other' not in unique_categories:
        unique_categories.add('other')

    # Set the choices for trade_category
    activity_form.trade_category.choices = [
        (cat, cat.capitalize()) for cat in sorted(unique_categories)
    ]

    # Important: Choices must be populated *before* validation for POST requests

    # Handle activity form submission
    if 'submit' in request.form:
        # WTForms validation needs choices set properly before validation
        # This ensures any POSTed trade_id is considered valid during validation
        if activity_form.validate():
            # Check if we're editing an existing activity
            activity_id = request.args.get('edit')

            if activity_id:
                activity = LaborActivity.query.get_or_404(activity_id)
                activity.name = activity_form.name.data
                activity.trade_category = activity_form.trade_category.data
                activity.is_active = activity_form.is_active.data

                # If trade_id is provided, associate with the trade
                if activity_form.trade_id.data and activity_form.trade_id.data > 0:
                    activity.trade_id = activity_form.trade_id.data

                flash('Labor activity updated successfully!', 'success')
            else:
                # Create new activity
                activity = LaborActivity(
                    name=activity_form.name.data,
                    trade_category=activity_form.trade_category.data,
                    is_active=activity_form.is_active.data)

                # If trade_id is provided, associate with the trade
                if activity_form.trade_id.data and activity_form.trade_id.data > 0:
                    activity.trade_id = activity_form.trade_id.data

                db.session.add(activity)
                flash('New labor activity created successfully!', 'success')

            db.session.commit()
            return redirect(url_for('manage_activities'))

    # Handle trade form submission
    if 'submit_trade' in request.form and trade_form.validate():
        if editing_trade:
            trade = Trade.query.get_or_404(editing_trade)
            trade.name = trade_form.name.data
            trade.is_active = trade_form.is_active.data
            flash('Trade updated successfully!', 'success')
        else:
            trade = Trade(name=trade_form.name.data,
                          is_active=trade_form.is_active.data)
            db.session.add(trade)
            flash('New trade created successfully!', 'success')

        db.session.commit()
        return redirect(url_for('manage_activities'))

    # Check if we're editing an activity
    activity_id = request.args.get('edit')
    if activity_id:
        activity = LaborActivity.query.get_or_404(activity_id)
        activity_form.name.data = activity.name
        activity_form.trade_category.data = activity.trade_category
        activity_form.is_active.data = activity.is_active
        if activity.trade_id:
            activity_form.trade_id.data = activity.trade_id

    # Check if we're editing a trade
    if editing_trade:
        trade = Trade.query.get_or_404(editing_trade)
        trade_form.name.data = trade.name
        trade_form.is_active.data = trade.is_active

    # Get active trades for display
    active_trades = Trade.query.filter_by(is_active=True).order_by(
        Trade.name).all()

    # Get disabled trades for a separate display section
    disabled_trades = Trade.query.filter_by(is_active=False).order_by(
        Trade.name).all()

    # Get activities grouped by trade category - only active activities
    activities_by_trade = {}
    activities = LaborActivity.query.filter_by(is_active=True).order_by(
        LaborActivity.trade_category, LaborActivity.name).all()

    for activity in activities:
        if activity.trade_category not in activities_by_trade:
            activities_by_trade[activity.trade_category] = []
        activities_by_trade[activity.trade_category].append(activity)

    return render_template('admin/activities.html',
                           activity_form=activity_form,
                           trade_form=trade_form,
                           activities_by_trade=activities_by_trade,
                           trades=active_trades,
                           disabled_trades=disabled_trades,
                           editing_activity=bool(activity_id),
                           editing_trade=bool(editing_trade))


@app.route('/admin/toggle_trade/<int:id>', methods=['POST'])
@login_required
@admin_required
def toggle_trade(id):
    trade = Trade.query.get_or_404(id)
    trade.is_active = not trade.is_active

    # Optionally, toggle all associated labor activities as well
    if not trade.is_active:
        for activity in trade.labor_activities:
            activity.is_active = False

    db.session.commit()

    flash(
        f"Trade '{trade.name}' {'enabled' if trade.is_active else 'disabled'} successfully.",
        "success")
    return redirect(url_for('manage_activities'))


@app.route('/admin/toggle_activity/<int:id>', methods=['POST'])
@login_required
@admin_required
def toggle_activity(id):
    activity = LaborActivity.query.get_or_404(id)
    activity.is_active = not activity.is_active
    db.session.commit()

    flash(
        f"Activity '{activity.name}' {'enabled' if activity.is_active else 'disabled'} successfully.",
        "success")
    return redirect(url_for('manage_activities'))


@app.route('/admin/users', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_users():
    form = UserManagementForm()

    if form.validate_on_submit():
        # Check if we're editing an existing user
        user_id = request.args.get('edit')

        if user_id:
            user = User.query.get_or_404(user_id)
            user.name = form.name.data
            user.email = form.email.data
            user.role = form.role.data
            # Set the use_clock_in field from the form
            user.use_clock_in = form.use_clock_in.data
            # Set the burden_rate field from the form
            user.burden_rate = form.burden_rate.data

            # Update qualified trades (many-to-many)
            from models import Trade
            # Clear existing trades properly
            user.qualified_trades = []
            
            # Get qualified trades from checkbox array
            selected_trade_ids = request.form.getlist('qualified_trades')
            for trade_id_str in selected_trade_ids:
                try:
                    trade_id = int(trade_id_str)
                    trade = Trade.query.filter_by(id=trade_id, is_active=True).first()
                    if trade:
                        user.qualified_trades.append(trade)
                except (ValueError, TypeError):
                    continue  # Skip invalid trade IDs

            # Log the change for debugging
            print(
                f"DEBUG: Updated user {user.name} (ID: {user.id}), use_clock_in set to: {user.use_clock_in}, burden_rate set to: {user.burden_rate}"
            )

            # Update password if provided
            if form.password.data:
                user.set_password(form.password.data)

            flash('User updated successfully!', 'success')
            db.session.commit()
        else:
            # This is a new user being created
            user = User(
                name=form.name.data,
                email=form.email.data,
                role=form.role.data,
                use_clock_in=form.use_clock_in.data,  # Add the use_clock_in field
                burden_rate=form.burden_rate.data  # Add the burden_rate field
            )

            # Log the creation for debugging
            print(
                f"DEBUG: Creating new user {form.name.data}, use_clock_in set to: {form.use_clock_in.data}, burden_rate set to: {form.burden_rate.data}"
            )

            # Set the password
            if form.password.data:
                user.set_password(form.password.data)
            else:
                # Default password is required
                flash('Password is required for new users', 'danger')
                users = User.query.order_by(User.role, User.name).all()
                return render_template('admin/users.html',
                                       form=form,
                                       users=users,
                                       editing=False,
                                       new_user=True)

            # Try to add the new user
            try:
                db.session.add(user)
                db.session.flush()  # Get the user ID
                
                # Add qualified trades for new user
                from models import Trade
                # Get qualified trades from checkbox array
                selected_trade_ids = request.form.getlist('qualified_trades')
                for trade_id_str in selected_trade_ids:
                    try:
                        trade_id = int(trade_id_str)
                        trade = Trade.query.filter_by(id=trade_id, is_active=True).first()
                        if trade:
                            user.qualified_trades.append(trade)
                    except (ValueError, TypeError):
                        continue  # Skip invalid trade IDs
                
                db.session.commit()
                flash('New user added successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding user: {str(e)}', 'danger')

        return redirect(url_for('manage_users'))

    # Check if we're editing a user or if form validation failed
    user_id = request.args.get('edit')
    new_user = request.args.get('new') == 'true' or (request.method == 'POST' and form.errors)

    if user_id:
        # Editing existing user
        user = User.query.get_or_404(user_id)
        form.name.data = user.name
        form.email.data = user.email
        form.role.data = user.role
        form.use_clock_in.data = user.use_clock_in  # Load the current use_clock_in setting
        form.burden_rate.data = user.burden_rate  # Load the current burden_rate setting
        # Load current qualified trades for editing
        form.qualified_trades.data = [trade.id for trade in user.qualified_trades]
        print(
            f"DEBUG: Editing user {user.name} (ID: {user.id}), current use_clock_in = {user.use_clock_in}, current burden_rate = {user.burden_rate}"
        )
        editing = True
        editing_user = user
    else:
        # Not editing (either viewing or adding new)
        editing = False
        editing_user = None

    # Get all users for display
    users = User.query.order_by(User.role, User.name).all()

    return render_template('admin/users.html',
                           form=form,
                           users=users,
                           editing=editing,
                           editing_user=editing_user,
                           new_user=new_user)


@app.route('/admin/reports', methods=['GET', 'POST'])
@login_required
@admin_required
def generate_reports():
    form = ReportForm()

    if form.validate_on_submit():
        # Check if this is a preview request
        is_preview = request.form.get('preview') == 'true'
        
        # Get form data
        report_type = form.report_type.data
        start_date = form.start_date.data
        end_date = form.end_date.data
        job_id = form.job_id.data if form.job_id.data != 0 else None
        user_id = form.user_id.data if form.user_id.data != 0 else None
        report_format = form.format.data

        # Build the base query - different for device audit logs
        if report_type == 'device_audit':
            from models import DeviceLog
            query = db.session.query(
                DeviceLog.ts.label('timestamp'), 
                User.name.label('employee_name'),
                DeviceLog.action,
                DeviceLog.device_id,
                DeviceLog.lat.label('latitude'),
                DeviceLog.lng.label('longitude'),
                DeviceLog.ua.label('user_agent')
            ).join(User, DeviceLog.user_id == User.id).filter(
                DeviceLog.ts >= start_date,
                DeviceLog.ts <= end_date + timedelta(days=1)  # Include full end date
            )
        elif report_type == 'job_cost':
            query = db.session.query(
                TimeEntry.id, TimeEntry.date, TimeEntry.hours, TimeEntry.approved,
                User.name.label('worker_name'), User.burden_rate, Job.job_code,
                Job.description.label('job_description'),
                LaborActivity.name.label('activity'),
                LaborActivity.trade_category).join(
                    User, TimeEntry.user_id == User.id).join(
                        Job, TimeEntry.job_id == Job.id).join(
                            LaborActivity, TimeEntry.labor_activity_id ==
                            LaborActivity.id).filter(TimeEntry.date >= start_date,
                                                     TimeEntry.date <= end_date)
        else:
            query = db.session.query(
                TimeEntry.date, TimeEntry.hours, TimeEntry.approved,
                User.name.label('worker_name'), 
                Job.job_code, Job.description.label('job_description'),
                LaborActivity.name.label('activity'),
                LaborActivity.trade_category).join(
                    User, TimeEntry.user_id == User.id).join(
                        Job, TimeEntry.job_id == Job.id).join(
                            LaborActivity, TimeEntry.labor_activity_id ==
                            LaborActivity.id).filter(TimeEntry.date >= start_date,
                                                     TimeEntry.date <= end_date)

        # Apply filters
        if report_type == 'device_audit':
            # For device audit, user_id filter applies to DeviceLog.user_id
            if user_id:
                query = query.filter(DeviceLog.user_id == user_id)
        else:
            # For other reports, apply standard TimeEntry filters
            if job_id:
                query = query.filter(TimeEntry.job_id == job_id)

            if user_id:
                query = query.filter(TimeEntry.user_id == user_id)

        # Order the results
        if report_type == 'device_audit':
            query = query.order_by(DeviceLog.ts.desc())  # Most recent first
        elif report_type == 'payroll':
            query = query.order_by(User.name, TimeEntry.date)
        elif report_type == 'job_labor':
            query = query.order_by(Job.job_code, TimeEntry.date)
        elif report_type == 'job_cost':
            query = query.order_by(Job.job_code, User.name, TimeEntry.date)
        else:  # employee_hours
            query = query.order_by(TimeEntry.date, User.name)

        # Execute the query
        results = query.all()

        # Create pandas dataframe from results
        if report_type == 'device_audit':
            columns = [
                'timestamp', 'employee_name', 'action', 'device_id', 
                'latitude', 'longitude', 'user_agent'
            ]
        elif report_type == 'job_cost':
            columns = [
                'id', 'date', 'hours', 'approved', 'worker_name', 'burden_rate', 'job_code',
                'job_description', 'activity', 'trade_category'
            ]
        else:
            columns = [
                'date', 'hours', 'approved', 'worker_name', 'job_code',
                'job_description', 'activity', 'trade_category'
            ]
        df = pd.DataFrame(results, columns=columns)

        # For job cost reports, add cost calculations
        if report_type == 'job_cost':
            # Calculate total cost for each row (hours * burden_rate)
            df['total_cost'] = df.apply(lambda row: 
                float(row['hours']) * float(row['burden_rate']) if row['burden_rate'] else 0.0, axis=1)
            
            # Add formatted columns for display
            df['burden_rate_formatted'] = df['burden_rate'].apply(lambda x: f"${float(x):,.2f}" if x else "N/A")
            df['total_cost_formatted'] = df['total_cost'].apply(lambda x: f"${x:,.2f}")

        # Convert DataFrame to list of dictionaries for report generation
        data_dicts = df.to_dict('records')

        # Get common info for both formats
        report_titles = {
            'payroll': 'Payroll Report',
            'job_labor': 'Job Labor Report',
            'employee_hours': 'Employee Hours Report',
            'job_cost': 'Job Cost Report',
            'device_audit': 'Device Audit Log'
        }
        report_title = f"{report_titles.get(report_type, 'Report')} ({start_date.strftime('%m/%d/%Y')} to {end_date.strftime('%m/%d/%Y')})"

        # Determine file delivery method (download or email)
        delivery_method = form.delivery_method.data

        # Generate report file
        if report_format == 'csv':
            # Use specialized CSV generators for specific report types
            if report_type == 'payroll':
                csv_data = utils.generate_payroll_csv(data_dicts, report_title)
            elif report_type == 'job_cost':
                csv_data = utils.generate_job_cost_csv(data_dicts, report_title)
            elif report_type == 'device_audit':
                csv_data = utils.generate_device_audit_csv(data_dicts, report_title)
            else:
                csv_data = utils.generate_csv_report(data_dicts, columns)

            # Generate filename
            if report_type == 'device_audit':
                filename = f"device_audit_log_{start_date.strftime('%m%d%Y')}_{end_date.strftime('%m%d%Y')}.csv"
            else:
                filename = f"{report_type}_{start_date.strftime('%m%d%Y')}_{end_date.strftime('%m%d%Y')}.csv"
            
            # If this is a preview request, return the CSV data directly
            if is_preview:
                from flask import Response
                return Response(csv_data, mimetype='text/plain')

            # Check if we should email the report
            if delivery_method == 'email':
                recipient_email = form.recipient_email.data

                # Create email body
                email_body = f"""
                Please find attached the {report_title} you requested.

                Date Range: {start_date.strftime('%m/%d/%Y')} to {end_date.strftime('%m/%d/%Y')}
                Report Type: {report_titles.get(report_type, 'Report')}

                This is an automated email from the Construction Timesheet Management System.
                """

                # Send email with CSV attachment
                email_sent = utils.send_email_with_attachment(
                    recipient_email=recipient_email,
                    subject=f"Construction Timesheet: {report_title}",
                    body=email_body,
                    attachment_data=io.BytesIO(csv_data.encode('utf-8')),
                    attachment_filename=filename,
                    attachment_mimetype='text/csv')

                if email_sent:
                    flash(f'Report successfully emailed to {recipient_email}',
                          'success')
                else:
                    flash('Failed to send email. Please check SMTP settings.',
                          'danger')

                return redirect(url_for('generate_reports'))
            else:
                # Use the same file-based approach for CSV files to be consistent
                # Get the CSV data as bytes
                csv_bytes = csv_data.encode('utf-8')

                # Generate a unique ID for this report
                import uuid
                report_id = str(uuid.uuid4())

                # Create a temp directory if it doesn't exist
                temp_dir = os.path.join(os.getcwd(), 'temp_reports')
                if not os.path.exists(temp_dir):
                    os.makedirs(temp_dir)

                # Save the CSV data to a temporary file
                temp_file_path = os.path.join(temp_dir, f"{report_id}.csv")
                with open(temp_file_path, 'wb') as f:
                    f.write(csv_bytes)

                print(f"DEBUG: Saved CSV to temporary file: {temp_file_path}")

                # Store only file reference in session
                session['report_id'] = report_id
                session['report_filename'] = filename
                session['report_mimetype'] = 'text/csv'

                # Set a flash message
                flash(
                    'Report generated successfully. Download will begin shortly.',
                    'success')

                # Redirect to download endpoint
                return redirect(url_for('download_report'))
        else:  # PDF format
            print(
                f"DEBUG: Generating PDF report - format explicitly set to: {report_format}"
            )

            # Generate PDF report - use specialized functions for different report types
            if report_type == 'job_cost':
                pdf_buffer = utils.generate_job_cost_pdf(data_dicts, title=report_title)
            elif report_type == 'payroll' or report_type == 'employee_hours':
                pdf_buffer = utils.generate_payroll_pdf(data_dicts, title=report_title)
            elif report_type == 'device_audit':
                pdf_buffer = utils.generate_pdf_report(data_dicts, columns, title=report_title)
            else:
                pdf_buffer = utils.generate_pdf_report(data_dicts,
                                                       columns,
                                                       title=report_title)

            # Generate filename
            if report_type == 'device_audit':
                filename = f"device_audit_log_{start_date.strftime('%m%d%Y')}_{end_date.strftime('%m%d%Y')}.pdf"
            else:
                filename = f"{report_type}_{start_date.strftime('%m%d%Y')}_{end_date.strftime('%m%d%Y')}.pdf"
            print(f"DEBUG: PDF filename generated: {filename}")
            
            # If this is a preview request, return the PDF data directly
            if is_preview:
                from flask import Response
                # The PDF functions return raw bytes data
                response = Response(pdf_buffer, mimetype='application/pdf')
                response.headers['Content-Disposition'] = f'inline; filename="{filename}"'
                return response

            # Check if we should email the report
            if delivery_method == 'email':
                recipient_email = form.recipient_email.data
                print(f"DEBUG: Emailing PDF report to: {recipient_email}")

                # Create email body
                email_body = f"""
                Please find attached the {report_title} you requested.

                Date Range: {start_date.strftime('%m/%d/%Y')} to {end_date.strftime('%m/%d/%Y')}
                Report Type: {report_titles.get(report_type, 'Report')}

                This is an automated email from the Construction Timesheet Management System.
                """

                # Send email with PDF attachment - handle bytes vs buffer
                if isinstance(pdf_buffer, bytes):
                    attachment_data = io.BytesIO(pdf_buffer)
                else:
                    attachment_data = pdf_buffer
                    
                email_sent = utils.send_email_with_attachment(
                    recipient_email=recipient_email,
                    subject=f"Construction Timesheet: {report_title}",
                    body=email_body,
                    attachment_data=attachment_data,
                    attachment_filename=filename,
                    attachment_mimetype='application/pdf')

                if email_sent:
                    flash(f'Report successfully emailed to {recipient_email}',
                          'success')
                else:
                    flash(
                        'Failed to send email. Please check SMTP settings or credentials.',
                        'danger')

                return redirect(url_for('generate_reports'))
            else:
                # Get PDF data and validate
                if isinstance(pdf_buffer, bytes):
                    pdf_data = pdf_buffer
                else:
                    pdf_data = pdf_buffer.getvalue()
                print(
                    f"DEBUG: PDF size before storing in session: {len(pdf_data)} bytes"
                )
                if not pdf_data:
                    flash('Error: Generated PDF is empty', 'danger')
                    return redirect(url_for('generate_reports'))

                print(
                    f"DEBUG: Verified PDF data exists, proceeding with temporary file storage"
                )

                # CRITICAL FIX: The PDF is too large for the session cookie (>4KB limit)
                # Instead of storing binary data in the session, save to a temporary file
                # and store only the reference in the session

                # Generate a unique ID for this report
                import uuid
                report_id = str(uuid.uuid4())

                # Create a temp directory if it doesn't exist
                temp_dir = os.path.join(os.getcwd(), 'temp_reports')
                if not os.path.exists(temp_dir):
                    os.makedirs(temp_dir)

                # Save the PDF data to a temporary file
                temp_file_path = os.path.join(temp_dir, f"{report_id}.pdf")
                with open(temp_file_path, 'wb') as f:
                    f.write(pdf_data)

                print(f"DEBUG: Saved PDF to temporary file: {temp_file_path}")

                # Store only file reference in session (much smaller)
                session['report_id'] = report_id
                session['report_filename'] = filename
                session['report_mimetype'] = 'application/pdf'

                # Debug log for confirmation
                print(
                    f"DEBUG: Stored reference in session, report_id: {report_id}"
                )

                # Set a flash message
                flash(
                    'PDF report generated successfully. Download will begin shortly.',
                    'success')

                # Redirect to download endpoint
                return redirect(url_for('download_report'))

    # Default dates to current week
    if not form.start_date.data:
        today = date.today()
        form.start_date.data = get_week_start(today)
        form.end_date.data = form.start_date.data + timedelta(days=6)

    return render_template('admin/reports.html', form=form)


@app.route('/admin/gps_compliance', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_gps_compliance():
    """GPS Compliance Report - Show clock-in violations by distance from job sites"""
    form = GPSComplianceReportForm()
    
    violations_data = None
    executive_summary = None
    
    if form.validate_on_submit():
        start_date = form.start_date.data
        end_date = form.end_date.data
        
        # Query clock sessions with GPS data within date range
        clock_sessions = ClockSession.query.filter(
            ClockSession.clock_in >= start_date,
            ClockSession.clock_in <= end_date + timedelta(days=1),
            ClockSession.clock_in_distance_mi.isnot(None),
            ClockSession.clock_in_distance_mi > 0.5  # Only violations > 0.5 miles
        ).options(
            db.joinedload(ClockSession.user),
            db.joinedload(ClockSession.job)
        ).all()
        
        # Categorize violations
        fraud_risk = []  # 5+ miles
        major = []       # 2-5 miles  
        minor = []       # 0.5-2 miles
        worker_counts = {}
        
        total_clock_ins = ClockSession.query.filter(
            ClockSession.clock_in >= start_date,
            ClockSession.clock_in <= end_date + timedelta(days=1)
        ).count()
        
        for session in clock_sessions:
            distance = session.clock_in_distance_mi
            # Flag poor GPS accuracy (>100 meters)
            poor_gps_accuracy = session.clock_in_accuracy and session.clock_in_accuracy > 100
            
            violation_data = {
                'worker_name': session.user.name,
                'job_code': session.job.job_code,
                'job_description': session.job.description,
                'distance': round(distance, 2),
                'datetime': session.clock_in,
                'location': session.job.location or 'No location set',
                'clock_in_latitude': session.clock_in_latitude,
                'clock_in_longitude': session.clock_in_longitude,
                'job_latitude': session.job.latitude,
                'job_longitude': session.job.longitude,
                'gps_accuracy': round(session.clock_in_accuracy, 1) if session.clock_in_accuracy else None,
                'poor_gps_accuracy': poor_gps_accuracy
            }
            
            # Count violations per worker
            if session.user.name not in worker_counts:
                worker_counts[session.user.name] = {'total': 0, 'fraud_risk': 0, 'major': 0, 'minor': 0}
            worker_counts[session.user.name]['total'] += 1
            
            # Categorize by distance
            if distance >= 5.0:
                fraud_risk.append(violation_data)
                worker_counts[session.user.name]['fraud_risk'] += 1
            elif distance >= 2.0:
                major.append(violation_data)
                worker_counts[session.user.name]['major'] += 1
            else:
                minor.append(violation_data)
                worker_counts[session.user.name]['minor'] += 1
        
        # Calculate summary statistics
        total_violations = len(clock_sessions)
        compliant_count = total_clock_ins - total_violations
        
        executive_summary = {
            'total_clock_ins': total_clock_ins,
            'compliant_count': compliant_count,
            'compliant_percentage': round((compliant_count / total_clock_ins * 100) if total_clock_ins > 0 else 0, 1),
            'violations_count': total_violations,
            'violations_percentage': round((total_violations / total_clock_ins * 100) if total_clock_ins > 0 else 0, 1),
            'fraud_risk_count': len(fraud_risk),
            'major_count': len(major),
            'minor_count': len(minor)
        }
        
        violations_data = {
            'fraud_risk': sorted(fraud_risk, key=lambda x: x['distance'], reverse=True),
            'major': sorted(major, key=lambda x: x['distance'], reverse=True),
            'minor': sorted(minor, key=lambda x: x['distance'], reverse=True),
            'worker_summary': sorted(worker_counts.items(), key=lambda x: x[1]['total'], reverse=True)
        }
        
        # Handle PDF generation
        if form.format.data == 'pdf':
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.units import inch
            
            # Create PDF
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch)
            styles = getSampleStyleSheet()
            story = []
            
            # Title
            title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=16, spaceAfter=20)
            story.append(Paragraph(f"GPS Compliance Report", title_style))
            story.append(Paragraph(f"Date Range: {start_date.strftime('%m/%d/%Y')} to {end_date.strftime('%m/%d/%Y')}", styles['Normal']))
            story.append(Spacer(1, 20))
            
            # Executive Summary
            story.append(Paragraph("Executive Summary", styles['Heading2']))
            summary_data = [
                ['Total Clock-ins', str(executive_summary['total_clock_ins'])],
                ['Compliant', f"{executive_summary['compliant_count']} ({executive_summary['compliant_percentage']}%)"],
                ['Violations', f"{executive_summary['violations_count']} ({executive_summary['violations_percentage']}%)"],
                ['Fraud Risk (5+ mi)', str(executive_summary['fraud_risk_count'])],
                ['Major (2-5 mi)', str(executive_summary['major_count'])],
                ['Minor (0.5-2 mi)', str(executive_summary['minor_count'])]
            ]
            summary_table = Table(summary_data, colWidths=[2*inch, 1.5*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.grey),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 10),
                ('BOTTOMPADDING', (0,0), (-1,0), 12),
                ('BACKGROUND', (0,1), (-1,-1), colors.beige),
                ('GRID', (0,0), (-1,-1), 1, colors.black)
            ]))
            story.append(summary_table)
            story.append(Spacer(1, 20))
            
            # Violation tables
            for category, violations, title in [
                ('fraud_risk', violations_data['fraud_risk'], 'Fraud Risk Violations (5+ miles)'),
                ('major', violations_data['major'], 'Major Violations (2-5 miles)'),
                ('minor', violations_data['minor'], 'Minor Violations (0.5-2 miles)')
            ]:
                if violations:
                    story.append(Paragraph(title, styles['Heading3']))
                    table_data = [['Worker', 'Job', 'Distance (mi)', 'GPS Accuracy', 'Date/Time', 'Coordinates']]
                    for v in violations:
                        gps_accuracy = f"{v['gps_accuracy']}m" if v['gps_accuracy'] else "N/A"
                        if v['poor_gps_accuracy']:
                            gps_accuracy += " (Poor)"
                        
                        coordinates = "N/A"
                        if v['clock_in_latitude'] and v['clock_in_longitude']:
                            coordinates = f"{v['clock_in_latitude']:.4f}, {v['clock_in_longitude']:.4f}"
                        
                        table_data.append([
                            v['worker_name'],
                            f"{v['job_code']}\n{v['job_description'][:30]}..." if len(v['job_description']) > 30 else f"{v['job_code']}\n{v['job_description']}",
                            str(v['distance']),
                            gps_accuracy,
                            v['datetime'].strftime('%m/%d/%Y %H:%M'),
                            coordinates
                        ])
                    
                    violations_table = Table(table_data, colWidths=[1.2*inch, 1.2*inch, 0.8*inch, 1*inch, 1*inch, 1*inch])
                    violations_table.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,0), colors.grey),
                        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0,0), (-1,-1), 8),
                        ('BOTTOMPADDING', (0,0), (-1,0), 12),
                        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
                        ('GRID', (0,0), (-1,-1), 1, colors.black)
                    ]))
                    story.append(violations_table)
                    story.append(Spacer(1, 15))
            
            # Worker Violation Summary
            if violations_data['worker_summary']:
                story.append(Paragraph("Worker Violation Summary", styles['Heading3']))
                worker_table_data = [['Worker Name', 'Total Violations', 'Fraud Risk', 'Major', 'Minor']]
                for worker_name, violation_counts in violations_data['worker_summary']:
                    worker_table_data.append([
                        worker_name,
                        str(violation_counts['total']),
                        str(violation_counts['fraud_risk']),
                        str(violation_counts['major']),
                        str(violation_counts['minor'])
                    ])
                
                worker_table = Table(worker_table_data, colWidths=[2*inch, 1*inch, 1*inch, 1*inch, 1*inch])
                worker_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.grey),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0,0), (-1,-1), 10),
                    ('BOTTOMPADDING', (0,0), (-1,0), 12),
                    ('BACKGROUND', (0,1), (-1,-1), colors.beige),
                    ('GRID', (0,0), (-1,-1), 1, colors.black)
                ]))
                story.append(worker_table)
                story.append(Spacer(1, 15))
            
            doc.build(story)
            pdf_data = buffer.getvalue()
            buffer.close()
            
            # Return PDF file
            filename = f"gps_compliance_report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
            return send_file(
                BytesIO(pdf_data),
                mimetype='application/pdf',
                as_attachment=True,
                download_name=filename
            )
    
    return render_template('admin/gps_compliance.html', 
                         form=form, 
                         violations_data=violations_data,
                         executive_summary=executive_summary)


# API routes for AJAX calls
@app.route('/api/labor_activities/<int:job_id>')
@login_required
def get_labor_activities(job_id):
    job = Job.query.get_or_404(job_id)
    
    # Get job's required trades
    job_trade_ids = [trade.id for trade in job.trades]
    
    if not job_trade_ids:
        # No trades assigned to job, return empty list with clear message
        return jsonify({
            'activities': [],
            'error': 'This job has no trades assigned. Please contact your administrator.'
        })
    
    # Get enabled activities where activity.trade_id is in job.trades
    activities_query = LaborActivity.query.filter(
        LaborActivity.trade_id.in_(job_trade_ids),
        LaborActivity.is_active == True
    )
    
    # If worker has qualified trades, intersect with those
    if current_user.role == 'worker' and current_user.qualified_trades:
        worker_trade_ids = [trade.id for trade in current_user.qualified_trades]
        # Find intersection: trades that are both required by job AND worker is qualified for
        allowed_trade_ids = list(set(job_trade_ids) & set(worker_trade_ids))
        
        if not allowed_trade_ids:
            # Worker not qualified for any of the job's trades
            return jsonify({
                'activities': [],
                'error': 'You are not qualified for any trades required by this job. Please contact your administrator.'
            })
        
        # Filter activities to only those for trades worker is qualified for
        activities_query = activities_query.filter(LaborActivity.trade_id.in_(allowed_trade_ids))
    
    activities = activities_query.all()
    
    # Return JSON response with filtered labor activities
    return jsonify({
        'activities': [{
            'id': activity.id,
            'name': activity.name
        } for activity in activities]
    })


@app.route('/admin/geocode')
@login_required
@admin_required
def geocode():
    """API endpoint to geocode an address using Nominatim"""
    address = request.args.get('address', '')
    if not address:
        return jsonify({'error': 'No address provided'}), 400

    result = utils.geocode_address(address)
    if result:
        return jsonify(result)
    else:
        return jsonify({'error': 'Could not geocode address'}), 404


@app.route('/api/time_entries/<date>/<int:job_id>')
@login_required
def get_time_entries(date, job_id):
    """API endpoint to get time entries for a specific date and job"""
    try:
        # Try to parse the date with both common formats
        if '/' in date:
            target_date = datetime.strptime(date, '%m/%d/%Y').date()
        elif '-' in date:
            target_date = datetime.strptime(date, '%Y-%m-%d').date()
        else:
            print(f"WARNING: Invalid date format in API call: {date}")
            return jsonify({'error': f'Invalid date format: {date}'}), 400
    except ValueError as e:
        print(
            f"ERROR: Invalid date format in API call: {date}, error: {str(e)}")
        return jsonify({'error': f'Error parsing date: {str(e)}'}), 400

    try:
        entries = TimeEntry.query.filter(TimeEntry.user_id == current_user.id,
                                         TimeEntry.job_id == job_id,
                                         TimeEntry.date == target_date).all()

        # Return JSON response with time entries
        return jsonify([{
            'id': entry.id,
            'labor_activity_id': entry.labor_activity_id,
            'hours': entry.hours,
            'notes': entry.notes
        } for entry in entries])
    except Exception as e:
        print(f"Error loading time entries: {str(e)}")
        return jsonify({'error': f'Error loading entries: {str(e)}'}), 500


# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500


@app.route('/download-report')
@login_required
def download_report():
    """Download report endpoint that serves file and redirects back to the reports page"""
    # We now use only the file reference mode
    if 'report_id' not in session or 'report_filename' not in session or 'report_mimetype' not in session:
        flash('No report data found. Please generate a report first.',
              'warning')
        return redirect(url_for('generate_reports'))

    # Get filename and mimetype from session
    filename = session['report_filename']
    mimetype = session['report_mimetype']
    report_id = session['report_id']

    # Log what we're doing
    print(
        f"DEBUG download_report: Using file reference mode, ID: {report_id}, File: {filename}"
    )

    # Verify the file exists before proceeding
    file_ext = 'pdf' if mimetype == 'application/pdf' else 'csv'
    temp_file_path = os.path.join(os.getcwd(), 'temp_reports',
                                  f"{report_id}.{file_ext}")

    if not os.path.exists(temp_file_path):
        flash('Error: Report file not found. Please regenerate the report.',
              'danger')
        return redirect(url_for('generate_reports'))

    # Create a template that will auto-download the file and then redirect back
    return render_template('download.html',
                           filename=filename,
                           mimetype=mimetype,
                           return_url=url_for('generate_reports'))


@app.route('/get-report-file')
@login_required
def get_report_file():
    """Actual file download endpoint"""
    # We now use only file-based storage with report_id for all file types
    if 'report_id' not in session or 'report_filename' not in session or 'report_mimetype' not in session:
        flash('No report data found. Please generate a report first.',
              'warning')
        return redirect(url_for('generate_reports'))

    # Get information from session
    report_id = session['report_id']
    report_filename = session['report_filename']
    report_mimetype = session['report_mimetype']

    print(
        f"DEBUG get_report_file: Processing {report_filename}, mimetype {report_mimetype}, ID: {report_id}"
    )

    try:
        # Determine file extension and path based on mimetype
        is_pdf = report_mimetype == 'application/pdf' or report_filename.lower(
        ).endswith('.pdf')
        file_ext = 'pdf' if is_pdf else 'csv'

        # Build the path to the temporary file
        temp_file_path = os.path.join(os.getcwd(), 'temp_reports',
                                      f"{report_id}.{file_ext}")

        print(f"DEBUG: Reading file from: {temp_file_path}")

        # Check if the file exists
        if not os.path.exists(temp_file_path):
            flash(
                'Error: Report file not found. Please regenerate the report.',
                'danger')
            return redirect(url_for('generate_reports'))

        # Send the file directly from disk with appropriate mimetype
        if is_pdf:
            print(f"DEBUG: Serving PDF file with strict PDF mimetype")

            # For PDFs, apply special handling with strict headers
            response = send_file(temp_file_path,
                                 mimetype='application/pdf',
                                 as_attachment=True,
                                 download_name=report_filename)

            # Add headers to ensure browser treats it as a download
            response.headers[
                "Content-Disposition"] = f"attachment; filename={report_filename}"
            response.headers[
                "Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        else:
            # For other formats (CSV, etc.), use standard delivery
            print(
                f"DEBUG: Serving file using standard delivery for {report_mimetype}"
            )
            response = send_file(temp_file_path,
                                 mimetype=report_mimetype,
                                 as_attachment=True,
                                 download_name=report_filename)

        # Clean up the temp file after sending (optional, can be disabled for debugging)
        # os.remove(temp_file_path)

        return response

    except Exception as e:
        print(f"Error sending file: {e}")
        flash(f'Error downloading file: {str(e)}', 'danger')
        return redirect(url_for('generate_reports'))


@app.route('/debug')
def debug_route():
    """Debug route to test rendering and basic functionality"""
    form = LoginForm()
    return render_template('login.html', form=form)