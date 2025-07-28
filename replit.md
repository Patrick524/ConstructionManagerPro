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
- **Models**: User, Job, LaborActivity, TimeEntry, ClockSession, Trade, WeeklyApprovalLock
- **Relationships**: Many-to-many job-worker assignments, trade-specific labor activities

## Key Components

### Authentication and Authorization
- **Three-tier role system**: Worker, Foreman, Admin
- **Session management**: Secure session handling with configurable timeouts
- **Password security**: Werkzeug password hashing

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
- **Report types**: Payroll, billing, GPS compliance, and summary reports
- **Date range filtering**: Flexible reporting periods

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

- July 28, 2025: Resolved temporary form glitch in worker timesheet edit functionality where hours field was briefly showing 0 instead of actual values. Enhanced UI with harmonious dark theme colors and improved table readability.
- June 30, 2025. Initial setup

## User Preferences

Preferred communication style: Simple, everyday language.