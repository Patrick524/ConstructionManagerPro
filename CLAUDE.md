```
# BuilderTime Pro / Construction Timesheet — Claude Handoff Summary

## What the app does

BuilderTime Pro is a construction timesheet platform with role-based workflows (Worker / Foreman / Admin) supporting:

Worker time capture via two modes:
- Manual time entry (quick daily entry: date + job + labor activity + hours)
- Clock-in / clock-out sessions (GPS captured when available)

Foreman weekly review + approval:
- Foreman views time week-by-week and can enter/edit time on behalf of workers
- Weekly status concepts (e.g., incomplete vs ready for approval)
- Approval locks time (no modification after approval)
- Foreman can approve even with missing entries

Admin configuration + reporting:
- Manage Jobs (job code/description, status, foreman assignment, job location/address to coordinates, trades required per job)
- Manage Users (role, active/inactive, burden rate for costing, per-worker use clock-in/out toggle, worker trade qualifications)
- Manage Trades and Labor Activities (customizable to match company services; activities grouped by trade; disable instead of delete)
- Reports hub supports preview + export (CSV/PDF): Payroll, Job Labor, Employee Hours, Job Cost, Job Assignment, GPS Compliance, Device Audit Log
- System Message: configurable announcement banner visible to selected roles

## Compliance features

GPS Compliance / Fraud Risk:
- GPS compliance report buckets violations by distance from job site: Minor (0.5-2 mi), Major (2-5 mi), Fraud Risk (5+ mi)
- Drill-down shows map evidence (Leaflet/OSM), worker + job info, timestamp, computed distance
- Policy: clock-in allowed without GPS; distance marked unknown/null in reports

Device/Browser Audit (anti buddy swipe):
- Captures User-Agent + IP into a DeviceLog table
- Used for audit/reporting only (no enforcement, no alerts)

## Data model

Jobs:
- Stored with lat/lng on Job model (via Get Coordinates geocode)
- No per-job radius; GPS compliance uses a global distance threshold
- Trades required per job; foreman assignment; active/inactive status

Workers:
- Worker trade qualifications stored (used to constrain job/trade visibility)
- Burden rate ($/hr) stored for job costing calculations
- Time entry method: Each worker is configured as either "timeclock" or "manual":
  - Timeclock workers (`use_clock_in=True`): Use clock-in/clock-out system with GPS capture
  - Manual workers (`use_clock_in=False`): Use quick daily entry form (date + job + activity + hours)
  - The toggle is stored in User.use_clock_in boolean field
  - UI shows appropriate interface based on worker's configured method

Timekeeping:
- Two source tables: TimeEntry (manual hours) and ClockSession (clock in/out events)
- Reports aggregate from both
- Overlapping clock sessions not prevented
- Duplicate time between manual + clock possible; relies on foreman review

GPS storage:
- GPS stored directly on ClockSession: clock_in_lat/lng, clock_out_lat/lng
- No accuracy/precision captured

## Tech stack

Backend:
- Python / Flask / SQLAlchemy / PostgreSQL (Neon hosted)
- Flask-Login auth (Worker/Foreman/Admin)
- Flask-Migrate for migrations (manual flask db upgrade)
- APScheduler background job (auto clock-out sessions after 8 hours)
- Flask-Mail + SMTP2GO for password reset email
- PST timezone display throughout

Frontend:
- Bootstrap 5 dark theme + Jinja2 server-side templates
- Chart.js dashboards
- Flatpickr date pickers
- Leaflet maps for GPS compliance drilldowns
- Font Awesome icons

Hosting:
- Digital Ocean droplet (164.92.75.109)
- Gunicorn binding to 0.0.0.0:8000
- NGINX reverse proxy to app.buildertimepro.com
- Systemd service: construction
- Code location: /opt/ConstructionManagerPro
- Neon PostgreSQL (external, via DATABASE_URL in .env)
- Python venv at /opt/ConstructionManagerPro/venv

Source Control:
- GitHub: https://github.com/Patrick524/ConstructionManagerPro
- Dev environment: Claude Code on DO droplet

## Key files

app.py - Flask app init
main.py - Entry point with scheduler init
routes.py - Main route handlers
routes_weekly.py - Weekly timesheet routes
models.py - SQLAlchemy models
forms.py - Flask-WTF forms
utils.py - CSV/PDF/email helpers
scheduler.py - APScheduler auto clock-out job
templates/ - Jinja2 templates (admin/, foreman/, worker/)
static/ - CSS/JS assets

## Background jobs

auto_clock_out_job runs every 1 minute - closes active clock sessions older than 8 hours, creates time entries. Scheduler is initialized in main.py via init_scheduler().

## Quick commands

Restart app: sudo systemctl restart construction
Check status: sudo systemctl status construction
View logs: sudo journalctl -u construction -f
Pull latest: cd /opt/ConstructionManagerPro && git pull origin main
Activate venv: source /opt/ConstructionManagerPro/venv/bin/activate
Run migrations: flask db upgrade

## Tests

Playwright end-to-end tests in `tests/` directory. Run against live app at https://app.buildertimepro.com.

Test files:
- `conftest.py` - Shared fixtures, login helper, test credentials
- `test_auth.py` - Login flow tests (worker + foreman login, invalid password)
- `test_foreman_review.py` - Foreman review workflow (dashboard, review screen, save draft, finalize, UI elements)
- `test_admin_reports.py` - Admin reports preview tests (all 6 report types with various date ranges)
- `test_gps_compliance.py` - GPS compliance report tests (11 tests: page access, violation detection, categorization)
- `test_system_message.py` - System message visibility tests (10 tests: all 3 roles + admin settings page)
- `test_manual_time_entry.py` - Data generation script (enters 30 days of time entries, slow)

Test credentials (in conftest.py):
- Worker: worker1@example.com / password123
- Foreman: foreman@example.com / password123
- Admin: admin@example.com / password123

Run tests:
- All tests: `./venv/bin/pytest tests/ -v`
- Auth tests only: `./venv/bin/pytest tests/test_auth.py -v`
- Foreman review tests: `./venv/bin/pytest tests/test_foreman_review.py -v`
- Admin reports tests: `./venv/bin/pytest tests/test_admin_reports.py -v`
- GPS compliance tests: `./venv/bin/pytest tests/test_gps_compliance.py -v`
- System message tests: `./venv/bin/pytest tests/test_system_message.py -v`
- Skip slow data generation: `./venv/bin/pytest tests/ -v --ignore=tests/test_manual_time_entry.py`

Notes:
- Tests use previous week's data (current week may not have entries)
- Foreman review tests navigate to weeks with actual worker time data
- Admin reports tests use summer 2025 date ranges (July 2025 has most data: 102 entries)
- GPS compliance tests use past 30 days of clock session data with known violations
- Playwright browsers installed via: `/opt/ConstructionManagerPro/venv/bin/playwright install`

## GPS Compliance Test Data

Script: `scripts/generate_gps_test_data.py`

Generates test data for GPS compliance testing:
- Creates 4 test workers: Mike Rodriguez, Danny O'Brien, Carlos Hernandez, Tommy Wilson
- Generates 100 clock sessions over past 30 days
- 90 compliant sessions (GPS within 0.3 miles of job site)
- 10 violation sessions distributed across categories:
  - 3 Fraud Risk (5-15 miles away)
  - 4 Major (2-5 miles away)
  - 3 Minor (1-2 miles away)

Run: `./venv/bin/python scripts/generate_gps_test_data.py`

Test workers created with `use_clock_in=True` and emails @example.com.

## Reports

Admin reports available at `/admin/reports` with preview + export (CSV/PDF):
- **Payroll** - Uses ForemanReviewedTime (reviewed entries only); QuickBooks-compatible CSV format
- **Employee Hours** - All time entries by employee
- **Job Labor** - Time entries grouped by job
- **Job Cost** - Labor cost calculations using burden rates
- **Job Assignment** - Current worker-to-job assignments (no date range needed)
- **Device Audit Log** - Clock in/out device fingerprints for fraud detection

GPS Compliance Report (`/admin/gps_compliance`):
- Separate page from main reports hub
- Detects violations on EITHER clock-in OR clock-out (catches workers who forget to clock out and do it from home)
- Session flagged if either event exceeds 0.5 miles from job site
- Categorized by worst distance: Minor (0.5-2 mi), Major (2-5 mi), Fraud Risk (5+ mi)
- Each violation row shows:
  - Clock-in time + distance (color-coded badge)
  - Clock-out time + distance (or "Still Active" / "No GPS")
  - Hours worked
- Map drill-down shows 3 markers:
  - Red = Job site (expected location)
  - Blue = Clock-in location
  - Green = Clock-out location
- Executive summary, violation counts, worker violation summary
- Worker filter to focus on specific employees

Report data flow:
- Payroll report queries `ForemanReviewedTime` table (only foreman-approved entries)
- GPS compliance queries `ClockSession` table with distance calculations
- Other reports query `TimeEntry` table directly
- All reports convert SQLAlchemy rows to dicts before passing to PDF/CSV generators

## System Message

Admin-configurable announcement banner displayed at the bottom of all screens.

Features:
- Access via Settings link in admin navigation (`/admin/settings`)
- Text input for custom message (e.g., "Timesheets due Monday 8am.")
- Three checkboxes to control visibility per role: Admin, Foreman, Worker
- Fixed position banner at bottom of page (blue gradient, visible but not intrusive)
- Live preview on settings page
- Message persists until admin clears or changes it

Database:
- `SystemMessage` model stores: message_text, show_to_admin, show_to_foreman, show_to_worker, updated_at, updated_by
- Single row (singleton pattern) - only one system message at a time
- Injected into all templates via Flask context processor

Key files:
- `models.py` - SystemMessage model
- `routes.py` - admin_settings route, inject_system_message context processor
- `templates/admin/settings.html` - Settings page with message form
- `templates/base.html` - System message banner display

## Operational notes

- No login rate limiting
- Gunicorn runs 1 worker; large PDF reports may timeout
- No automated DB backup strategy

## Known issues

- Overlapping clock sessions not prevented
- Duplicate time between manual + clock possible
- No GPS accuracy/precision captured

## Suggested improvements

- Enforce one open clock session per worker to prevent overlaps
- Add duplicate detection in approval UI
- Add login rate limiting
- Add external DB backup strategy (scheduled pg_dump)
- Capture GPS accuracy metadata

## Recent bug fixes (Jan 2026)

- Fixed payroll report error: `get_effective_time_query()` now converts SQLAlchemy rows to dicts when `reviewed_only=True`
- Fixed reports `UnboundLocalError`: Removed redundant local import of `User` in job_assignment block that shadowed global import

## Code style

- Place all imports at the top of files, never inside functions (avoid shadowing global imports with local imports in conditionals)
- Use PST timezone for all user-facing timestamps
```
