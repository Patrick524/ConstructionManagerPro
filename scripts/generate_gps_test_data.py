"""
Generate GPS compliance test data:
- Creates 4 new test workers with use_clock_in=True
- Creates 100 clock sessions over the past 30 days
- 90 sessions are compliant (GPS at job site)
- 10 sessions are violations (GPS 1-15 miles away)
"""
import random
import math
from datetime import datetime, timedelta
from decimal import Decimal

# Add parent directory to path for imports
import sys
sys.path.insert(0, '/opt/ConstructionManagerPro')

from app import app, db
from models import User, Job, ClockSession, LaborActivity
from werkzeug.security import generate_password_hash


def offset_coordinates(lat, lng, distance_miles, bearing_degrees=None):
    """
    Offset coordinates by a given distance in miles.
    If bearing not specified, use random bearing.
    Returns (new_lat, new_lng, actual_distance_miles)
    """
    if bearing_degrees is None:
        bearing_degrees = random.uniform(0, 360)

    # Earth's radius in miles
    R = 3959

    # Convert to radians
    lat_rad = math.radians(lat)
    lng_rad = math.radians(lng)
    bearing_rad = math.radians(bearing_degrees)

    # Calculate new position
    new_lat_rad = math.asin(
        math.sin(lat_rad) * math.cos(distance_miles / R) +
        math.cos(lat_rad) * math.sin(distance_miles / R) * math.cos(bearing_rad)
    )

    new_lng_rad = lng_rad + math.atan2(
        math.sin(bearing_rad) * math.sin(distance_miles / R) * math.cos(lat_rad),
        math.cos(distance_miles / R) - math.sin(lat_rad) * math.sin(new_lat_rad)
    )

    new_lat = math.degrees(new_lat_rad)
    new_lng = math.degrees(new_lng_rad)

    return new_lat, new_lng, distance_miles


def calculate_distance(lat1, lng1, lat2, lng2):
    """Calculate distance between two points in miles using Haversine formula."""
    R = 3959  # Earth's radius in miles

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)

    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def create_test_workers():
    """Create 4 test workers with use_clock_in=True."""
    test_workers = [
        {"name": "Mike Rodriguez", "email": "mike.rodriguez@example.com"},
        {"name": "Danny O'Brien", "email": "danny.obrien@example.com"},
        {"name": "Carlos Hernandez", "email": "carlos.hernandez@example.com"},
        {"name": "Tommy Wilson", "email": "tommy.wilson@example.com"},
    ]

    created_workers = []

    for worker_data in test_workers:
        # Check if worker already exists
        existing = User.query.filter_by(email=worker_data["email"]).first()
        if existing:
            print(f"  Worker {worker_data['name']} already exists (id={existing.id})")
            # Ensure use_clock_in is True
            existing.use_clock_in = True
            created_workers.append(existing)
        else:
            worker = User(
                name=worker_data["name"],
                email=worker_data["email"],
                password_hash=generate_password_hash("password123"),
                role="worker",
                active=True,
                use_clock_in=True,
                burden_rate=Decimal("55.00")
            )
            db.session.add(worker)
            db.session.flush()  # Get the ID
            print(f"  Created worker: {worker.name} (id={worker.id})")
            created_workers.append(worker)

    db.session.commit()
    return created_workers


def generate_clock_sessions(workers, jobs, num_sessions=100, num_violations=10):
    """
    Generate clock sessions.
    - num_sessions total
    - num_violations will be GPS violations (1-15 miles away)
    - rest will be compliant (at job site)
    """
    # Get active labor activities
    activities = LaborActivity.query.filter_by(is_active=True).all()
    if not activities:
        raise ValueError("No active labor activities found!")

    now = datetime.now()
    thirty_days_ago = now - timedelta(days=30)

    # Evenly distribute sessions over 30 days
    sessions_per_day = num_sessions / 30

    # Decide which sessions will be violations
    # Spread violations across 3-4 workers
    violation_indices = set(random.sample(range(num_sessions), num_violations))

    # Violation distances: 3 fraud risk (5-15mi), 4 major (2-5mi), 3 minor (1-2mi)
    violation_distances = (
        [random.uniform(5, 15) for _ in range(3)] +  # Fraud risk
        [random.uniform(2, 5) for _ in range(4)] +   # Major
        [random.uniform(1, 2) for _ in range(3)]     # Minor
    )
    random.shuffle(violation_distances)

    # Workers who will have violations (spread across 3-4 workers)
    violation_workers = random.sample(workers, min(4, len(workers)))

    sessions_created = 0
    violations_created = 0

    for i in range(num_sessions):
        # Calculate date for this session (evenly distributed)
        day_offset = int(i / sessions_per_day)
        session_date = thirty_days_ago + timedelta(days=day_offset)

        # Random time during work hours (6 AM - 6 PM)
        hour = random.randint(6, 17)
        minute = random.randint(0, 59)
        clock_in_time = session_date.replace(hour=hour, minute=minute, second=0)

        # Clock out 4-10 hours later
        hours_worked = random.uniform(4, 10)
        clock_out_time = clock_in_time + timedelta(hours=hours_worked)

        # Select random job and worker
        job = random.choice(jobs)

        # Check if this is a violation session
        is_violation = i in violation_indices

        if is_violation:
            # Use a violation worker
            worker = random.choice(violation_workers)
            distance = violation_distances[violations_created]
            violations_created += 1

            # Offset GPS from job site
            clock_in_lat, clock_in_lng, _ = offset_coordinates(
                float(job.latitude), float(job.longitude), distance
            )
            clock_out_lat, clock_out_lng, _ = offset_coordinates(
                float(job.latitude), float(job.longitude), distance * 0.9  # Slightly closer on clock out
            )
        else:
            # Compliant - use any worker, GPS at job site (small random offset < 0.3 miles)
            worker = random.choice(workers)
            small_offset = random.uniform(0.01, 0.3)

            clock_in_lat, clock_in_lng, _ = offset_coordinates(
                float(job.latitude), float(job.longitude), small_offset
            )
            clock_out_lat, clock_out_lng, _ = offset_coordinates(
                float(job.latitude), float(job.longitude), small_offset * 0.8
            )
            distance = small_offset

        # Calculate actual distances
        clock_in_distance = calculate_distance(
            float(job.latitude), float(job.longitude),
            clock_in_lat, clock_in_lng
        )
        clock_out_distance = calculate_distance(
            float(job.latitude), float(job.longitude),
            clock_out_lat, clock_out_lng
        )

        # Create clock session
        session = ClockSession(
            user_id=worker.id,
            job_id=job.id,
            labor_activity_id=random.choice(activities).id,
            clock_in=clock_in_time,
            clock_out=clock_out_time,
            clock_in_latitude=clock_in_lat,
            clock_in_longitude=clock_in_lng,
            clock_out_latitude=clock_out_lat,
            clock_out_longitude=clock_out_lng,
            clock_in_distance_mi=round(clock_in_distance, 4),
            clock_out_distance_mi=round(clock_out_distance, 4),
            clock_in_accuracy=random.uniform(5, 50) if not is_violation else random.uniform(10, 80),
            clock_out_accuracy=random.uniform(5, 50) if not is_violation else random.uniform(10, 80),
            is_active=False,  # Completed session
        )

        db.session.add(session)
        sessions_created += 1

        if is_violation:
            category = "FRAUD RISK" if distance >= 5 else ("MAJOR" if distance >= 2 else "MINOR")
            print(f"  [{category}] Session {i+1}: {worker.name} at {job.job_code}, {distance:.2f} mi away")

    db.session.commit()
    print(f"\nCreated {sessions_created} clock sessions ({violations_created} violations)")
    return sessions_created, violations_created


def main():
    with app.app_context():
        print("=" * 60)
        print("GPS Compliance Test Data Generator")
        print("=" * 60)

        # Get jobs with GPS coordinates
        jobs = Job.query.filter(
            Job.status == 'active',
            Job.latitude.isnot(None),
            Job.longitude.isnot(None)
        ).all()

        if not jobs:
            print("ERROR: No jobs with GPS coordinates found!")
            return

        print(f"\nFound {len(jobs)} jobs with GPS coordinates")

        # Create test workers
        print("\n--- Creating Test Workers ---")
        workers = create_test_workers()

        # Also include Brad Bradley if he exists
        brad = User.query.filter_by(email="worker1@example.com").first()
        if brad and brad not in workers:
            brad.use_clock_in = True
            workers.append(brad)
            db.session.commit()
            print(f"  Added existing worker: {brad.name} (id={brad.id})")

        print(f"\nTotal workers for test: {len(workers)}")

        # Generate clock sessions
        print("\n--- Generating Clock Sessions ---")
        total, violations = generate_clock_sessions(workers, jobs, num_sessions=100, num_violations=10)

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Total clock sessions created: {total}")
        print(f"Compliant sessions (< 0.5 mi): {total - violations}")
        print(f"Violation sessions (> 0.5 mi): {violations}")
        print("  - Fraud Risk (5+ mi): ~3")
        print("  - Major (2-5 mi): ~4")
        print("  - Minor (1-2 mi): ~3")
        print("\nTest data generation complete!")


if __name__ == "__main__":
    main()
