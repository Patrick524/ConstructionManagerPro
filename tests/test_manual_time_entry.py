"""
Playwright test to automate manual time entry for 30 days.
Uses the actual app at https://app.buildertimepro.com
"""

import pytest
from playwright.sync_api import Page, expect
from datetime import datetime, timedelta
import random

# Test data
WORKER_EMAIL = "quick@me.com"
WORKER_PASSWORD = "TestPass123!"
BASE_URL = "https://app.buildertimepro.com"

# Jobs that are assigned to Jack Quick (from database)
JOBS = [
    "DRY-001",
    "4321",
    "4423",
    "8001",
    "8002",
    "8003",
    "SPRING-002",
]

# Labor activities
ACTIVITIES = [
    "Hanging Drywall",
    "Taping and Mudding",
    "Sanding",
    "Surface Preparation",
    "Priming",
    "Painting",
    "General Work",
    "Grid Installation",
    "Ceiling Tile Installation",
]

# Hours options (realistic construction work hours)
HOURS_OPTIONS = [6, 8, 8, 8, 10, 10, 12]  # weighted toward 8-10 hours

# Sample notes
NOTES_OPTIONS = [
    "",  # No notes
    "",  # No notes (weighted)
    "",  # No notes (weighted)
    "Completed main floor section",
    "Weather delay - started late",
    "Overtime to meet deadline",
    "Training new crew member",
    "Material delivery issues",
    "Safety meeting in morning",
    "Worked with HVAC team on coordination",
    "Finished ahead of schedule",
    "Extra detail work required",
]


@pytest.fixture(scope="function")
def logged_in_page(page: Page):
    """Login as the worker and return the page."""
    page.goto(f"{BASE_URL}/login")
    page.wait_for_load_state("networkidle")

    # Fill in login form - using id selectors for Flask-WTF form fields
    page.fill('#email', WORKER_EMAIL)
    page.fill('#password', WORKER_PASSWORD)

    # Submit button - Flask-WTF creates input with id="submit" or button
    page.click('#submit')

    # Wait for redirect to dashboard or timesheet
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)  # Give extra time for redirect

    # Verify login successful by checking we're not on login page
    assert "/login" not in page.url, f"Login failed, still on: {page.url}"

    return page


def enter_time_entry(page: Page, date: datetime, job: str, activity: str, hours: int, notes: str = ""):
    """Enter a single time entry using the manual entry form."""

    # Navigate to the time entry page
    page.goto(f"{BASE_URL}/worker/timesheet")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)  # Wait for flatpickr to initialize

    # Format date as YYYY-MM-DD for the date input
    date_str = date.strftime("%Y-%m-%d")

    # For flatpickr, we need to use JavaScript to set the value
    # The visible input is the one without type="hidden" that has flatpickr-input class
    page.evaluate(f"""
        const dateInput = document.querySelector('#date');
        if (dateInput && dateInput._flatpickr) {{
            dateInput._flatpickr.setDate('{date_str}', true);
        }} else {{
            // Fallback: set via the visible input
            const visibleInput = document.querySelector('.flatpickr-input:not([type="hidden"])');
            if (visibleInput) {{
                visibleInput.value = '{date_str}';
                visibleInput.dispatchEvent(new Event('change'));
            }}
        }}
    """)

    # Select job - find option containing the job code
    job_select = page.locator('select[name="job_id"]')
    # Get all options and find one containing our job code
    options = job_select.locator('option').all()
    job_value = None
    for opt in options:
        text = opt.text_content()
        if job in text:
            job_value = opt.get_attribute('value')
            break

    if job_value:
        job_select.select_option(value=job_value)
    else:
        # Try selecting by visible text containing job code
        job_select.select_option(label=job)

    # Small wait for activity dropdown to potentially update
    page.wait_for_timeout(500)

    # Select labor activity
    activity_select = page.locator('select[name="labor_activity_1"]')
    activity_options = activity_select.locator('option').all()
    activity_value = None
    for opt in activity_options:
        text = opt.text_content()
        if activity.lower() in text.lower():
            activity_value = opt.get_attribute('value')
            break

    if activity_value:
        activity_select.select_option(value=activity_value)

    # Enter hours
    hours_input = page.locator('input[name="hours_1"]')
    hours_input.clear()
    hours_input.fill(str(hours))

    # Enter notes using JavaScript (notes textarea is hidden in display:none div)
    if notes:
        escaped_notes = notes.replace("'", "\\'").replace("\n", "\\n")
        page.evaluate(f"""
            const notesArea = document.querySelector('textarea[name="notes"]');
            if (notesArea) {{
                notesArea.value = '{escaped_notes}';
            }}
        """)

    # Submit the form
    page.click('button[type="submit"]')

    # Wait for response
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)

    return True


def test_manual_time_entry_30_days(logged_in_page: Page):
    """Enter time entries for the past 30 days with varied data."""

    page = logged_in_page
    entries_made = []

    # Generate dates for the past 30 days
    today = datetime.now()
    dates = [today - timedelta(days=i) for i in range(1, 31)]

    # Skip some random days to simulate missing entries (about 5 days)
    days_to_skip = random.sample(range(len(dates)), 5)

    for i, entry_date in enumerate(dates):
        # Skip some days
        if i in days_to_skip:
            print(f"Skipping {entry_date.strftime('%Y-%m-%d')} (simulating missing entry)")
            continue

        # Skip weekends occasionally (50% chance)
        if entry_date.weekday() >= 5 and random.random() < 0.5:
            print(f"Skipping weekend {entry_date.strftime('%Y-%m-%d')}")
            continue

        # Pick random job, activity, hours, notes
        job = random.choice(JOBS)
        activity = random.choice(ACTIVITIES)
        hours = random.choice(HOURS_OPTIONS)
        notes = random.choice(NOTES_OPTIONS)

        print(f"Entering: {entry_date.strftime('%Y-%m-%d')} | {job} | {activity} | {hours}h | notes: {notes[:30] if notes else 'none'}")

        try:
            enter_time_entry(page, entry_date, job, activity, hours, notes)
            entries_made.append({
                'date': entry_date.strftime('%Y-%m-%d'),
                'job': job,
                'activity': activity,
                'hours': hours,
                'notes': notes
            })
        except Exception as e:
            print(f"Error entering time for {entry_date.strftime('%Y-%m-%d')}: {e}")
            # Take screenshot on error
            page.screenshot(path=f"error_{entry_date.strftime('%Y%m%d')}.png")

    # Summary
    print(f"\n=== SUMMARY ===")
    print(f"Total entries made: {len(entries_made)}")
    print(f"Days skipped: {30 - len(entries_made)}")

    print("\nEntries breakdown:")
    for entry in entries_made:
        print(f"  {entry['date']}: {entry['job']} - {entry['activity']} - {entry['hours']}h")

    # Verify some entries were created
    assert len(entries_made) >= 15, f"Expected at least 15 entries, got {len(entries_made)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
