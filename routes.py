import os
import csv
import io
from datetime import datetime, timedelta, date
from functools import wraps
from flask import render_template, redirect, url_for, flash, request, jsonify, send_file
from flask_login import login_user, logout_user, current_user, login_required
from app import app, db
from models import User, Job, LaborActivity, TimeEntry, WeeklyApprovalLock
from forms import (LoginForm, RegistrationForm, TimeEntryForm, ApprovalForm, JobForm,
                  LaborActivityForm, UserManagementForm, ReportForm, WeeklyTimesheetForm)
import pandas as pd

# Context processor to provide the current datetime to all templates
@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}

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
            
        return redirect(url_for('worker_history'))
    
    # Get job_id from URL parameters if provided
    if job_id and not form.job_id.data:
        form.job_id.data = int(job_id)
        
    # If labor_activity_id is in the URL, use it
    labor_activity_id = request.args.get('labor_activity_id')
    if labor_activity_id:
        form.labor_activity_id.data = int(labor_activity_id)
    
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
        
        # If form is being loaded and there are existing entries, populate the form
        if existing_entries:
            print(f"DEBUG: Setting form values from existing entries")
            # Set all fields to 0 first to clear default values
            form.monday_hours.data = 0
            form.tuesday_hours.data = 0
            form.wednesday_hours.data = 0
            form.thursday_hours.data = 0
            form.friday_hours.data = 0
            form.saturday_hours.data = 0
            form.sunday_hours.data = 0
            
            # Find entries for each day and populate hours
            for entry in existing_entries:
                print(f"DEBUG: Entry date {entry.date}, hours {entry.hours}")
                day_index = (entry.date - week_start).days
                print(f"DEBUG: Day index {day_index}")
                if day_index == 0:
                    form.monday_hours.data = entry.hours
                elif day_index == 1:
                    form.tuesday_hours.data = entry.hours
                elif day_index == 2:
                    form.wednesday_hours.data = entry.hours
                elif day_index == 3:
                    form.thursday_hours.data = entry.hours
                elif day_index == 4:
                    form.friday_hours.data = entry.hours
                elif day_index == 5:
                    form.saturday_hours.data = entry.hours
                elif day_index == 6:
                    form.sunday_hours.data = entry.hours
                
            # Populate notes from any entry (they should be the same)
            if existing_entries:
                form.notes.data = existing_entries[0].notes
                
            print(f"DEBUG: Form values after population: M={form.monday_hours.data}, T={form.tuesday_hours.data}, W={form.wednesday_hours.data}")
        else:
            print("DEBUG: No existing entries found to populate form")
    elif form.job_id.data:
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
            
            # Reset all hours to zero first
            form.monday_hours.data = 0
            form.tuesday_hours.data = 0
            form.wednesday_hours.data = 0
            form.thursday_hours.data = 0
            form.friday_hours.data = 0
            form.saturday_hours.data = 0
            form.sunday_hours.data = 0
            
            # Find entries for each day and populate hours
            for entry in entries:
                print(f"DEBUG: Entry date {entry.date}, hours {entry.hours}")
                day_index = (entry.date - week_start).days
                print(f"DEBUG: Day index {day_index}")
                if day_index == 0:
                    form.monday_hours.data = entry.hours
                elif day_index == 1:
                    form.tuesday_hours.data = entry.hours
                elif day_index == 2:
                    form.wednesday_hours.data = entry.hours
                elif day_index == 3:
                    form.thursday_hours.data = entry.hours
                elif day_index == 4:
                    form.friday_hours.data = entry.hours
                elif day_index == 5:
                    form.saturday_hours.data = entry.hours
                elif day_index == 6:
                    form.sunday_hours.data = entry.hours
            
            # Populate notes from any entry (they should be the same)
            if entries:
                form.notes.data = entries[0].notes
                
            print(f"DEBUG: Form values after population from job entries: M={form.monday_hours.data}, T={form.tuesday_hours.data}, W={form.wednesday_hours.data}")
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
        return redirect(url_for('worker_history'))
    
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
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
    if not end_date:
        end_date = start_date + timedelta(days=6)
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
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
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
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
    
    # Default to current week if no week start provided
    if not form.week_start.data:
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
        flash(f'This week was already approved by {existing_approval.approver.name} on {existing_approval.approved_at.strftime("%Y-%m-%d %H:%M")}. Time entries cannot be modified.', 'warning')
        return redirect(url_for('foreman_dashboard'))
    
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
        return redirect(url_for('foreman_dashboard'))
    
    # Load existing entries for this week with eager loading of labor_activity
    existing_entries = TimeEntry.query.filter(
        TimeEntry.user_id == user_id,
        TimeEntry.job_id == job_id,
        TimeEntry.date >= week_start,
        TimeEntry.date <= week_end
    ).options(db.joinedload(TimeEntry.labor_activity)).all()
    
    # If form is being loaded and there are existing entries, populate the form
    if not form.is_submitted() and existing_entries:
        # Group by labor_activity_id
        entries_by_activity = {}
        for entry in existing_entries:
            if entry.labor_activity_id not in entries_by_activity:
                entries_by_activity[entry.labor_activity_id] = []
            entries_by_activity[entry.labor_activity_id].append(entry)
        
        # For simplicity, just use the first activity group to populate the form
        if entries_by_activity:
            # Get the first activity and its entries
            activity_id, entries = next(iter(entries_by_activity.items()))
            form.labor_activity_id.data = activity_id
            
            # Find entries for each day and populate hours
            for entry in entries:
                day_index = (entry.date - week_start).days
                if day_index == 0:
                    form.monday_hours.data = entry.hours
                elif day_index == 1:
                    form.tuesday_hours.data = entry.hours
                elif day_index == 2:
                    form.wednesday_hours.data = entry.hours
                elif day_index == 3:
                    form.thursday_hours.data = entry.hours
                elif day_index == 4:
                    form.friday_hours.data = entry.hours
                elif day_index == 5:
                    form.saturday_hours.data = entry.hours
                elif day_index == 6:
                    form.sunday_hours.data = entry.hours
            
            # Populate notes from any entry (they should be the same)
            if entries:
                form.notes.data = entries[0].notes
    
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
    
    # Default to current week if no week start provided
    if not form.week_start.data:
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
        flash(f'This week was already approved by {existing_approval.approver.name} on {existing_approval.approved_at.strftime("%Y-%m-%d %H:%M")}', 'warning')
        return redirect(url_for('foreman_dashboard'))
    
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
        return redirect(url_for('foreman_dashboard'))
    
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
            job.status = form.status.data
            job.trade_type = form.trade_type.data
            flash('Job updated successfully!', 'success')
        else:
            # Create new job
            job = Job(
                job_code=form.job_code.data,
                description=form.description.data,
                status=form.status.data,
                trade_type=form.trade_type.data
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
        form.status.data = job.status
        form.trade_type.data = job.trade_type
    
    # Get all jobs for display
    jobs = Job.query.order_by(Job.created_at.desc()).all()
    
    return render_template('admin/jobs.html', form=form, jobs=jobs, editing=bool(job_id))

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
            
        return redirect(url_for('manage_users'))
    
    # Check if we're editing a user
    user_id = request.args.get('edit')
    if user_id:
        user = User.query.get_or_404(user_id)
        form.name.data = user.name
        form.email.data = user.email
        form.role.data = user.role
    
    # Get all users for display
    users = User.query.order_by(User.role, User.name).all()
    
    return render_template('admin/users.html', form=form, users=users, editing=bool(user_id))

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
        
        # Generate report file
        if report_format == 'csv':
            output = io.StringIO()
            df.to_csv(output, index=False)
            output.seek(0)
            
            # Generate filename
            filename = f"{report_type}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"
            
            return send_file(
                io.BytesIO(output.getvalue().encode('utf-8')),
                mimetype='text/csv',
                as_attachment=True,
                download_name=filename
            )
        else:  # PDF not directly implemented, could use a library like WeasyPrint
            flash('PDF generation is not implemented in this version.', 'warning')
            return redirect(url_for('generate_reports'))
    
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
    
    return jsonify([
        {'id': activity.id, 'name': activity.name}
        for activity in activities
    ])

@app.route('/api/time_entries/<date>/<int:job_id>')
@login_required
def get_time_entries(date, job_id):
    target_date = datetime.strptime(date, '%Y-%m-%d').date()
    
    entries = TimeEntry.query.filter(
        TimeEntry.user_id == current_user.id,
        TimeEntry.job_id == job_id,
        TimeEntry.date == target_date
    ).all()
    
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
    
@app.route('/debug')
def debug_route():
    """Debug route to test rendering and basic functionality"""
    form = LoginForm()
    return render_template('login.html', form=form)
