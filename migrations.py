from flask import Flask
from app import app, db
from models import User, Job, job_workers

def create_job_workers_table():
    """Create the job_workers association table if it doesn't exist"""
    # Check if the job_workers table already exists
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    if 'job_workers' not in inspector.get_table_names():
        # Create the job_workers table
        job_workers.create(db.engine)
        print("Created job_workers table")
    else:
        print("job_workers table already exists")

def assign_all_workers_to_jobs():
    """Assign all workers to all active jobs"""
    # Get all workers
    workers = User.query.filter_by(role='worker').all()
    # Get all active jobs
    jobs = Job.query.filter(Job.status != 'complete').all()
    
    # For each job, assign all workers
    assignments_count = 0
    for job in jobs:
        for worker in workers:
            # Check if the worker is already assigned to this job
            if not job.assigned_workers.filter_by(id=worker.id).first():
                # Add the worker to the job
                job.assigned_workers.append(worker)
                assignments_count += 1
    
    # Commit the changes
    if assignments_count > 0:
        db.session.commit()
        print(f"Assigned {assignments_count} worker-job relationships")
    else:
        print("No new worker-job assignments needed")

def run_migrations():
    """Run all migrations"""
    with app.app_context():
        # Create the job_workers table
        create_job_workers_table()
        
        # Assign all workers to all jobs
        assign_all_workers_to_jobs()
        
        print("Migrations completed successfully")

if __name__ == "__main__":
    run_migrations()