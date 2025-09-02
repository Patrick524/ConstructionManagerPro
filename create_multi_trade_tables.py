#!/usr/bin/env python3
"""
Script to create many-to-many tables for multi-trade jobs and worker qualified trades.
This also backfills existing jobs from the legacy trade_type field.
"""

from app import app, db
from models import Job, Trade, User, job_trades, user_trades
from sqlalchemy import text

def create_many_to_many_tables():
    """Create the new many-to-many association tables"""
    with app.app_context():
        try:
            print("Creating many-to-many association tables...")
            
            # Create the job_trades table
            with db.engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS job_trades (
                        job_id INTEGER NOT NULL,
                        trade_id INTEGER NOT NULL,
                        assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (job_id, trade_id),
                        FOREIGN KEY (job_id) REFERENCES job (id),
                        FOREIGN KEY (trade_id) REFERENCES trade (id)
                    )
                """))
                conn.commit()
            print("✓ Created job_trades table")
            
            # Create the user_trades table
            with db.engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS user_trades (
                        user_id INTEGER NOT NULL,
                        trade_id INTEGER NOT NULL,
                        qualified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (user_id, trade_id),
                        FOREIGN KEY (user_id) REFERENCES "user" (id),
                        FOREIGN KEY (trade_id) REFERENCES trade (id)
                    )
                """))
                conn.commit()
            print("✓ Created user_trades table")
            
            db.session.commit()
            print("✓ Tables created successfully")
            
        except Exception as e:
            print(f"Error creating tables: {e}")
            db.session.rollback()
            raise

def backfill_job_trades():
    """Backfill existing jobs' trade relationships from the legacy trade_type field"""
    with app.app_context():
        try:
            print("Backfilling job-trade relationships from legacy trade_type...")
            
            # Get all jobs with trade_type
            jobs = Job.query.filter(Job.trade_type.isnot(None)).all()
            print(f"Found {len(jobs)} jobs to backfill")
            
            # Get or create trades based on unique trade_type values
            trade_mapping = {}
            for job in jobs:
                if job.trade_type and job.trade_type not in trade_mapping:
                    # Find existing trade or create new one
                    trade = Trade.query.filter(Trade.name.ilike(job.trade_type)).first()
                    if not trade:
                        # Create new trade with proper capitalization
                        trade_name = job.trade_type.title()
                        trade = Trade(name=trade_name, is_active=True)
                        db.session.add(trade)
                        db.session.flush()  # Get the ID
                        print(f"  Created new trade: {trade_name}")
                    trade_mapping[job.trade_type] = trade
            
            db.session.commit()
            print(f"✓ Created/found {len(trade_mapping)} trades")
            
            # Now assign trades to jobs
            assignments_count = 0
            for job in jobs:
                if job.trade_type and job.trade_type in trade_mapping:
                    trade = trade_mapping[job.trade_type]
                    
                    # Check if relationship already exists
                    existing = db.session.execute(text("""
                        SELECT 1 FROM job_trades 
                        WHERE job_id = :job_id AND trade_id = :trade_id
                    """), {'job_id': job.id, 'trade_id': trade.id}).fetchone()
                    
                    if not existing:
                        # Add the relationship
                        db.session.execute(text("""
                            INSERT INTO job_trades (job_id, trade_id) 
                            VALUES (:job_id, :trade_id)
                        """), {'job_id': job.id, 'trade_id': trade.id})
                        assignments_count += 1
                        print(f"  Assigned job {job.job_code} to trade {trade.name}")
            
            db.session.commit()
            print(f"✓ Created {assignments_count} job-trade assignments")
            
        except Exception as e:
            print(f"Error backfilling job trades: {e}")
            db.session.rollback()
            raise

def verify_migration():
    """Verify the migration worked correctly"""
    with app.app_context():
        try:
            # Count job-trade relationships
            job_trade_count = db.session.execute(text("SELECT COUNT(*) FROM job_trades")).scalar()
            print(f"✓ Total job-trade relationships: {job_trade_count}")
            
            # Show sample assignments
            results = db.session.execute(text("""
                SELECT j.job_code, j.description, t.name as trade_name
                FROM job_trades jt
                JOIN job j ON jt.job_id = j.id
                JOIN trade t ON jt.trade_id = t.id
                LIMIT 5
            """)).fetchall()
            
            print("Sample job-trade assignments:")
            for row in results:
                print(f"  {row.job_code}: {row.description} → {row.trade_name}")
                
        except Exception as e:
            print(f"Error verifying migration: {e}")

def run_migration():
    """Run the complete migration"""
    print("Starting multi-trade jobs migration...")
    print("=" * 50)
    
    create_many_to_many_tables()
    print()
    
    backfill_job_trades()
    print()
    
    verify_migration()
    print()
    
    print("=" * 50)
    print("Migration completed successfully!")
    print()
    print("Next steps:")
    print("1. Update admin interface to manage job trades")
    print("2. Update worker interface to show qualified trades")
    print("3. Consider removing legacy trade_type field after testing")

if __name__ == "__main__":
    run_migration()