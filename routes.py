import os
import csv
import io
import base64
from datetime import datetime, timedelta, date
from functools import wraps
from flask import render_template, redirect, url_for, flash, request, jsonify, send_file, session
from flask_login import login_user, logout_user, current_user, login_required
from app import app, db
from models import User, Job, LaborActivity, TimeEntry, WeeklyApprovalLock, ClockSession
from forms import (LoginForm, RegistrationForm, TimeEntryForm, ApprovalForm, JobForm,
                  LaborActivityForm, UserManagementForm, ReportForm, WeeklyTimesheetForm,
                  ClockInForm, ClockOutForm)
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
    return target_date - timedelta(days=target_date.weekday())

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

# Authentication routes
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_worker():
            if current_user.use_clock_in:
                return redirect(url_for('worker_clock'))
            else:
                return redirect(url_for('worker_timesheet'))
        elif current_user.is_foreman():
            return redirect(url_for('foreman_dashboard'))
        else:
            return redirect(url_for('admin_dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')

            if next_page:
                return redirect(next_page)
            elif user.is_worker():
                if user.use_clock_in:
                    return redirect(url_for('worker_clock'))
                else:
                    return redirect(url_for('worker_timesheet'))
            elif user.is_foreman():
                return redirect(url_for('foreman_dashboard'))
            else:
                return redirect(url_for('admin_dashboard'))
        else:
            flash('Login unsuccessful. Please check your email and password.', 'danger')

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
        user = User(
            name=form.name.data,
            email=form.email.data,
            role=form.role.data
        )
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
    form = WeeklyTimesheetForm()

    # Check if we're loading a specific job's labor activities
    job_id = request.args.get('job_id')
    if job_id:
        job = Job.query.get_or_404(job_id)
        # Populate labor activities for this job's trade type
        form.labor_activity_id.choices = [(activity.id, activity.name) 
                                     for activity in LaborActivity.query.filter_by(trade_category=job.trade_type).all()]
    else:
        # Default empty list or all activities if no job selected
        form.labor_activity_id.choices = [(activity.id, activity.name) for activity in LaborActivity.query.all()]

    # Default to current week if no week start provided
    if not form.week_start.data:
        today = date.today()
        form.week_start.data = get_week_start(today)

    week_start = form.week_start.data
    week_end = week_start + timedelta(days=6)

    if form.validate_on_submit():
        # Check if any timesheet for this week is already approved/locked
        is_locked = WeeklyApprovalLock.query.filter_by(
            user_id=current_user.id,
            job_id=form.job_id.data,
            week_start=week_start
        ).first()

        if is_locked:
            flash('Cannot add or edit time entries for this week. It has already been approved.', 'danger')
            return redirect(url_for('worker_weekly_timesheet'))

        # First, delete any existing entries for this week with the same activity
        # This ensures we don't get duplicate entries if the user submits multiple times
        TimeEntry.query.filter(
            TimeEntry.user_id == current_user.id,
            TimeEntry.job_id == form.job_id.data,
            TimeEntry.labor_activity_id == form.labor_activity_id.data,
            TimeEntry.date >= week_start,
            TimeEntry.date <= week_end
        ).delete()

        # Create time entries for each day of the week that has hours
        days_of_week = [
            ('monday', form.monday_hours),
            ('tuesday', form.tuesday_hours),
            ('wednesday', form.wednesday_hours),
            ('thursday', form.thursday_hours),
            ('friday', form.friday_hours),
            ('saturday', form.saturday_hours),
            ('sunday', form.sunday_hours)
        ]

        entries_created = 0

        for i, (day_name, hours_field) in enumerate(days_of_week):
            if hours_field.data and hours_field.data > 0:
                # Calculate the date for this day
                entry_date = week_start + timedelta(days=i)

                # Create new entry
                new_entry = TimeEntry(
                    user_id=current_user.id,
                    job_id=form.job_id.data,
                    labor_activity_id=form.labor_activity_id.data,
                    date=entry_date,
                    hours=hours_field.data,
                    notes=form.notes.data
                )
                db.session.add(new_entry)
                entries_created += 1

        db.session.commit()

        if entries_created > 0:
            flash(f'Weekly timesheet saved successfully! Created {entries_created} time entries.', 'success')
        else:
            flash('Weekly timesheet updated successfully!', 'success')

        # Pass the week_start to maintain the selected date when redirecting
        return redirect(url_for('worker_history', start_date=week_start.strftime('%m/%d/%Y')))

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
        # Load existing entries for this week with eager loading of labor_activity
        if form.job_id.data and form.labor_activity_id.data:
            print(f"DEBUG: Searching for entries with job_id={form.job_id.data}, labor_activity_id={form.labor_activity_id.data}, user_id={current_user.id}")
            print(f"DEBUG: Week range: {week_start} to {week_end}")

            existing_entries = TimeEntry.query.filter(
                TimeEntry.user_id == current_user.id,
                TimeEntry.job_id == form.job_id.data,
                TimeEntry.labor_activity_id == form.labor_activity_id.data,
                TimeEntry.date >= week_start,
                TimeEntry.date <= week_end
            ).options(db.joinedload(TimeEntry.labor_activity)).all()

            print(f"DEBUG: Found {len(existing_entries)} existing entries")

            # Set all hours fields to 0 by default
            form.monday_hours.data = 0.0
            form.tuesday_hours.data = 0.0
            form.wednesday_hours.data = 0.0
            form.thursday_hours.data = 0.0
            form.friday_hours.data = 0.0
            form.saturday_hours.data = 0.0
            form.sunday_hours.data = 0.0

            # If there are existing entries, populate the form
            if existing_entries:
                print(f"DEBUG: Setting form values from existing entries")

                # Create a dictionary to store hours by day index
                day_entries = {}
                for entry in existing_entries:
                    print(f"DEBUG: Entry date {entry.date}, hours {entry.hours}")
                    day_index = (entry.date - week_start).days
                    if 0 <= day_index <= 6:  # Make sure it's within the week
                        day_entries[day_index] = entry.hours
                        print(f"DEBUG: Day index {day_index} = {entry.hours} hours")

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
                if existing_entries:
                    form.notes.data = existing_entries[0].notes

                print(f"DEBUG: Form values after population: M={form.monday_hours.data}, T={form.tuesday_hours.data}, W={form.wednesday_hours.data}, Total: {sum([form.monday_hours.data or 0, form.tuesday_hours.data or 0, form.wednesday_hours.data or 0, form.thursday_hours.data or 0, form.friday_hours.data or 0, form.saturday_hours.data or 0, form.sunday_hours.data or 0])}")
            else:
                print("DEBUG: No existing entries found to populate form")
    # Handle the case where job_id is set but labor_activity_id is not
    elif form.job_id.data and request.method == 'GET':
        # If just job_id is set but not labor_activity_id, try to find any entries for this job
        # to determine which labor activity to show by default
        print(f"DEBUG: Searching for any job entries with job_id={form.job_id.data}")
        job_entries = TimeEntry.query.filter(
            TimeEntry.user_id == current_user.id,
            TimeEntry.job_id == form.job_id.data,
            TimeEntry.date >= week_start,
            TimeEntry.date <= week_end
        ).options(db.joinedload(TimeEntry.labor_activity)).all()

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
                    print(f"DEBUG: Entry date {entry.date}, hours {entry.hours}")
                    day_index = (entry.date - week_start).days
                    if 0 <= day_index <= 6:  # Make sure it's within the week
                        day_entries[day_index] = entry.hours
                        print(f"DEBUG: Day index {day_index} = {entry.hours} hours")

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

                print(f"DEBUG: Form values after population from job entries: M={form.monday_hours.data}, T={form.tuesday_hours.data}, W={form.wednesday_hours.data}, Total: {sum([form.monday_hours.data or 0, form.tuesday_hours.data or 0, form.wednesday_hours.data or 0, form.thursday_hours.data or 0, form.friday_hours.data or 0, form.saturday_hours.data or 0, form.sunday_hours.data or 0])}")
            else:
                print("DEBUG: No grouped activities found to populate form")
        else:
            print("DEBUG: No job entries found to populate form")

    return render_template('worker/weekly_timesheet.html', form=form)

@app.route('/worker/timesheet', methods=['GET', 'POST'])
@login_required
@worker_required
def worker_timesheet():
    form = TimeEntryForm()

    # Default to today's date
    if not form.date.data:
        form.date.data = date.today()

    if form.validate_on_submit():
        # Check if timesheet for this date is already approved/locked
        week_start = get_week_start(form.date.data)
        is_locked = WeeklyApprovalLock.query.filter_by(
            user_id=current_user.id,
            job_id=form.job_id.data,
            week_start=week_start
        ).first()

        if is_locked:
            flash('Cannot add or edit time entries for this week. It has already been approved.', 'danger')
            return redirect(url_for('worker_timesheet'))

        # Extract all labor activities from the form
        labor_activities = []
        for key in request.form.keys():
            if key.startswith('labor_activity_') and key != 'labor_activity_1':
                index = key.split('_')[-1]
                activity_id = request.form.get(f'labor_activity_{index}')
                hours = request.form.get(f'hours_{index}')

                if activity_id and hours and float(hours) > 0:
                    labor_activities.append((int(activity_id), float(hours)))

        # Add the first activity if it's valid
        if form.labor_activity_1.data and form.hours_1.data and form.hours_1.data > 0:
            labor_activities.append((form.labor_activity_1.data, form.hours_1.data))

        # Ensure we have at least one valid labor activity
        if not labor_activities:
            flash('You must enter at least one labor activity with hours.', 'danger')
            return redirect(url_for('worker_timesheet'))

        # Get all activity IDs that will be submitted
        activity_ids = [act_id for act_id, _ in labor_activities]

        # Delete all existing entries for this date and job with matching activities
        # to avoid duplicates when resubmitting the form
        TimeEntry.query.filter(
            TimeEntry.user_id == current_user.id,
            TimeEntry.job_id == form.job_id.data,
            TimeEntry.labor_activity_id.in_(activity_ids),
            TimeEntry.date == form.date.data
        ).delete()

        # Create new entries for each activity
        for activity_id, hours in labor_activities:
            # Create new entry
            new_entry = TimeEntry(
                user_id=current_user.id,
                job_id=form.job_id.data,
                labor_activity_id=activity_id,
                date=form.date.data,
                hours=hours,
                notes=form.notes.data
            )
            db.session.add(new_entry)

        db.session.commit()
        flash('Time entry saved successfully!', 'success')
        # Pass the date to maintain the selected date when redirecting
        week_start = get_week_start(form.date.data)
        return redirect(url_for('worker_history', start_date=week_start.strftime('%m/%d/%Y')))

    # Get labor activities for the selected job's trade type
    activities = LaborActivity.query.all()

    return render_template('worker/timesheet.html', form=form, activities=activities)

@app.route('/worker/history')
@login_required
@worker_required
def worker_history():
    # Get date range parameters from query string
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # Default to current week if no dates provided
    if not start_date:
        today = date.today()
        start_date = get_week_start(today)
    else:
        start_date = datetime.strptime(start_date, '%m/%d/%Y').date()

    if not end_date:
        end_date = start_date + timedelta(days=6)
    else:
        end_date = datetime.strptime(end_date, '%m/%d/%Y').date()

    # Get time entries for the date range
    entries = TimeEntry.query.filter(
        TimeEntry.user_id == current_user.id,
        TimeEntry.date >= start_date,
        TimeEntry.date <= end_date
    ).order_by(TimeEntry.date.desc()).all()

    # Group entries by date for display
    entries_by_date = {}
    for entry in entries:
        if entry.date not in entries_by_date:
            entries_by_date[entry.date] = []
        entries_by_date[entry.date].append(entry)

    # Get weekly approval status
    week_start = get_week_start(start_date)
    approved_weeks = WeeklyApprovalLock.query.filter_by(
        user_id=current_user.id,
        week_start=week_start
    ).all()

    approved_jobs = [lock.job_id for lock in approved_weeks]

    return render_template(
        'worker/history.html',
        entries_by_date=entries_by_date,
        start_date=start_date,
        end_date=end_date,
        approved_jobs=approved_jobs
    )

@app.route('/worker/clock', methods=['GET'])
@login_required
@worker_required
def worker_clock():
    """Clock in/out interface for workers who use the clock system"""
    # Check if user is configured to use clock in/out
    if not current_user.use_clock_in:
        flash('You are not configured to use the clock in/out system. Please use the timesheet interface.', 'warning')
        return redirect(url_for('worker_timesheet'))
    
    # Get active session (if any)
    active_session = ClockSession.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).first()
    
    # Get today's sessions (active and completed)
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end = datetime.combine(date.today(), datetime.max.time())
    
    today_sessions = ClockSession.query.filter(
        ClockSession.user_id == current_user.id,
        ClockSession.clock_in >= today_start,
        ClockSession.clock_in <= today_end
    ).order_by(ClockSession.clock_in.desc()).all()
    
    # Calculate today's hours from completed sessions
    today_hours = sum(session.get_duration_hours() for session in today_sessions if not session.is_active)
    
    # Get recent sessions (completed, not including today)
    recent_sessions = ClockSession.query.filter(
        ClockSession.user_id == current_user.id,
        ClockSession.is_active == False,
        ClockSession.clock_in < today_start
    ).order_by(ClockSession.clock_in.desc()).limit(5).all()
    
    # Prepare forms
    clock_in_form = ClockInForm()
    clock_out_form = ClockOutForm()
    
    return render_template(
        'worker/clock.html',
        active_session=active_session,
        today_sessions=today_sessions,
        recent_sessions=recent_sessions,
        today_hours=today_hours,
        session_count=len([s for s in today_sessions if not s.is_active]),
        clock_in_form=clock_in_form,
        clock_out_form=clock_out_form
    )

@app.route('/worker/clock-in', methods=['POST'])
@login_required
@worker_required
def clock_in():
    """Handle clock in submissions"""
    # Check if user is configured to use clock in/out
    if not current_user.use_clock_in:
        flash('You are not configured to use the clock in/out system.', 'warning')
        return redirect(url_for('worker_timesheet'))
    
    # Check if already clocked in
    active_session = ClockSession.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).first()
    
    if active_session:
        flash('You are already clocked in! Please clock out of your current session first.', 'warning')
        return redirect(url_for('worker_clock'))
    
    form = ClockInForm()
    
    if form.validate_on_submit():
        # Create new clock session
        session = ClockSession(
            user_id=current_user.id,
            job_id=form.job_id.data,
            labor_activity_id=form.labor_activity_id.data,
            notes=form.notes.data,
            clock_in=datetime.utcnow(),
            is_active=True
        )
        
        db.session.add(session)
        db.session.commit()
        
        flash('You have successfully clocked in!', 'success')
        return redirect(url_for('worker_clock'))
    
    # If form validation fails
    for field, errors in form.errors.items():
        for error in errors:
            flash(f"Error in {getattr(form, field).label.text}: {error}", "danger")
    
    return redirect(url_for('worker_clock'))

@app.route('/api/job/<int:job_id>')
@login_required
def get_job_details(job_id):
    job = Job.query.get_or_404(job_id)
    return jsonify({
        'description': job.description,
        'location': job.location,
        'foreman_name': job.foreman.name if job.foreman else None
    })

@app.route('/worker/clock-out', methods=['POST'])
@login_required
@worker_required
def clock_out():
    """Handle clock out submissions"""
    # Check if user is configured to use clock in/out
    if not current_user.use_clock_in:
        flash('You are not configured to use the clock in/out system.', 'warning')
        return redirect(url_for('worker_timesheet'))
    
    # Get active session
    active_session = ClockSession.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).first()
    
    if not active_session:
        flash('You are not currently clocked in to any job!', 'warning')
        return redirect(url_for('worker_clock'))
    
    form = ClockOutForm()
    
    if form.validate_on_submit():
        # Update notes if provided
        if form.notes.data:
            active_session.notes = form.notes.data
        
        # Clock out
        active_session.clock_out_session()
        
        # Create a time entry based on this clock session
        time_entry = active_session.create_time_entry()
        if time_entry:
            db.session.add(time_entry)
        
        db.session.commit()
        
        hours = active_session.get_duration_hours()
        flash(f'You have successfully clocked out! {hours:.2f} hours recorded.', 'success')
        return redirect(url_for('worker_clock'))
    
    # If form validation fails
    for field, errors in form.errors.items():
        for error in errors:
            flash(f"Error in {getattr(form, field).label.text}: {error}", "danger")
    
    return redirect(url_for('worker_clock'))

# Foreman routes
@app.route('/foreman/dashboard')
@login_required
@foreman_required
def foreman_dashboard():
    # Get date range parameters from query string
    start_date = request.args.get('start_date')

    # Default to current week if no dates provided
    if not start_date:
        today = date.today()
        start_date = get_week_start(today)
    else:
        start_date = datetime.strptime(start_date, '%m/%d/%Y').date()

    end_date = start_date + timedelta(days=6)

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
                user_id=worker.id,
                job_id=job.id,
                week_start=start_date
            ).first() is not None

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

            workers_data.append({
                'worker': worker,
                'is_approved': is_approved,
                'total_hours': total_hours,
                'days_with_entries': days_with_entries,
                'has_all_days': days_with_entries == 7  # A full week has 7 days
            })

        job_data.append({
            'job': job,
            'workers': workers_data
        })

    return render_template(
        'foreman/dashboard.html',
        job_data=job_data,
        start_date=start_date,
        end_date=end_date
    )

@app.route('/foreman/enter_time/<int:job_id>/<int:user_id>', methods=['GET', 'POST'])
@login_required
@foreman_required
def foreman_enter_time(job_id, user_id):
    """Allow foremen to enter time on behalf of a worker"""
    # Get the worker and job
    worker = User.query.get_or_404(user_id)
    job = Job.query.get_or_404(job_id)

    # Use the same weekly timesheet form as workers
    form = WeeklyTimesheetForm()
    form.job_id.data = job_id

    # Populate labor activity choices based on job trade
    labor_activities = LaborActivity.query.filter_by(trade_category=job.trade_type).all()
    form.labor_activity_id.choices = [(activity.id, activity.name) for activity in labor_activities]

    # Get week start from query parameters or default to current week
    selected_week = request.args.get('week_start')
    if selected_week:
        form.week_start.data = datetime.strptime(selected_week, '%m/%d/%Y').date()
    elif not form.week_start.data:
        today = date.today()
        form.week_start.data = get_week_start(today)

    week_start = form.week_start.data
    week_end = week_start + timedelta(days=6)

    # Check if this week is already approved
    existing_approval = WeeklyApprovalLock.query.filter_by(
        user_id=user_id,
        job_id=job_id,
        week_start=week_start
    ).first()

    if existing_approval:
        flash(f'This week was already approved by {existing_approval.approver.name} on {existing_approval.approved_at.strftime("%m/%d/%Y %H:%M")}. Time entries cannot be modified.', 'warning')
        # Pass the week_start to maintain the selected date when redirecting
        return redirect(url_for('foreman_dashboard', start_date=week_start.strftime('%m/%d/%Y')))

    if form.validate_on_submit():
        # Get the dates for each day of the week
        monday = form.week_start.data
        dates = [monday + timedelta(days=i) for i in range(7)]

        # Get the hours for each day
        hours_values = [
            form.monday_hours.data,
            form.tuesday_hours.data, 
            form.wednesday_hours.data,
            form.thursday_hours.data,
            form.friday_hours.data,
            form.saturday_hours.data,
            form.sunday_hours.data
        ]

        # First, delete any existing entries for this week with the same activity
        # This ensures we don't get duplicate entries if the foreman submits multiple times
        TimeEntry.query.filter(
            TimeEntry.user_id == user_id,
            TimeEntry.job_id == job_id,
            TimeEntry.labor_activity_id == form.labor_activity_id.data,
            TimeEntry.date >= dates[0],
            TimeEntry.date <= dates[6]
        ).delete()

        # Now create new entries for days with hours > 0
        for i, date_val in enumerate(dates):
            if hours_values[i] > 0:
                # Create a new entry
                entry = TimeEntry(
                    user_id=user_id,
                    job_id=job_id,
                    labor_activity_id=form.labor_activity_id.data,
                    date=date_val,
                    hours=hours_values[i],
                    notes=form.notes.data
                )
                db.session.add(entry)

        db.session.commit()
        flash(f'Time entries for {worker.name} on {job.job_code} successfully saved!', 'success')
        # Pass the week_start to maintain the selected date when redirecting
        return redirect(url_for('foreman_dashboard', start_date=week_start.strftime('%m/%d/%Y')))

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
        if form.labor_activity_id.data:
            # If labor activity is already selected, get entries for that specific activity
            existing_entries = TimeEntry.query.filter(
                TimeEntry.user_id == user_id,
                TimeEntry.job_id == job_id,
                TimeEntry.labor_activity_id == form.labor_activity_id.data,
                TimeEntry.date >= week_start,
                TimeEntry.date <= week_end
            ).options(db.joinedload(TimeEntry.labor_activity)).all()

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
            # If no labor activity selected, get all entries and pick the first activity
            existing_entries = TimeEntry.query.filter(
                TimeEntry.user_id == user_id,
                TimeEntry.job_id == job_id,
                TimeEntry.date >= week_start,
                TimeEntry.date <= week_end
            ).options(db.joinedload(TimeEntry.labor_activity)).all()

            if existing_entries:
                # Group by labor_activity_id
                entries_by_activity = {}
                for entry in existing_entries:
                    if entry.labor_activity_id not in entries_by_activity:
                        entries_by_activity[entry.labor_activity_id] = []
                    entries_by_activity[entry.labor_activity_id].append(entry)

                if entries_by_activity:
                    # Get the first activity and its entries
                    activity_id, first_entries = next(iter(entries_by_activity.items()))
                    form.labor_activity_id.data = activity_id

                    # Create a dictionary to store hours by day index
                    day_entries = {}
                    for entry in first_entries:
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
                    if first_entries:
                        form.notes.data = first_entries[0].notes

    return render_template(
        'foreman/enter_time.html',
        form=form,
        worker=worker,
        job=job,
        week_start=week_start,
        week_end=week_end,
        existing_entries=existing_entries
    )

@app.route('/foreman/approve/<int:job_id>/<int:user_id>', methods=['GET', 'POST'])
@login_required
@foreman_required
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
            # Use the start_date from URL
            form.week_start.data = datetime.strptime(url_start_date, '%m/%d/%Y').date()
        else:
            today = date.today()
            form.week_start.data = get_week_start(today)

    week_start = form.week_start.data
    week_end = week_start + timedelta(days=6)

    # Check if this week is already approved
    existing_approval = WeeklyApprovalLock.query.filter_by(
        user_id=user_id,
        job_id=job_id,
        week_start=week_start
    ).first()

    if existing_approval:
        flash(f'This week was already approved by {existing_approval.approver.name} on {existing_approval.approved_at.strftime("%m/%d/%Y %H:%M")}', 'warning')
        # Pass the week_start to maintain the selected date when redirecting
        return redirect(url_for('foreman_dashboard', start_date=week_start.strftime('%m/%d/%Y')))

    # Get all time entries for the week
    entries = TimeEntry.query.filter(
        TimeEntry.user_id == user_id,
        TimeEntry.job_id == job_id,
        TimeEntry.date >= week_start,
        TimeEntry.date <= week_end
    ).order_by(TimeEntry.date).all()

    # Check if all 7 days have entries
    days_with_entries = set(entry.date for entry in entries)
    all_days = {week_start + timedelta(days=i) for i in range(7)}
    missing_days = all_days - days_with_entries

    if form.validate_on_submit():
        # Show a notification about missing days, but still allow approval
        if missing_days:
            missing_day_list = ", ".join([d.strftime('%a %m/%d') for d in sorted(missing_days)])
            flash(f'Note: Worker has no time entries for: {missing_day_list}', 'warning')

        # Approve all time entries
        for entry in entries:
            entry.approved = True
            entry.approved_by = current_user.id
            entry.approved_at = datetime.utcnow()

        # Create weekly approval lock
        approval = WeeklyApprovalLock(
            user_id=user_id,
            job_id=job_id,
            week_start=week_start,
            approved_by=current_user.id
        )
        db.session.add(approval)
        db.session.commit()

        flash(f'Timesheet for {worker.name} on job {job.job_code} successfully approved!', 'success')
        # Pass the week_start to maintain the selected date when redirecting
        return redirect(url_for('foreman_dashboard', start_date=week_start.strftime('%m/%d/%Y')))

    # Group entries by date for display
    entries_by_date = {}
    for day in all_days:
        entries_by_date[day] = []

    for entry in entries:
        entries_by_date[entry.date].append(entry)

    # Calculate daily and weekly totals
    daily_totals = {day: sum(entry.hours for entry in day_entries) 
                   for day, day_entries in entries_by_date.items()}
    weekly_total = sum(daily_totals.values())

    return render_template(
        'foreman/approve.html',
        form=form,
        worker=worker,
        job=job,
        entries_by_date=entries_by_date,
        daily_totals=daily_totals,
        weekly_total=weekly_total,
        missing_days=missing_days,
        week_start=week_start,
        week_end=week_end
    )

# Admin routes
@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    # Get counts for dashboard widgets
    active_jobs_count = Job.query.filter_by(status='active').count()
    total_workers = User.query.filter_by(role='worker').count()

    # Get recent time approvals
    recent_approvals = WeeklyApprovalLock.query.order_by(
        WeeklyApprovalLock.approved_at.desc()
    ).limit(10).all()

    # Get current week's total hours
    today = date.today()
    week_start = get_week_start(today)
    week_end = week_start + timedelta(days=6)

    weekly_hours = db.session.query(db.func.sum(TimeEntry.hours)).\
        filter(
            TimeEntry.date >= week_start,
            TimeEntry.date <= week_end
        ).scalar() or 0

    # Get hours by job for the current week (for chart)
    job_hours = db.session.query(
        Job.job_code,
        db.func.sum(TimeEntry.hours).label('total_hours')
    ).join(TimeEntry, Job.id == TimeEntry.job_id).filter(
        TimeEntry.date >= week_start,
        TimeEntry.date <= week_end
    ).group_by(Job.job_code).all()

    # Get hours by trade category for the current week (for chart)
    trade_hours = db.session.query(
        LaborActivity.trade_category,
        db.func.sum(TimeEntry.hours).label('total_hours')
    ).join(TimeEntry, LaborActivity.id == TimeEntry.labor_activity_id).filter(
        TimeEntry.date >= week_start,
        TimeEntry.date <= week_end
    ).group_by(LaborActivity.trade_category).all()

    return render_template(
        'admin/dashboard.html',
        active_jobs_count=active_jobs_count,
        total_workers=total_workers,
        weekly_hours=weekly_hours,
        recent_approvals=recent_approvals,
        job_hours=job_hours,
        trade_hours=trade_hours,
        week_start=week_start,
        week_end=week_end
    )

@app.route('/admin/jobs', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_jobs():
    form = JobForm()

    if form.validate_on_submit():
        # Check if we're editing an existing job
        job_id = request.args.get('edit')

        if job_id:
            job = Job.query.get_or_404(job_id)
            job.job_code = form.job_code.data
            job.description = form.description.data
            job.location = form.location.data
            job.status = form.status.data
            job.trade_type = form.trade_type.data
            # Handle foreman assignment
            if form.foreman_id.data and form.foreman_id.data > 0:
                job.foreman_id = form.foreman_id.data
            else:
                job.foreman_id = None
            flash('Job updated successfully!', 'success')
        else:
            # Create new job
            job = Job(
                job_code=form.job_code.data,
                description=form.description.data,
                location=form.location.data,
                status=form.status.data,
                trade_type=form.trade_type.data,
                foreman_id=form.foreman_id.data if form.foreman_id.data and form.foreman_id.data > 0 else None
            )
            db.session.add(job)
            flash('New job created successfully!', 'success')

        db.session.commit()
        return redirect(url_for('manage_jobs'))

    # Check if we're editing a job
    job_id = request.args.get('edit')
    if job_id:
        job = Job.query.get_or_404(job_id)
        form.job_code.data = job.job_code
        form.description.data = job.description
        form.location.data = job.location
        form.status.data = job.status
        form.trade_type.data = job.trade_type
        form.foreman_id.data = job.foreman_id if job.foreman_id else 0

    # Get all jobs for display
    jobs = Job.query.order_by(Job.created_at.desc()).all()

    return render_template('admin/jobs.html', form=form, jobs=jobs, editing=bool(job_id))

@app.route('/admin/jobs/delete/<int:job_id>', methods=['POST'])
@login_required
@admin_required
def delete_job(job_id):
    job = Job.query.get_or_404(job_id)
    
    # Check if there are any time entries associated with this job
    time_entries = TimeEntry.query.filter_by(job_id=job_id).count()
    
    if time_entries > 0:
        flash(f'Cannot delete job "{job.job_code}". It has {time_entries} time entries associated with it. Mark it as "Complete" instead.', 'danger')
        return redirect(url_for('manage_jobs'))
    
    # Check if there are any weekly approval locks for this job
    approvals = WeeklyApprovalLock.query.filter_by(job_id=job_id).count()
    
    if approvals > 0:
        flash(f'Cannot delete job "{job.job_code}". It has {approvals} weekly approvals associated with it. Mark it as "Complete" instead.', 'danger')
        return redirect(url_for('manage_jobs'))
        
    # If no time entries or approvals, safe to delete
    job_code = job.job_code  # Store for the flash message
    db.session.delete(job)
    db.session.commit()
    
    flash(f'Job "{job_code}" has been deleted successfully.', 'success')
    return redirect(url_for('manage_jobs'))

@app.route('/admin/activities', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_activities():
    form = LaborActivityForm()

    if form.validate_on_submit():
        # Check if we're editing an existing activity
        activity_id = request.args.get('edit')

        if activity_id:
            activity = LaborActivity.query.get_or_404(activity_id)
            activity.name = form.name.data
            activity.trade_category = form.trade_category.data
            flash('Labor activity updated successfully!', 'success')
        else:
            # Create new activity
            activity = LaborActivity(
                name=form.name.data,
                trade_category=form.trade_category.data
            )
            db.session.add(activity)
            flash('New labor activity created successfully!', 'success')

        db.session.commit()
        return redirect(url_for('manage_activities'))

    # Check if we're editing an activity
    activity_id = request.args.get('edit')
    if activity_id:
        activity = LaborActivity.query.get_or_404(activity_id)
        form.name.data = activity.name
        form.trade_category.data = activity.trade_category

    # Get all activities grouped by trade category
    activities_by_trade = {}
    activities = LaborActivity.query.order_by(LaborActivity.trade_category, LaborActivity.name).all()

    for activity in activities:
        if activity.trade_category not in activities_by_trade:
            activities_by_trade[activity.trade_category] = []
        activities_by_trade[activity.trade_category].append(activity)

    return render_template(
        'admin/activities.html',
        form=form,
        activities_by_trade=activities_by_trade,
        editing=bool(activity_id)
    )

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
                role=form.role.data
            )
            
            # Set the password
            if form.password.data:
                user.set_password(form.password.data)
            else:
                # Default password is required
                flash('Password is required for new users', 'danger')
                users = User.query.order_by(User.role, User.name).all()
                return render_template('admin/users.html', form=form, users=users, editing=False, new_user=True)
            
            # Try to add the new user
            try:
                db.session.add(user)
                db.session.commit()
                flash('New user added successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding user: {str(e)}', 'danger')

        return redirect(url_for('manage_users'))

    # Check if we're editing a user
    user_id = request.args.get('edit')
    new_user = request.args.get('new') == 'true'
    
    if user_id:
        # Editing existing user
        user = User.query.get_or_404(user_id)
        form.name.data = user.name
        form.email.data = user.email
        form.role.data = user.role
        editing = True
    else:
        # Not editing (either viewing or adding new)
        editing = False

    # Get all users for display
    users = User.query.order_by(User.role, User.name).all()

    return render_template('admin/users.html', form=form, users=users, editing=editing, new_user=new_user)

@app.route('/admin/reports', methods=['GET', 'POST'])
@login_required
@admin_required
def generate_reports():
    form = ReportForm()

    if form.validate_on_submit():
        # Get form data
        report_type = form.report_type.data
        start_date = form.start_date.data
        end_date = form.end_date.data
        job_id = form.job_id.data if form.job_id.data != 0 else None
        user_id = form.user_id.data if form.user_id.data != 0 else None
        report_format = form.format.data

        # Build the base query
        query = db.session.query(
            TimeEntry.id,
            TimeEntry.date,
            TimeEntry.hours,
            TimeEntry.approved,
            User.name.label('worker_name'),
            Job.job_code,
            Job.description.label('job_description'),
            LaborActivity.name.label('activity'),
            LaborActivity.trade_category
        ).join(
            User, TimeEntry.user_id == User.id
        ).join(
            Job, TimeEntry.job_id == Job.id
        ).join(
            LaborActivity, TimeEntry.labor_activity_id == LaborActivity.id
        ).filter(
            TimeEntry.date >= start_date,
            TimeEntry.date <= end_date
        )

        # Apply filters
        if job_id:
            query = query.filter(TimeEntry.job_id == job_id)

        if user_id:
            query = query.filter(TimeEntry.user_id == user_id)

        # Order the results
        if report_type == 'payroll':
            query = query.order_by(User.name, TimeEntry.date)
        elif report_type == 'job_labor':
            query = query.order_by(Job.job_code, TimeEntry.date)
        else:  # employee_hours
            query = query.order_by(TimeEntry.date, User.name)

        # Execute the query
        results = query.all()

        # Create pandas dataframe from results
        columns = ['id', 'date', 'hours', 'approved', 'worker_name', 'job_code', 
                  'job_description', 'activity', 'trade_category']
        df = pd.DataFrame(results, columns=columns)

        # Convert DataFrame to list of dictionaries for report generation
        data_dicts = df.to_dict('records')

        # Get common info for both formats
        report_titles = {
            'payroll': 'Payroll Report',
            'job_labor': 'Job Labor Report',
            'employee_hours': 'Employee Hours Report'
        }
        report_title = f"{report_titles.get(report_type, 'Report')} ({start_date.strftime('%m/%d/%Y')} to {end_date.strftime('%m/%d/%Y')})"

        # Determine file delivery method (download or email)
        delivery_method = form.delivery_method.data

        # Generate report file
        if report_format == 'csv':
            # Generate CSV report
            csv_data = utils.generate_csv_report(data_dicts, columns)

            # Generate filename
            filename = f"{report_type}_{start_date.strftime('%m%d%Y')}_{end_date.strftime('%m%d%Y')}.csv"

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
                    attachment_mimetype='text/csv'
                )

                if email_sent:
                    flash(f'Report successfully emailed to {recipient_email}', 'success')
                else:
                    flash('Failed to send email. Please check SMTP settings.', 'danger')

                return redirect(url_for('generate_reports'))
            else:
                # Store the file data in session for download
                session['report_data'] = csv_data.encode('utf-8')
                session['report_filename'] = filename
                session['report_mimetype'] = 'text/csv'
                
                # Set a flash message
                flash('Report generated successfully. Download will begin shortly.', 'success')
                
                # Redirect to download endpoint
                return redirect(url_for('download_report'))
        else:  # PDF format
            # Generate PDF report
            pdf_buffer = utils.generate_pdf_report(data_dicts, columns, title=report_title)

            # Generate filename
            filename = f"{report_type}_{start_date.strftime('%m%d%Y')}_{end_date.strftime('%m%d%Y')}.pdf"

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

                # Send email with PDF attachment
                email_sent = utils.send_email_with_attachment(
                    recipient_email=recipient_email,
                    subject=f"Construction Timesheet: {report_title}",
                    body=email_body,
                    attachment_data=pdf_buffer,
                    attachment_filename=filename,
                    attachment_mimetype='application/pdf'
                )

                if email_sent:
                    flash(f'Report successfully emailed to {recipient_email}', 'success')
                else:
                    flash('Failed to send email. Please check SMTP settings or credentials.', 'danger')

                return redirect(url_for('generate_reports'))
            else:
                # Store the file data in session for download
                session['report_data'] = pdf_buffer.getvalue()
                session['report_filename'] = filename
                session['report_mimetype'] = 'application/pdf'
                
                # Set a flash message
                flash('Report generated successfully. Download will begin shortly.', 'success')
                
                # Redirect to download endpoint
                return redirect(url_for('download_report'))

    # Default dates to current week
    if not form.start_date.data:
        today = date.today()
        form.start_date.data = get_week_start(today)
        form.end_date.data = form.start_date.data + timedelta(days=6)

    return render_template('admin/reports.html', form=form)

# API routes for AJAX calls
@app.route('/api/labor_activities/<int:job_id>')
@login_required
def get_labor_activities(job_id):
    job = Job.query.get_or_404(job_id)
    activities = LaborActivity.query.filter_by(trade_category=job.trade_type).all()

    # Return JSON response with labor activities for the job's trade type
    return jsonify([
        {'id': activity.id, 'name': activity.name}
        for activity in activities
    ])

@app.route('/api/time_entries/<date>/<int:job_id>')
@login_required
def get_time_entries(date, job_id):
    """API endpoint to get time entries for a specific date and job"""
    target_date = datetime.strptime(date, '%m/%d/%Y').date()

    entries = TimeEntry.query.filter(
        TimeEntry.user_id == current_user.id,
        TimeEntry.job_id == job_id,
        TimeEntry.date == target_date
    ).all()

    # Return JSON response with time entries
    return jsonify([
        {
            'id': entry.id,
            'labor_activity_id': entry.labor_activity_id,
            'hours': entry.hours,
            'notes': entry.notes
        }
        for entry in entries
    ])

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
    if 'report_data' not in session or 'report_filename' not in session or 'report_mimetype' not in session:
        flash('No report data found. Please generate a report first.', 'warning')
        return redirect(url_for('generate_reports'))
    
    # Create a template that will auto-download the file and then redirect back
    return render_template('download.html', 
                          filename=session['report_filename'],
                          mimetype=session['report_mimetype'],
                          return_url=url_for('generate_reports'))

@app.route('/get-report-file')
@login_required
def get_report_file():
    """Actual file download endpoint"""
    if 'report_data' not in session or 'report_filename' not in session or 'report_mimetype' not in session:
        flash('No report data found. Please generate a report first.', 'warning')
        return redirect(url_for('generate_reports'))
    
    # Get data from session
    report_data = session['report_data']
    filename = session['report_filename']
    mimetype = session['report_mimetype']
    
    # Create a BytesIO object from the data
    file_data = io.BytesIO(report_data)
    file_data.seek(0)
    
    # Check if this is an iframe request or direct navigation
    is_iframe = request.args.get('iframe', 'false') == 'true'
    
    # If direct navigation, show a page with a link back
    if not is_iframe and mimetype == 'application/pdf':
        return render_template('file_viewer.html', 
                              report_data=report_data,
                              filename=filename,
                              return_url=url_for('generate_reports'))
    
    # Send the file
    return send_file(
        file_data,
        mimetype=mimetype,
        as_attachment=True,
        download_name=filename
    )

@app.route('/debug')
def debug_route():
    """Debug route to test rendering and basic functionality"""
    form = LoginForm()
    return render_template('login.html', form=form)