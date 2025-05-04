"""
Scheduler module for running background tasks.
Currently implements:
- Auto clock-out job that runs every minute to close any clock sessions older than 8 hours
"""
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app import app, db
from models import ClockSession

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def auto_clock_out_job():
    """
    Automatically clock out any active sessions that are older than 8 hours.
    This prevents workers from accidentally leaving sessions open indefinitely.
    """
    with app.app_context():
        try:
            # Find all active clock sessions older than 8 hours
            eight_hours_ago = datetime.utcnow() - timedelta(hours=8)
            
            # Get sessions that need to be closed
            sessions = ClockSession.query.filter(
                ClockSession.is_active == True,
                ClockSession.clock_out == None,
                ClockSession.clock_in <= eight_hours_ago
            ).all()
            
            if not sessions:
                logger.debug("No stale clock sessions found to auto-close")
                return
            
            # Close each session
            session_count = 0
            for session in sessions:
                # Set clock_out to exactly 8 hours after clock_in
                session.clock_out = session.clock_in + timedelta(hours=8)
                session.is_active = False
                session_count += 1
                
                # Create a time entry record from the clock session
                time_entry = session.create_time_entry()
                if time_entry:
                    db.session.add(time_entry)
            
            # Commit all changes
            db.session.commit()
            
            if session_count > 0:
                logger.info(f"Auto-closed {session_count} clock sessions older than 8 hours")
                
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error in auto_clock_out_job: {str(e)}")

def init_scheduler():
    """Initialize and start the background scheduler"""
    scheduler = BackgroundScheduler()
    
    # Schedule the auto clock-out job to run every minute
    scheduler.add_job(
        auto_clock_out_job,
        IntervalTrigger(minutes=1),
        id='auto_clock_out_job',
        name='Auto close clock sessions older than 8 hours',
        replace_existing=True
    )
    
    # Start the scheduler
    scheduler.start()
    logger.info("Background scheduler started with auto clock-out job")
    return scheduler