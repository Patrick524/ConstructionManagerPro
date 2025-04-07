from app import db
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    """User model representing workers, foremen, and administrators"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='worker')  # worker, foreman, admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    time_entries = db.relationship('TimeEntry', foreign_keys='TimeEntry.user_id', backref='user', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_worker(self):
        return self.role == 'worker'
        
    def is_foreman(self):
        return self.role == 'foreman'
        
    def is_admin(self):
        return self.role == 'admin'
    
    def __repr__(self):
        return f'<User {self.name}>'

class Job(db.Model):
    """Job model representing construction projects"""
    id = db.Column(db.Integer, primary_key=True)
    job_code = db.Column(db.String(20), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='active')  # active, complete, on_hold
    trade_type = db.Column(db.String(50), default='drywall')  # drywall, plumbing, electrical, etc.
    foreman_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    foreman = db.relationship('User', foreign_keys=[foreman_id], backref='managed_jobs')
    time_entries = db.relationship('TimeEntry', backref='job', lazy='dynamic')
    weekly_approvals = db.relationship('WeeklyApprovalLock', backref='job', lazy='dynamic')
    
    def __repr__(self):
        return f'<Job {self.job_code}>'

class LaborActivity(db.Model):
    """Labor activity types for different trades"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    trade_category = db.Column(db.String(50), nullable=False, default='drywall')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    time_entries = db.relationship('TimeEntry', backref='labor_activity', lazy='dynamic')
    
    def __repr__(self):
        return f'<LaborActivity {self.name} ({self.trade_category})>'

class TimeEntry(db.Model):
    """Time entry records for workers"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    labor_activity_id = db.Column(db.Integer, db.ForeignKey('labor_activity.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    hours = db.Column(db.Float, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    approved = db.Column(db.Boolean, default=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    approver = db.relationship('User', foreign_keys=[approved_by], backref='approved_entries', lazy='joined')
    
    def __repr__(self):
        return f'<TimeEntry {self.user_id} - {self.date} - {self.hours}h>'

class WeeklyApprovalLock(db.Model):
    """Weekly approval locks to prevent modification after foreman approval"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    week_start = db.Column(db.Date, nullable=False)  # Monday of the approved week
    approved_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    approved_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    worker = db.relationship('User', foreign_keys=[user_id], backref='weekly_approvals', lazy='joined')
    approver = db.relationship('User', foreign_keys=[approved_by], backref='approved_weeks', lazy='joined')
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'job_id', 'week_start', name='unique_weekly_approval'),
    )
    
    def __repr__(self):
        return f'<WeeklyApprovalLock {self.user_id} - {self.job_id} - {self.week_start}>'
