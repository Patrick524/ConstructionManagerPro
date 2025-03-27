from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, FloatField
from wtforms import TextAreaField, HiddenField, DateField, BooleanField, FieldList, FormField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, NumberRange
from models import User, Job, LaborActivity
from datetime import date, timedelta

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
    labor_activity_1 = SelectField('Labor Activity', coerce=int)
    hours_1 = FloatField('Hours', validators=[NumberRange(min=0, max=12)])
    
    notes = TextAreaField('Notes')
    submit = SubmitField('Save Time Entry')
    
    def __init__(self, *args, **kwargs):
        super(TimeEntryForm, self).__init__(*args, **kwargs)
        # Populate job choices
        self.job_id.choices = [(job.id, f"{job.job_code} - {job.description}") 
                               for job in Job.query.filter_by(status='active').all()]
        
        # Set the first labor activity field with all activities
        self.labor_activity_1.choices = [(activity.id, activity.name) 
                                        for activity in LaborActivity.query.all()]

class ApprovalForm(FlaskForm):
    """Form for approving time entries"""
    week_start = DateField('Week Starting', validators=[DataRequired()])
    job_id = SelectField('Job', coerce=int, validators=[DataRequired()])
    user_id = SelectField('Worker', coerce=int, validators=[DataRequired()])
    approve_all = BooleanField('Approve All Entries')
    submit = SubmitField('Submit Approval')

class JobForm(FlaskForm):
    """Form for creating/editing jobs"""
    job_code = StringField('Job Code', validators=[DataRequired(), Length(min=2, max=20)])
    description = StringField('Description', validators=[DataRequired(), Length(min=2, max=255)])
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
    submit = SubmitField('Save Job')

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
    password = PasswordField('New Password (leave blank to keep current)')
    confirm_password = PasswordField('Confirm New Password', 
                                    validators=[EqualTo('password')])
    submit = SubmitField('Update User')

class WeeklyTimesheetForm(FlaskForm):
    """Form for weekly timesheet entry (more efficient interface)"""
    job_id = SelectField('Job', coerce=int, validators=[DataRequired()])
    labor_activity_id = SelectField('Labor Activity', coerce=int, validators=[DataRequired()])
    week_start = DateField('Week Starting', validators=[DataRequired()])
    
    # Daily hours fields
    monday_hours = FloatField('Monday', default=8.0, validators=[NumberRange(min=0, max=12)])
    tuesday_hours = FloatField('Tuesday', default=8.0, validators=[NumberRange(min=0, max=12)])
    wednesday_hours = FloatField('Wednesday', default=8.0, validators=[NumberRange(min=0, max=12)])
    thursday_hours = FloatField('Thursday', default=8.0, validators=[NumberRange(min=0, max=12)]) 
    friday_hours = FloatField('Friday', default=8.0, validators=[NumberRange(min=0, max=12)])
    saturday_hours = FloatField('Saturday', default=0.0, validators=[NumberRange(min=0, max=12)])
    sunday_hours = FloatField('Sunday', default=0.0, validators=[NumberRange(min=0, max=12)])
    
    notes = TextAreaField('Notes for the Week')
    submit = SubmitField('Save Weekly Timesheet')
    
    def __init__(self, *args, **kwargs):
        super(WeeklyTimesheetForm, self).__init__(*args, **kwargs)
        # Populate job choices
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
        if self.monday_hours.data is not None:
            total += self.monday_hours.data
        if self.tuesday_hours.data is not None:
            total += self.tuesday_hours.data
        if self.wednesday_hours.data is not None:
            total += self.wednesday_hours.data
        if self.thursday_hours.data is not None:
            total += self.thursday_hours.data
        if self.friday_hours.data is not None:
            total += self.friday_hours.data
        if self.saturday_hours.data is not None:
            total += self.saturday_hours.data
        if self.sunday_hours.data is not None:
            total += self.sunday_hours.data
        return total
        
class ReportForm(FlaskForm):
    """Form for generating reports"""
    report_type = SelectField('Report Type', choices=[
        ('payroll', 'Payroll Report'),
        ('job_labor', 'Job Labor Report'),
        ('employee_hours', 'Employee Hours Report')
    ], validators=[DataRequired()])
    start_date = DateField('Start Date', validators=[DataRequired()])
    end_date = DateField('End Date', validators=[DataRequired()])
    job_id = SelectField('Job (optional)', coerce=int)
    user_id = SelectField('Employee (optional)', coerce=int)
    format = SelectField('Format', choices=[
        ('csv', 'CSV'),
        ('pdf', 'PDF')
    ], validators=[DataRequired()])
    submit = SubmitField('Generate Report')
    
    def __init__(self, *args, **kwargs):
        super(ReportForm, self).__init__(*args, **kwargs)
        # Add a blank option for optional filters
        self.job_id.choices = [(0, 'All Jobs')] + [(job.id, f"{job.job_code} - {job.description}") 
                               for job in Job.query.all()]
        self.user_id.choices = [(0, 'All Employees')] + [(user.id, user.name) 
                                for user in User.query.filter_by(role='worker').all()]
