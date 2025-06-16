
#!/usr/bin/env python3

from app import app, db
from models import ClockSession, User, Job
from datetime import datetime, date, timedelta

def debug_gps_compliance():
    with app.app_context():
        # Set date range (last 30 days)
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        print(f"DEBUG: Checking GPS compliance from {start_date} to {end_date}")
        print("=" * 60)
        
        # Step 1: Check total clock sessions in date range
        total_sessions = ClockSession.query.filter(
            ClockSession.clock_in >= start_date,
            ClockSession.clock_in <= end_date + timedelta(days=1)
        ).count()
        print(f"1. Total clock sessions in date range: {total_sessions}")
        
        # Step 2: Check sessions with GPS data
        sessions_with_gps = ClockSession.query.filter(
            ClockSession.clock_in >= start_date,
            ClockSession.clock_in <= end_date + timedelta(days=1),
            ClockSession.clock_in_distance_mi.isnot(None)
        ).count()
        print(f"2. Sessions with GPS distance data: {sessions_with_gps}")
        
        # Step 3: Check distance distribution
        all_distances = db.session.query(ClockSession.clock_in_distance_mi).filter(
            ClockSession.clock_in >= start_date,
            ClockSession.clock_in <= end_date + timedelta(days=1),
            ClockSession.clock_in_distance_mi.isnot(None)
        ).all()
        
        distances = [d[0] for d in all_distances if d[0] is not None]
        print(f"3. Distance values found: {len(distances)}")
        if distances:
            print(f"   Min distance: {min(distances):.2f} miles")
            print(f"   Max distance: {max(distances):.2f} miles")
            print(f"   Sample distances: {distances[:10]}")
        
        # Step 4: Check violations by category
        violations_05_to_2 = ClockSession.query.filter(
            ClockSession.clock_in >= start_date,
            ClockSession.clock_in <= end_date + timedelta(days=1),
            ClockSession.clock_in_distance_mi > 0.5,
            ClockSession.clock_in_distance_mi < 2.0
        ).count()
        
        violations_2_to_5 = ClockSession.query.filter(
            ClockSession.clock_in >= start_date,
            ClockSession.clock_in <= end_date + timedelta(days=1),
            ClockSession.clock_in_distance_mi >= 2.0,
            ClockSession.clock_in_distance_mi < 5.0
        ).count()
        
        violations_5_plus = ClockSession.query.filter(
            ClockSession.clock_in >= start_date,
            ClockSession.clock_in <= end_date + timedelta(days=1),
            ClockSession.clock_in_distance_mi >= 5.0
        ).count()
        
        print(f"4. Violations by category:")
        print(f"   Minor (0.5-2 miles): {violations_05_to_2}")
        print(f"   Major (2-5 miles): {violations_2_to_5}")
        print(f"   Fraud Risk (5+ miles): {violations_5_plus}")
        
        # Step 5: Show sample violation records
        sample_violations = ClockSession.query.filter(
            ClockSession.clock_in >= start_date,
            ClockSession.clock_in <= end_date + timedelta(days=1),
            ClockSession.clock_in_distance_mi > 0.5
        ).join(User).join(Job).limit(5).all()
        
        print(f"5. Sample violation records:")
        for session in sample_violations:
            print(f"   Worker: {session.user.name}, Job: {session.job.job_code}")
            print(f"   Distance: {session.clock_in_distance_mi:.2f} miles")
            print(f"   Clock-in: {session.clock_in}")
            print(f"   GPS Accuracy: {session.clock_in_accuracy}m")
            print("   ---")

if __name__ == "__main__":
    debug_gps_compliance()
