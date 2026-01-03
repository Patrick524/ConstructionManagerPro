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
- Per-worker toggle: Use Clock In/Out System exists but not enforced

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

## Operational notes

- No login rate limiting
- Gunicorn runs 1 worker; large PDF reports may timeout
- No automated DB backup strategy

## Known issues

- Overlapping clock sessions not prevented
- Duplicate time between manual + clock possible
- use_clock_in toggle exists but not strictly enforced
- No GPS accuracy/precision captured

## Suggested improvements

- Enforce one open clock session per worker to prevent overlaps
- Add duplicate detection in approval UI
- Add login rate limiting
- Add external DB backup strategy (scheduled pg_dump)
- Capture GPS accuracy metadata

## Code style

- Place all imports at the top of files, never inside functions
- Use PST timezone for all user-facing timestamps
```
