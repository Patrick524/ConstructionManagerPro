# Construction Timesheet Management System

## Overview

This is a comprehensive Flask-based web application designed for construction timesheet management. The system provides role-based access control for workers, foremen, and administrators to track time across multiple construction jobs with trade-specific labor activities. The application features both manual time entry and clock-in/out functionality with GPS tracking capabilities.

## System Architecture

### Frontend Architecture
- **Framework**: Flask with Jinja2 templating
- **UI Framework**: Bootstrap 5 with dark theme
- **JavaScript Libraries**: 
  - Chart.js for data visualization
  - Flatpickr for date picking
  - Leaflet for GPS mapping
  - Custom JavaScript modules for timesheet functionality
- **Responsive Design**: Mobile-first approach optimized for field workers

### Backend Architecture
- **Framework**: Flask with SQLAlchemy ORM
- **Authentication**: Flask-Login with role-based access control
- **Database Migrations**: Flask-Migrate for schema management
- **Background Tasks**: APScheduler for automated clock-out functionality
- **Form Handling**: WTForms with custom validation

### Data Storage Solutions
- **Primary Database**: SQLAlchemy with support for multiple database backends
- **Models**: User, Job, LaborActivity, TimeEntry, ClockSession, Trade, WeeklyApprovalLock, PasswordResetToken, DeviceLog
- **Relationships**: Many-to-many job-worker assignments, trade-specific labor activities

## Key Components

### Authentication and Authorization
- **Three-tier role system**: Worker, Foreman, Admin
- **Session management**: Secure session handling with configurable timeouts
- **Password security**: Werkzeug password hashing
- **Password reset**: Email-based password reset with secure hashed tokens (1-hour expiry)

### Time Tracking System
- **Dual input methods**: Manual timesheet entry and GPS-enabled clock in/out
- **Weekly approval workflow**: Foremen approve entire weeks, locking entries
- **GPS compliance**: Distance tracking from job sites with configurable thresholds

### Job Management
- **Trade categorization**: Support for multiple construction trades (drywall, electrical, etc.)
- **Labor activities**: Trade-specific work categories
- **Location tracking**: Job site coordinates for GPS validation

### Reporting System
- **Multiple formats**: CSV and PDF report generation
- **Report types**: Payroll, billing, GPS compliance, job assignment, and summary reports
- **Job Assignment Reports**: Job-focused workforce reporting optimized for small construction companies
- **Date range filtering**: Flexible reporting periods (except job assignment which shows current state)

## Data Flow

1. **Time Entry**: Workers enter daily hours or use clock in/out system
2. **GPS Validation**: System calculates distance from job site for clock sessions
3. **Weekly Review**: Foremen review and approve worker timesheets
4. **Report Generation**: Approved time generates payroll and billing reports
5. **Background Processing**: Automated clock-out prevents sessions over 8 hours

## External Dependencies

### Required Python Packages
- Flask ecosystem (Flask, Flask-SQLAlchemy, Flask-Login, Flask-Migrate, Flask-WTF)
- SQLAlchemy for database operations
- APScheduler for background tasks
- WTForms for form handling
- Pandas for data processing

### Frontend Dependencies
- Bootstrap 5 (dark theme variant)
- Font Awesome icons
- Chart.js for dashboard visualizations
- Flatpickr for date selection
- Leaflet for mapping functionality

### Optional Integrations
- SMTP configuration for email notifications
- Database-specific drivers (PostgreSQL, MySQL, SQLite)

## Deployment Strategy

### Development Setup
- Environment variables for database URL and session secrets
- Debug mode enabled for development
- SQLite fallback for local development

### Production Considerations
- Secure session configuration
- Database connection pooling
- Background scheduler initialization
- Static file serving optimization

### Migration Strategy
- Alembic-based database migrations
- Backward compatibility maintenance
- Data integrity validation scripts

## Changelog

- December 15, 2025: **Added Forgot Password flow with secure email-based password reset**. Features: "Forgot password?" link on login page, secure token generation with hashing (tokens stored hashed, not plain), 1-hour expiration on reset links, tokens invalidated after use, user-friendly messages that don't reveal whether an email is registered. New model: PasswordResetToken. Email sent via Flask-Mail with SMTP2GO. Routes: /forgot-password and /reset-password/<token>.

- September 15, 2025: **Fixed PST timezone display issue and completed comprehensive trade validation system**. Root cause: JavaScript timezone functions were not executing due to unhandled Leaflet map errors ("Invalid LatLng object: NaN, NaN") that crashed the entire DOMContentLoaded handler. **Solution**: Separated timezone functions into isolated event handler with proper error handling, added coordinate validation for maps. **Result**: All clock-in/out times now display correctly in PST format instead of confusing UTC times. Trade validation system prevents workers from seeing jobs they're not qualified for through multi-layer security: UI filtering, server-side validation, and admin controls. **Testing**: Comprehensive Playwright tests confirm both systems work together properly.

- September 13, 2025: Major refactor of Job Assignment Report to job-summary format for small construction companies. Changed from individual worker rows to job-focused table showing "who's working where right now." New format groups by job with comma-separated worker lists and worker counts. Implemented database-compatible aggregation (PostgreSQL string_agg vs SQLite group_concat) and rewrote CSV/PDF generation. Added current-state filtering (active jobs + active users only). Report now answers "current assignments" without date complexity.
- July 28, 2025: Fixed critical edit functionality bug where editing time entries showed incorrect hours values in the form. Root cause was JavaScript interference overriding server-populated form values. Solution involved primary key-based entry fetching, proper edit mode detection, and preventing API calls from overwriting form data during edits. Enhanced UI with harmonious dark theme colors and improved table readability.
- June 30, 2025. Initial setup

## User Preferences

Preferred communication style: Simple, everyday language.