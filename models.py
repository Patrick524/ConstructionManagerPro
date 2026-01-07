from app import db
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# Association table for many-to-many relationship between Job and User (worker)
job_workers = db.Table('job_workers',
    db.Column('job_id', db.Integer, db.ForeignKey('job.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('assigned_at', db.DateTime, default=datetime.utcnow)
)

# Association table for many-to-many relationship between Job and Trade
job_trades = db.Table('job_trades',
    db.Column('job_id', db.Integer, db.ForeignKey('job.id'), primary_key=True),
    db.Column('trade_id', db.Integer, db.ForeignKey('trade.id'), primary_key=True),
    db.Column('assigned_at', db.DateTime, default=datetime.utcnow)
)

# Association table for many-to-many relationship between User and Trade (qualified trades)
user_trades = db.Table('user_trades',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('trade_id', db.Integer, db.ForeignKey('trade.id'), primary_key=True),
    db.Column('qualified_at', db.DateTime, default=datetime.utcnow)
)

class User(UserMixin, db.Model):
    """User model representing workers, foremen, and administrators"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='worker')  # worker, foreman, admin
    use_clock_in = db.Column(db.Boolean, default=False)  # Whether the worker uses clock in/out
    burden_rate = db.Column(db.Numeric(10, 2), nullable=True)  # Hourly burden rate for job costing ($/hour)
    active = db.Column(db.Boolean, default=True)  # Whether the employee is active/inactive
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    time_entries = db.relationship('TimeEntry', foreign_keys='TimeEntry.user_id', backref='user', lazy='dynamic')
    clock_sessions = db.relationship('ClockSession', backref='user', lazy='dynamic')
    # Jobs assigned to this worker (many-to-many)
    assigned_jobs = db.relationship('Job', 
                                secondary=job_workers,
                                backref=db.backref('assigned_workers', lazy='dynamic'),
                                lazy='dynamic')
    # Qualified trades for this worker (many-to-many)
    qualified_trades = db.relationship('Trade',
                                     secondary=user_trades,
                                     backref=db.backref('qualified_workers', lazy='dynamic'),
                                     lazy='dynamic')
    
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

class Trade(db.Model):
    """Trade categories for construction work"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)  # e.g. drywall, electrical, plumbing
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Trade {self.name}>'

class Job(db.Model):
    """Job model representing construction projects"""
    id = db.Column(db.Integer, primary_key=True)
    job_code = db.Column(db.String(20), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    location = db.Column(db.String(255), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), default='active')  # active, complete, on_hold
    trade_type = db.Column(db.String(50), default='drywall')  # drywall, plumbing, electrical, etc.
    foreman_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    time_entries = db.relationship('TimeEntry', backref='job', lazy='dynamic')
    weekly_approvals = db.relationship('WeeklyApprovalLock', backref='job', lazy='dynamic')
    foreman = db.relationship('User', foreign_keys=[foreman_id], backref='managed_jobs', lazy='joined')
    # Many-to-many relationship with trades
    trades = db.relationship('Trade',
                           secondary=job_trades,
                           backref=db.backref('jobs', lazy='dynamic'),
                           lazy='dynamic')
    
    def __repr__(self):
        return f'<Job {self.job_code}>'

class LaborActivity(db.Model):
    """Labor activity types for different trades"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    trade_category = db.Column(db.String(50), nullable=False, default='drywall')
    trade_id = db.Column(db.Integer, db.ForeignKey('trade.id'), nullable=True)  # Link to Trade model
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)  # New field to enable/disable activities
    
    # Relationships
    time_entries = db.relationship('TimeEntry', backref='labor_activity', lazy='dynamic')
    trade = db.relationship('Trade', backref='labor_activities', lazy='joined')
    
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
    
    # Add unique constraint for (user_id, job_id, labor_activity_id, date) to support upsert
    __table_args__ = (
        db.UniqueConstraint('user_id', 'job_id', 'labor_activity_id', 'date', name='unique_time_entry'),
        db.CheckConstraint('hours BETWEEN 0 AND 24', name='check_hours_range'),
    )
    
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
        
class ClockSession(db.Model):
    """Clock in/out session records for workers"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    labor_activity_id = db.Column(db.Integer, db.ForeignKey('labor_activity.id'), nullable=False)
    clock_in = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    clock_out = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)  # Used to track if session is currently active
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Location tracking fields
    clock_in_latitude = db.Column(db.Float, nullable=True)
    clock_in_longitude = db.Column(db.Float, nullable=True)
    clock_in_accuracy = db.Column(db.Float, nullable=True)  # Accuracy in meters
    clock_in_distance_mi = db.Column(db.Float, nullable=True)  # Distance from job site in miles
    
    clock_out_latitude = db.Column(db.Float, nullable=True)
    clock_out_longitude = db.Column(db.Float, nullable=True)
    clock_out_accuracy = db.Column(db.Float, nullable=True)  # Accuracy in meters
    clock_out_distance_mi = db.Column(db.Float, nullable=True)  # Distance from job site in miles
    
    # Relationships
    job = db.relationship('Job', backref='clock_sessions', lazy='joined')
    labor_activity = db.relationship('LaborActivity', backref='clock_sessions', lazy='joined')
    
    def clock_out_session(self):
        """Clock out of the session"""
        self.clock_out = datetime.utcnow()
        self.is_active = False
    
    def get_duration_hours(self):
        """Get the duration of the session in hours"""
        if not self.clock_out:
            # If still clocked in, calculate against current time
            end_time = datetime.utcnow()
        else:
            end_time = self.clock_out
            
        delta = end_time - self.clock_in
        # Convert timedelta to hours (as a float)
        hours = delta.total_seconds() / 3600
        return round(hours, 2)  # Round to 2 decimal places
    
    def create_time_entry(self):
        """Convert a completed clock session to a TimeEntry.
        If an entry already exists for the same user/job/activity/date,
        add hours to it instead of creating a new one.
        """
        if not self.clock_out:
            return None

        entry_date = self.clock_in.date()
        session_hours = self.get_duration_hours()

        # Check for existing time entry
        existing = TimeEntry.query.filter_by(
            user_id=self.user_id,
            job_id=self.job_id,
            labor_activity_id=self.labor_activity_id,
            date=entry_date
        ).first()

        if existing:
            # Add hours to existing entry
            existing.hours = round(existing.hours + session_hours, 2)
            if self.notes:
                existing.notes = f"{existing.notes}; {self.notes}" if existing.notes else self.notes
            return None  # No new entry to add

        # Create a new time entry from this clock session
        time_entry = TimeEntry(
            user_id=self.user_id,
            job_id=self.job_id,
            labor_activity_id=self.labor_activity_id,
            date=entry_date,
            hours=session_hours,
            notes=self.notes
        )

        return time_entry
        
    def __repr__(self):
        status = "ACTIVE" if self.is_active else "COMPLETED"
        return f'<ClockSession {self.id} - {status} - {self.user_id} - {self.job_id}>'


class DeviceLog(db.Model):
    """Device audit log for clock in/out actions"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ts = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    action = db.Column(db.String(10), nullable=False)  # 'IN' or 'OUT'
    device_id = db.Column(db.String(36), nullable=True)  # UUID stored in localStorage
    ua = db.Column(db.Text, nullable=True)  # User agent string
    lat = db.Column(db.Float, nullable=True)  # GPS latitude
    lng = db.Column(db.Float, nullable=True)  # GPS longitude
    
    # Relationships
    user = db.relationship('User', backref='device_logs', lazy='select')
    
    def __repr__(self):
        return f'<DeviceLog {self.user_id} - {self.action} - {self.ts}>'


class ForemanReviewedTime(db.Model):
    """Foreman's reviewed/adjusted time entries - separate from worker submissions.

    This table stores the foreman's interpretation of worker time. The original
    worker submissions in TimeEntry remain immutable. Foremen can adjust hours,
    job, labor activity freely - the reviewed time may differ significantly from
    what the worker submitted.
    """
    id = db.Column(db.Integer, primary_key=True)

    # Link to original worker submission (nullable for foreman-originated entries)
    worker_time_entry_id = db.Column(db.Integer, db.ForeignKey('time_entry.id'), nullable=True)

    # Core fields
    worker_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    work_date = db.Column(db.Date, nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    labor_activity_id = db.Column(db.Integer, db.ForeignKey('labor_activity.id'), nullable=True)

    # Reviewed values (foreman's interpretation)
    reviewed_hours = db.Column(db.Numeric(5, 2), nullable=False)
    notes = db.Column(db.Text, nullable=True)  # Foreman's explanation of adjustment

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    worker_time_entry = db.relationship('TimeEntry', foreign_keys=[worker_time_entry_id],
                                        backref='foreman_reviews', lazy='joined')
    worker = db.relationship('User', foreign_keys=[worker_id],
                            backref='reviewed_time_entries', lazy='joined')
    reviewer = db.relationship('User', foreign_keys=[reviewer_id],
                              backref='time_reviews_given', lazy='joined')
    job = db.relationship('Job', backref='foreman_reviewed_times', lazy='joined')
    labor_activity = db.relationship('LaborActivity', backref='foreman_reviewed_times', lazy='joined')

    # Unique constraint: one review per worker/date/job/activity combo
    __table_args__ = (
        db.UniqueConstraint('worker_id', 'work_date', 'job_id', 'labor_activity_id',
                           name='unique_reviewed_time'),
    )

    def __repr__(self):
        return f'<ForemanReviewedTime {self.worker_id} - {self.work_date} - {self.reviewed_hours}h>'


class PasswordResetToken(db.Model):
    """Password reset tokens for forgot password functionality"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token_hash = db.Column(db.String(256), nullable=False)  # Hashed token for security
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    used_at = db.Column(db.DateTime, nullable=True)  # Set when token is used
    
    # Relationships
    user = db.relationship('User', backref='password_reset_tokens', lazy='joined')
    
    def is_expired(self):
        """Check if token has expired (1 hour limit)"""
        from datetime import timedelta
        return datetime.utcnow() > self.created_at + timedelta(hours=1)
    
    def is_valid(self):
        """Check if token is valid (not used and not expired)"""
        return self.used_at is None and not self.is_expired()
    
    def __repr__(self):
        return f'<PasswordResetToken {self.id} - User {self.user_id}>'


class SystemMessage(db.Model):
    """System-wide message displayed to users based on role visibility settings"""
    id = db.Column(db.Integer, primary_key=True)
    message_text = db.Column(db.Text, nullable=True)
    show_to_admin = db.Column(db.Boolean, default=False)
    show_to_foreman = db.Column(db.Boolean, default=False)
    show_to_worker = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    # Relationship
    updater = db.relationship('User', backref='system_message_updates', lazy='joined')

    def is_visible_to(self, role):
        """Check if message should be visible to a given role"""
        if not self.message_text:
            return False
        if role == 'admin':
            return self.show_to_admin
        elif role == 'foreman':
            return self.show_to_foreman
        elif role == 'worker':
            return self.show_to_worker
        return False

    def __repr__(self):
        return f'<SystemMessage {self.id}>'


class PasskeyCredential(db.Model):
    """WebAuthn passkey credentials for passwordless authentication (Workers only)"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # WebAuthn credential data
    credential_id = db.Column(db.LargeBinary, nullable=False, unique=True)  # Raw credential ID bytes
    public_key = db.Column(db.LargeBinary, nullable=False)  # COSE-encoded public key
    sign_count = db.Column(db.Integer, nullable=False, default=0)  # Signature counter for replay protection

    # Credential metadata
    name = db.Column(db.String(100), nullable=False, default='My iPhone')  # User-friendly name
    transports = db.Column(db.String(200), nullable=True)  # JSON array of transports (e.g., ["internal"])

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    user = db.relationship('User', backref=db.backref('passkey_credentials', lazy='dynamic'))

    def __repr__(self):
        return f'<PasskeyCredential {self.id} - User {self.user_id}>'
