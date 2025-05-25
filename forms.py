from flask_wtf import FlaskForm as BaseFlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, FloatField as BaseFloatField, EmailField
from wtforms import TextAreaField, HiddenField, DateField, BooleanField, FieldList, FormField, SelectMultipleField
from wtforms import widgets, Field
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, NumberRange, Optional, StopValidation
from models import User, Job, LaborActivity
from datetime import date, timedelta

# Custom FloatField that properly handles empty inputs
class FloatField(BaseFloatField):
    """
    Custom FloatField that properly handles empty strings as None or 0 (based on flag)
    This provides the cleanest long-term fix for float conversion errors.
    """
    def __init__(self, label=None, validators=None, treat_empty_as_zero=False, **kwargs):
        self.treat_empty_as_zero = treat_empty_as_zero
        super(FloatField, self).__init__(label, validators, **kwargs)
    
    def process_formdata(self, valuelist):
        if not valuelist:
            self.data = 0.0 if self.treat_empty_as_zero else None
            return
            
        value = valuelist[0].strip()
        if value == '':
            self.data = 0.0 if self.treat_empty_as_zero else None
            return
            
        try:
            self.data = float(value)
        except ValueError:
            self.data = None
            raise ValueError(self.gettext('Not a valid float value'))
    
    def pre_validate(self, form):
        # Skip validation if data is None 
        if self.data is None:
            return
        super().pre_validate(form)
    
    # Override validate method to properly handle None values
    def validate(self, form, extra_validators=None):
        if self.data is None:
            # Skip validation entirely for None values
            return True
            
        # For non-None values, use the standard validation
        return super().validate(form, extra_validators)

class FlaskForm(BaseFlaskForm):
    """Custom base form class that adds automatic handling of empty values"""
    def __init__(self, *args, **kwargs):
        # If data is provided, process it before validation
        if len(args) > 0 and args[0] is not None and hasattr(self, 'process_data'):
            args = list(args)
            args[0] = self.process_data(args[0])
            args = tuple(args)
        super(FlaskForm, self).__init__(*args, **kwargs)

class LoginForm(FlaskForm):
    """Form for user login"""
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    """Form for user registration"""
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', 
                                    validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Role', choices=[
        ('worker', 'Field Worker'),
        ('foreman', 'Foreman'),
        ('admin', 'Administrator')
    ], validators=[DataRequired()])
    submit = SubmitField('Register')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered. Please use a different email.')

class TimeEntryForm(FlaskForm):
    """Form for daily time entry"""
    job_id = SelectField('Job', coerce=int, validators=[DataRequired()])
    date = DateField('Date', validators=[DataRequired()])
    
    # These are placeholder for dynamic labor activities - will be handled in JS
    labor_activity_1 = SelectField('Labor Activity', coerce=int, validators=[Optional()])
    hours_1 = FloatField('Hours', validators=[Optional(), NumberRange(min=0, max=12)], treat_empty_as_zero=True)
    
    notes = TextAreaField('Notes')
    submit = SubmitField('Save Time Entry')
    
    def __init__(self, *args, **kwargs):
        # Extract current_user if provided
        current_user = kwargs.pop('current_user', None)
        
        super(TimeEntryForm, self).__init__(*args, **kwargs)
        
        # Populate job choices based on user role
        if current_user and current_user.role == 'worker':
            # For workers, only show jobs they're assigned to
            self.job_id.choices = [(job.id, f"{job.job_code} - {job.description}") 
                                  for job in current_user.assigned_jobs.filter_by(status='active').all()]
        else:
            # For foremen and admins, show all active jobs
            self.job_id.choices = [(job.id, f"{job.job_code} - {job.description}") 
                                  for job in Job.query.filter_by(status='active').all()]
        
        # Set the first labor activity field with all activities
        self.labor_activity_1.choices = [(activity.id, activity.name) 
                                        for activity in LaborActivity.query.all()]
                                        
    def process_data(self, data):
        """Process form data before validation - convert empty strings to None for hours fields"""
        # Handle standard hours_1 field
        if 'hours_1' in data and data['hours_1'] == '':
            data['hours_1'] = None
            
        # Handle dynamically added hours_N fields
        for key in list(data.keys()):
            if key.startswith('hours_') and key != 'hours_1' and data[key] == '':
                data[key] = None
        
        return data

class ApprovalForm(FlaskForm):
    """Form for approving time entries"""
    week_start = DateField('Week Starting', validators=[DataRequired()])
    job_id = SelectField('Job', coerce=int, validators=[DataRequired()])
    user_id = SelectField('Worker', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Approve Timesheet')

class JobForm(FlaskForm):
    """Form for creating/editing jobs"""
    job_code = StringField('Job Code', validators=[DataRequired(), Length(min=2, max=20)])
    description = StringField('Description', validators=[DataRequired(), Length(min=2, max=255)])
    location = StringField('Job Location', validators=[Optional(), Length(max=255)])
    # Hidden fields for latitude and longitude
    latitude = FloatField('Latitude', validators=[Optional()], render_kw={'type': 'hidden'})
    longitude = FloatField('Longitude', validators=[Optional()], render_kw={'type': 'hidden'})
    status = SelectField('Status', choices=[
        ('active', 'Active'),
        ('complete', 'Complete'),
        ('on_hold', 'On Hold')
    ], validators=[DataRequired()])
    trade_type = SelectField('Primary Trade', choices=[
        ('drywall', 'Drywall'),
        ('electrical', 'Electrical'),
        ('plumbing', 'Plumbing'),
        ('carpentry', 'Carpentry'),
        ('painting', 'Painting'),
        ('masonry', 'Masonry'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    foreman_id = SelectField('Assign Foreman', coerce=int, validators=[Optional()])
    submit = SubmitField('Save Job')
    
    def __init__(self, *args, **kwargs):
        super(JobForm, self).__init__(*args, **kwargs)
        from models import User
        
        # Populate foreman choices
        foremen = User.query.filter_by(role='foreman').all()
        self.foreman_id.choices = [(0, '-- Select Foreman --')] + [(f.id, f.name) for f in foremen]

class TradeForm(FlaskForm):
    """Form for creating/editing trades"""
    name = StringField('Trade Name', validators=[DataRequired(), Length(min=2, max=50)])
    is_active = BooleanField('Enabled', default=True)
    submit = SubmitField('Save Trade')

class LaborActivityForm(FlaskForm):
    """Form for creating/editing labor activities"""
    name = StringField('Activity Name', validators=[DataRequired(), Length(min=2, max=100)])
    trade_category = SelectField('Trade Category', choices=[
        ('drywall', 'Drywall'),
        ('electrical', 'Electrical'),
        ('plumbing', 'Plumbing'),
        ('carpentry', 'Carpentry'),
        ('painting', 'Painting'),
        ('masonry', 'Masonry'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    trade_id = SelectField('Trade', coerce=int, validators=[Optional()])
    is_active = BooleanField('Enabled', default=True)
    submit = SubmitField('Save Activity')

class UserManagementForm(FlaskForm):
    """Form for admin to edit users"""
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    role = SelectField('Role', choices=[
        ('worker', 'Field Worker'),
        ('foreman', 'Foreman'),
        ('admin', 'Administrator')
    ], validators=[DataRequired()])
    burden_rate = FloatField('Burden Rate ($/hour)', validators=[Optional(), NumberRange(min=0, max=999.99)], 
                            render_kw={'step': '0.01', 'placeholder': 'Enter hourly burden rate'})
    use_clock_in = BooleanField('Use Clock In/Out System', default=False)
    password = PasswordField('New Password (leave blank to keep current)')
    confirm_password = PasswordField('Confirm New Password', 
                                    validators=[EqualTo('password')])
    submit = SubmitField('Update User')
    
    def validate_burden_rate(self, field):
        """Validate burden rate - required for field workers, optional for others"""
        if self.role.data == 'worker' and (field.data is None or field.data <= 0):
            raise ValidationError('Burden rate is required for Field Workers and must be greater than $0.')

class WeeklyTimesheetForm(FlaskForm):
    """Form for weekly timesheet entry (more efficient interface)"""
    job_id = SelectField('Job', coerce=int, validators=[DataRequired()])
    labor_activity_id = SelectField('Labor Activity', coerce=int, validators=[DataRequired()])
    week_start = DateField('Week Starting', validators=[DataRequired()])
    
    # Daily hours fields with improved validation that properly accepts empty values
    # treat_empty_as_zero=True ensures empty inputs become 0, which is a safe default
    # Removed max=12 constraint to allow custom validation logic to handle daily limits
    monday_hours = FloatField('Monday', validators=[Optional(), NumberRange(min=0)], treat_empty_as_zero=True)
    tuesday_hours = FloatField('Tuesday', validators=[Optional(), NumberRange(min=0)], treat_empty_as_zero=True)
    wednesday_hours = FloatField('Wednesday', validators=[Optional(), NumberRange(min=0)], treat_empty_as_zero=True)
    thursday_hours = FloatField('Thursday', validators=[Optional(), NumberRange(min=0)], treat_empty_as_zero=True) 
    friday_hours = FloatField('Friday', validators=[Optional(), NumberRange(min=0)], treat_empty_as_zero=True)
    saturday_hours = FloatField('Saturday', validators=[Optional(), NumberRange(min=0)], treat_empty_as_zero=True)
    sunday_hours = FloatField('Sunday', validators=[Optional(), NumberRange(min=0)], treat_empty_as_zero=True)
    
    notes = TextAreaField('Notes for the Week')
    submit = SubmitField('Save Weekly Timesheet')
    
    def __init__(self, *args, **kwargs):
        # Extract current_user if provided
        current_user = kwargs.pop('current_user', None)
        
        super(WeeklyTimesheetForm, self).__init__(*args, **kwargs)
        
        # Populate job choices based on user role
        if current_user and current_user.role == 'worker':
            # For workers, only show jobs they're assigned to
            self.job_id.choices = [(job.id, f"{job.job_code} - {job.description}") 
                                  for job in current_user.assigned_jobs.filter_by(status='active').all()]
        else:
            # For foremen and admins, show all active jobs
            self.job_id.choices = [(job.id, f"{job.job_code} - {job.description}") 
                                  for job in Job.query.filter_by(status='active').all()]
        
        # Default to current week's Monday if no date is provided
        if not self.week_start.data:
            today = date.today()
            # Calculate the most recent Monday (current week's start)
            self.week_start.data = today - timedelta(days=today.weekday())
            
    def get_total_hours(self):
        """Calculate total hours for the week"""
        total = 0
        # Helper function to safely convert None or empty string to 0
        def safe_hours(val):
            if val in [None, '']:
                return 0
            return float(val)
            
        total += safe_hours(self.monday_hours.data)
        total += safe_hours(self.tuesday_hours.data)
        total += safe_hours(self.wednesday_hours.data)
        total += safe_hours(self.thursday_hours.data)
        total += safe_hours(self.friday_hours.data)
        total += safe_hours(self.saturday_hours.data)
        total += safe_hours(self.sunday_hours.data)
        return total
        
    def process_data(self, data):
        """Process form data before validation - convert empty strings to None for hours fields"""
        for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
            field_name = f'{day}_hours'
            if field_name in data and data[field_name] == '':
                data[field_name] = None
        return data
        
class ClockInForm(FlaskForm):
    """Form for clock in"""
    job_id = SelectField('Job', coerce=int, validators=[DataRequired()])
    labor_activity_id = SelectField('Labor Activity', coerce=int, validators=[DataRequired()])
    notes = TextAreaField('Notes (optional)')
    submit = SubmitField('Clock In')
    
    def __init__(self, *args, **kwargs):
        # Extract current_user if provided
        current_user = kwargs.pop('current_user', None)
        
        super(ClockInForm, self).__init__(*args, **kwargs)
        
        # Populate job choices based on user role
        if current_user and current_user.role == 'worker':
            # For workers, only show jobs they're assigned to
            self.job_id.choices = [(job.id, f"{job.job_code} - {job.description}") 
                                  for job in current_user.assigned_jobs.filter_by(status='active').all()]
        else:
            # For foremen and admins, show all active jobs
            self.job_id.choices = [(job.id, f"{job.job_code} - {job.description}") 
                                  for job in Job.query.filter_by(status='active').all()]
        
        # Default to the first labor activity, but this will be dynamically updated via JavaScript
        # Only show active labor activities
        activities = LaborActivity.query.filter_by(is_active=True).all()
        if activities:
            self.labor_activity_id.choices = [(activity.id, activity.name) for activity in activities]
        else:
            self.labor_activity_id.choices = []

class ClockOutForm(FlaskForm):
    """Form for clock out"""
    notes = TextAreaField('Notes (optional)')
    submit = SubmitField('Clock Out')

class ReportForm(FlaskForm):
    """Form for generating reports"""
    report_type = SelectField('Report Type', choices=[
        ('payroll', 'Payroll Report'),
        ('job_labor', 'Job Labor Report'),
        ('employee_hours', 'Employee Hours Report'),
        ('job_cost', 'Job Cost Report')
    ], validators=[DataRequired()])
    start_date = DateField('Start Date', validators=[DataRequired()])
    end_date = DateField('End Date', validators=[DataRequired()])
    job_id = SelectField('Job (optional)', coerce=int)
    user_id = SelectField('Employee (optional)', coerce=int)
    format = SelectField('Format', choices=[
        ('csv', 'CSV'),
        ('pdf', 'PDF')
    ], validators=[DataRequired()])
    delivery_method = SelectField('Delivery Method', choices=[
        ('download', 'Download'),
        ('email', 'Email')
    ], default='download', validators=[DataRequired()])
    recipient_email = EmailField('Recipient Email (if emailing)')
    submit = SubmitField('Generate Report')
    
    def __init__(self, *args, **kwargs):
        super(ReportForm, self).__init__(*args, **kwargs)
        # Add a blank option for optional filters
        self.job_id.choices = [(0, 'All Jobs')] + [(job.id, f"{job.job_code} - {job.description}") 
                               for job in Job.query.all()]
        self.user_id.choices = [(0, 'All Employees')] + [(user.id, user.name) 
                                for user in User.query.filter_by(role='worker').all()]
                                
    def validate_recipient_email(self, field):
        """Validate recipient email when email delivery is selected"""
        if self.delivery_method.data == 'email' and not field.data:
            raise ValidationError('Email address is required when email delivery is selected.')

class JobWorkersForm(FlaskForm):
    """Form for managing worker assignments to jobs"""
    job_id = SelectField('Job', coerce=int, validators=[DataRequired()])
    workers = SelectMultipleField('Assign Workers', coerce=int, validators=[Optional()])
    submit = SubmitField('Update Worker Assignments')
    
    def __init__(self, *args, **kwargs):
        super(JobWorkersForm, self).__init__(*args, **kwargs)
        # Populate job choices
        self.job_id.choices = [(job.id, f"{job.job_code} - {job.description}") 
                              for job in Job.query.filter(Job.status != 'complete').order_by(Job.job_code).all()]
        # Populate worker choices
        self.workers.choices = [(worker.id, worker.name) 
                               for worker in User.query.filter_by(role='worker').order_by(User.name).all()]
