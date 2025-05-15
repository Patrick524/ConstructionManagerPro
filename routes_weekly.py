@app.route('/worker/weekly', methods=['GET', 'POST'])
@login_required
@worker_required
def worker_weekly_timesheet():
    """Weekly timesheet view allowing workers to enter time for an entire week at once"""
    print("DEBUG: Weekly timesheet form submission - Request method:", request.method)
    print("DEBUG: Form data:", request.form)
    
    form = WeeklyTimesheetForm()

    # Default to current week if no week start provided
    if not form.week_start.data:
        # Calculate the start of the current week (Monday)
        today = date.today()
        
        # Get start_date from query parameters if provided
        start_date = request.args.get('start_date')
        week_offset = request.args.get('week_offset', 0)
        
        try:
            week_offset = int(week_offset)
        except (ValueError, TypeError):
            week_offset = 0
        
        if start_date:
            try:
                # Parse start_date (MM/DD/YYYY)
                parsed_date = datetime.strptime(start_date, '%m/%d/%Y').date()
                # Find the Monday of that week
                week_start = parsed_date - timedelta(days=parsed_date.weekday())
            except ValueError:
                # If parsing fails, use the current week
                week_start = today - timedelta(days=today.weekday())
        else:
            # Use the current week
            week_start = today - timedelta(days=today.weekday())
        
        # Apply week offset
        week_start = week_start + timedelta(weeks=week_offset)
        form.week_start.data = week_start

    # Define week range and dates
    week_start = form.week_start.data
    week_end = week_start + timedelta(days=6)
    week_dates = [week_start + timedelta(days=i) for i in range(7)]
    
    # Get all time entries for the week regardless of job
    all_week_entries = TimeEntry.query.filter(
        TimeEntry.user_id == current_user.id,
        TimeEntry.date >= week_start,
        TimeEntry.date <= week_end
    ).options(
        db.joinedload(TimeEntry.job),
        db.joinedload(TimeEntry.labor_activity)
    ).order_by(TimeEntry.date, TimeEntry.job_id, TimeEntry.labor_activity_id).all()
    
    print(f"DEBUG: Found {len(all_week_entries)} total entries for the week")
    
    # Build hours map by (date, job_id, labor_activity_id)
    hours_map = {}
    for entry in all_week_entries:
        key = (entry.date, entry.job_id, entry.labor_activity_id)
        hours_map[key] = entry.hours
    
    # Calculate daily totals
    daily_totals = {}
    for day in week_dates:
        daily_total = sum(hours for (date, _, _), hours in hours_map.items() if date == day)
        daily_totals[day] = daily_total

    # Get jobs for dropdown
    form.job_id.choices = [(0, '-- Select Job --')]
    active_jobs = Job.query.filter(Job.status != 'complete').order_by(Job.job_code).all()
    form.job_id.choices.extend([(j.id, f"{j.job_code} - {j.description}") for j in active_jobs])

    # Check if we're loading a specific job's labor activities
    job_id = request.args.get('job_id')
    if job_id:
        job = Job.query.get_or_404(int(job_id))
        # Populate labor activities for this job's trade type
        form.labor_activity_id.choices = [(0, '-- Select Activity --')]
        form.labor_activity_id.choices.extend([
            (activity.id, activity.name) 
            for activity in LaborActivity.query.filter_by(trade_category=job.trade_type, is_active=True).all()
        ])
        form.job_id.data = int(job_id)
    else:
        # Default to all active activities if no job selected
        form.labor_activity_id.choices = [(0, '-- Select Activity --')]
        form.labor_activity_id.choices.extend([
            (activity.id, activity.name) 
            for activity in LaborActivity.query.filter_by(is_active=True).all()
        ])

    # Handle form submission for adding/updating time entries
    if form.validate_on_submit():
        # Process form data
        job_id = form.job_id.data
        labor_activity_id = form.labor_activity_id.data
        notes = form.notes.data
        
        if job_id == 0 or labor_activity_id == 0:
            flash("Please select both a job and a labor activity", "warning")
            return redirect(url_for('worker_weekly_timesheet', start_date=week_start.strftime('%m/%d/%Y')))
        
        # Process each day of the week
        days_data = {
            'monday': form.monday_hours.data,
            'tuesday': form.tuesday_hours.data,
            'wednesday': form.wednesday_hours.data,
            'thursday': form.thursday_hours.data,
            'friday': form.friday_hours.data,
            'saturday': form.saturday_hours.data,
            'sunday': form.sunday_hours.data
        }
        
        entries_updated = 0
        
        try:
            # Use a single transaction
            with db.session.begin():
                for day_idx, (day_name, hours) in enumerate(days_data.items()):
                    # Skip days with zero or null hours
                    if not hours or hours <= 0:
                        continue
                        
                    day_date = week_start + timedelta(days=day_idx)
                    
                    # Use upsert pattern with the unique constraint we added
                    stmt = db.text("""
                        INSERT INTO time_entry (user_id, job_id, labor_activity_id, date, hours, notes, created_at)
                        VALUES (:user_id, :job_id, :labor_activity_id, :date, :hours, :notes, :created_at)
                        ON CONFLICT (user_id, job_id, date) DO UPDATE
                        SET hours = :hours, notes = :notes, labor_activity_id = :labor_activity_id
                        WHERE time_entry.approved = FALSE
                    """)
                    
                    result = db.session.execute(stmt, {
                        'user_id': current_user.id,
                        'job_id': job_id,
                        'labor_activity_id': labor_activity_id,
                        'date': day_date,
                        'hours': min(hours, 24.0),  # Cap at 24 hours per day
                        'notes': notes,
                        'created_at': datetime.utcnow()
                    })
                    
                    if result.rowcount > 0:
                        entries_updated += 1
            
            if entries_updated > 0:
                flash(f"Weekly timesheet saved successfully! Updated {entries_updated} days.", "success")
            else:
                flash("No changes were made. Make sure there are hours entered and the entries aren't already approved.", "info")
                
        except Exception as e:
            flash(f"Error saving timesheet: {str(e)}", "danger")
            print(f"ERROR: {str(e)}")
            db.session.rollback()
            
        return redirect(url_for(
            'worker_weekly_timesheet', 
            start_date=week_start.strftime('%m/%d/%Y'),
            job_id=job_id
        ))
        
    # If labor_activity_id was provided in query params
    labor_activity_id = request.args.get('labor_activity_id')
    if labor_activity_id:
        form.labor_activity_id.data = int(labor_activity_id)
        
    # If job_id and labor_activity_id are set, populate form with existing data
    if form.job_id.data and form.job_id.data != 0 and form.labor_activity_id.data and form.labor_activity_id.data != 0:
        # Reset all day fields to zero first
        form.monday_hours.data = 0
        form.tuesday_hours.data = 0
        form.wednesday_hours.data = 0
        form.thursday_hours.data = 0
        form.friday_hours.data = 0
        form.saturday_hours.data = 0
        form.sunday_hours.data = 0
        
        # Map day indices to form fields
        day_fields = [
            form.monday_hours, form.tuesday_hours, form.wednesday_hours, 
            form.thursday_hours, form.friday_hours, form.saturday_hours, form.sunday_hours
        ]
        
        # Find entries for this job/activity and populate the form
        for i, day in enumerate(week_dates):
            key = (day, form.job_id.data, form.labor_activity_id.data)
            if key in hours_map:
                day_fields[i].data = hours_map[key]
        
        # Use notes from any matching entry
        for entry in all_week_entries:
            if entry.job_id == form.job_id.data and entry.labor_activity_id == form.labor_activity_id.data:
                form.notes.data = entry.notes
                break
                
    # Group entries by job and activity for the editable grid
    jobs_data = {}
    for entry in all_week_entries:
        job_key = (entry.job_id, entry.job.job_code, entry.job.description)
        activity_key = (entry.labor_activity_id, entry.labor_activity.name)
        
        if job_key not in jobs_data:
            jobs_data[job_key] = {}
        
        if activity_key not in jobs_data[job_key]:
            jobs_data[job_key][activity_key] = {
                'days': {day: 0 for day in week_dates},
                'total': 0,
                'approved': False,
                'notes': entry.notes
            }
        
        jobs_data[job_key][activity_key]['days'][entry.date] = entry.hours
        jobs_data[job_key][activity_key]['total'] += entry.hours
        
        # If any entry for this job/activity is approved, mark the whole row as approved
        if entry.approved:
            jobs_data[job_key][activity_key]['approved'] = True

    return render_template(
        'worker/weekly_timesheet.html', 
        form=form,
        all_week_entries=all_week_entries,
        hours_map=hours_map,
        daily_totals=daily_totals,
        week_dates=week_dates,
        week_start=week_start,
        jobs_data=jobs_data
    )