from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from models import TimeEntry

# Create admin blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def roles_required(role):
    """Decorator to require specific roles"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('You need to log in to access this page.', 'danger')
                return redirect(url_for('login'))
            
            if role == 'admin' and not current_user.is_admin():
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('login'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@admin_bp.route('/timesheets')
@login_required
@roles_required('admin')
def timesheets():
    # Query TimeEntry records that are submitted but not approved
    # This maps to the concept of submitted timesheets awaiting approval
    sheets = (TimeEntry.query
              .filter_by(approved=False)
              .order_by(TimeEntry.created_at.desc())
              .all())
    return render_template('admin/timesheets.html', sheets=sheets)