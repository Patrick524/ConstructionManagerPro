"""Tests for admin reports functionality."""
import pytest
from playwright.sync_api import Page, expect

from conftest import BASE_URL


# Report types to test with their expected date ranges
# Using dates known to have data in the system
REPORT_CONFIGS = [
    {
        "type": "payroll",
        "name": "Payroll Report",
        "start_date": "2025-07-01",
        "end_date": "2025-07-31",
    },
    {
        "type": "employee_hours",
        "name": "Employee Hours",
        "start_date": "2025-06-15",
        "end_date": "2025-07-15",
    },
    {
        "type": "job_labor",
        "name": "Job Labor Report",
        "start_date": "2025-07-01",
        "end_date": "2025-07-31",
    },
    {
        "type": "job_cost",
        "name": "Job Cost Report",
        "start_date": "2025-05-01",
        "end_date": "2025-08-31",
    },
    {
        "type": "job_assignment",
        "name": "Job Assignment",
        "start_date": None,  # No date range needed
        "end_date": None,
    },
    {
        "type": "device_audit",
        "name": "Device Audit Log",
        "start_date": "2025-07-01",
        "end_date": "2025-07-31",
    },
]


def set_date_range(page: Page, start_date: str, end_date: str):
    """Set date range using JavaScript for flatpickr inputs."""
    if start_date and end_date:
        page.evaluate(f"""
            const startInput = document.querySelector('#start_date');
            const endInput = document.querySelector('#end_date');
            if (startInput._flatpickr) startInput._flatpickr.setDate('{start_date}', true);
            else startInput.value = '{start_date}';
            if (endInput._flatpickr) endInput._flatpickr.setDate('{end_date}', true);
            else endInput.value = '{end_date}';
        """)


def run_preview_and_check(page: Page, report_type: str, start_date: str = None, end_date: str = None):
    """Run preview for a report type and check for errors."""
    page.goto(f"{BASE_URL}/admin/reports")
    page.wait_for_load_state("networkidle")

    # Select report type
    page.select_option('select#report_type', report_type)

    # Set date range if provided
    if start_date and end_date:
        set_date_range(page, start_date, end_date)

    # Click preview button
    page.locator('#preview_button').click()

    # Wait for modal to appear and content to load
    page.wait_for_timeout(4000)

    # Check for error in the modal
    error_alert = page.locator('#pdfPreviewModal .alert-danger')
    if error_alert.is_visible():
        return False, error_alert.inner_text()

    # Modal should be visible (preview opened)
    modal = page.locator('#pdfPreviewModal')
    if not modal.is_visible():
        return False, "Preview modal did not appear"

    return True, "Preview successful"


class TestAdminReportsAccess:
    """Tests for accessing the admin reports page."""

    def test_admin_can_access_reports_page(self, logged_in_admin: Page):
        """Test that admin can access the reports page."""
        page = logged_in_admin

        page.goto(f"{BASE_URL}/admin/reports")
        page.wait_for_load_state("networkidle")

        # Verify we're on the reports page
        assert "/admin/reports" in page.url, "Should be on admin reports page"
        assert page.is_visible("text=Generate Reports"), "Should see Generate Reports heading"

    def test_reports_page_has_all_report_types(self, logged_in_admin: Page):
        """Test that all report types are available."""
        page = logged_in_admin

        page.goto(f"{BASE_URL}/admin/reports")
        page.wait_for_load_state("networkidle")

        # Check the report type dropdown has all expected options
        report_select = page.locator('select#report_type')
        expect(report_select).to_be_visible()

        for config in REPORT_CONFIGS:
            option = report_select.locator(f'option[value="{config["type"]}"]')
            assert option.count() > 0, f"Should have {config['name']} option"


class TestReportPreviewPayroll:
    """Tests for payroll report preview."""

    def test_payroll_report_july_2025(self, logged_in_admin: Page):
        """Test payroll report preview for July 2025 (high data month)."""
        page = logged_in_admin
        success, message = run_preview_and_check(
            page, "payroll", "2025-07-01", "2025-07-31"
        )
        assert success, f"Payroll report preview failed: {message}"

    def test_payroll_report_summer_2025(self, logged_in_admin: Page):
        """Test payroll report preview for summer 2025."""
        page = logged_in_admin
        success, message = run_preview_and_check(
            page, "payroll", "2025-06-01", "2025-08-31"
        )
        assert success, f"Payroll report preview failed: {message}"


class TestReportPreviewEmployeeHours:
    """Tests for employee hours report preview."""

    def test_employee_hours_june_july_2025(self, logged_in_admin: Page):
        """Test employee hours report for June-July 2025."""
        page = logged_in_admin
        success, message = run_preview_and_check(
            page, "employee_hours", "2025-06-15", "2025-07-15"
        )
        assert success, f"Employee hours report preview failed: {message}"

    def test_employee_hours_single_week(self, logged_in_admin: Page):
        """Test employee hours report for a single week in July 2025."""
        page = logged_in_admin
        success, message = run_preview_and_check(
            page, "employee_hours", "2025-07-14", "2025-07-20"
        )
        assert success, f"Employee hours report preview failed: {message}"


class TestReportPreviewJobLabor:
    """Tests for job labor report preview."""

    def test_job_labor_july_2025(self, logged_in_admin: Page):
        """Test job labor report for July 2025."""
        page = logged_in_admin
        success, message = run_preview_and_check(
            page, "job_labor", "2025-07-01", "2025-07-31"
        )
        assert success, f"Job labor report preview failed: {message}"

    def test_job_labor_q2_2025(self, logged_in_admin: Page):
        """Test job labor report for Q2 2025."""
        page = logged_in_admin
        success, message = run_preview_and_check(
            page, "job_labor", "2025-04-01", "2025-06-30"
        )
        assert success, f"Job labor report preview failed: {message}"


class TestReportPreviewJobCost:
    """Tests for job cost report preview."""

    def test_job_cost_summer_2025(self, logged_in_admin: Page):
        """Test job cost report for summer 2025."""
        page = logged_in_admin
        success, message = run_preview_and_check(
            page, "job_cost", "2025-05-01", "2025-08-31"
        )
        assert success, f"Job cost report preview failed: {message}"

    def test_job_cost_single_month(self, logged_in_admin: Page):
        """Test job cost report for single month (July 2025)."""
        page = logged_in_admin
        success, message = run_preview_and_check(
            page, "job_cost", "2025-07-01", "2025-07-31"
        )
        assert success, f"Job cost report preview failed: {message}"


class TestReportPreviewJobAssignment:
    """Tests for job assignment report preview."""

    def test_job_assignment_current(self, logged_in_admin: Page):
        """Test job assignment report (no date range needed)."""
        page = logged_in_admin
        success, message = run_preview_and_check(
            page, "job_assignment", None, None
        )
        assert success, f"Job assignment report preview failed: {message}"


class TestReportPreviewDeviceAudit:
    """Tests for device audit log report preview."""

    def test_device_audit_july_2025(self, logged_in_admin: Page):
        """Test device audit report for July 2025."""
        page = logged_in_admin
        success, message = run_preview_and_check(
            page, "device_audit", "2025-07-01", "2025-07-31"
        )
        assert success, f"Device audit report preview failed: {message}"

    def test_device_audit_recent(self, logged_in_admin: Page):
        """Test device audit report for recent period."""
        page = logged_in_admin
        success, message = run_preview_and_check(
            page, "device_audit", "2025-12-01", "2026-01-05"
        )
        assert success, f"Device audit report preview failed: {message}"


class TestReportFilters:
    """Tests for report filtering options."""

    def test_employee_hours_filter_by_employee(self, logged_in_admin: Page):
        """Test filtering employee hours report by employee."""
        page = logged_in_admin

        page.goto(f"{BASE_URL}/admin/reports")
        page.wait_for_load_state("networkidle")

        page.select_option('select#report_type', 'employee_hours')

        # Select first non-empty employee option
        user_select = page.locator('select#user_id')
        options = user_select.locator('option').all()
        for opt in options[1:]:  # Skip first "All" option
            value = opt.get_attribute('value')
            if value:
                user_select.select_option(value=value)
                break

        set_date_range(page, "2025-07-01", "2025-07-31")

        page.locator('#preview_button').click()
        page.wait_for_timeout(4000)

        error_alert = page.locator('#pdfPreviewModal .alert-danger')
        if error_alert.is_visible():
            pytest.fail(f"Filtered report preview failed: {error_alert.inner_text()}")

        modal = page.locator('#pdfPreviewModal')
        assert modal.is_visible(), "Preview modal should be visible"

    def test_job_labor_filter_by_job(self, logged_in_admin: Page):
        """Test filtering job labor report by job."""
        page = logged_in_admin

        page.goto(f"{BASE_URL}/admin/reports")
        page.wait_for_load_state("networkidle")

        page.select_option('select#report_type', 'job_labor')

        # Select first non-empty job option
        job_select = page.locator('select#job_id')
        options = job_select.locator('option').all()
        for opt in options[1:]:  # Skip first "All" option
            value = opt.get_attribute('value')
            if value:
                job_select.select_option(value=value)
                break

        set_date_range(page, "2025-07-01", "2025-07-31")

        page.locator('#preview_button').click()
        page.wait_for_timeout(4000)

        error_alert = page.locator('#pdfPreviewModal .alert-danger')
        if error_alert.is_visible():
            pytest.fail(f"Job filtered report preview failed: {error_alert.inner_text()}")

        modal = page.locator('#pdfPreviewModal')
        assert modal.is_visible(), "Preview modal should be visible"


class TestReportFormats:
    """Tests for different report output formats."""

    def test_csv_format_available(self, logged_in_admin: Page):
        """Test that CSV format is available."""
        page = logged_in_admin

        page.goto(f"{BASE_URL}/admin/reports")
        page.wait_for_load_state("networkidle")

        format_select = page.locator('select#format')
        csv_option = format_select.locator('option[value="csv"]')
        assert csv_option.count() > 0, "CSV format should be available"

    def test_pdf_format_available(self, logged_in_admin: Page):
        """Test that PDF format is available."""
        page = logged_in_admin

        page.goto(f"{BASE_URL}/admin/reports")
        page.wait_for_load_state("networkidle")

        format_select = page.locator('select#format')
        pdf_option = format_select.locator('option[value="pdf"]')
        assert pdf_option.count() > 0, "PDF format should be available"
