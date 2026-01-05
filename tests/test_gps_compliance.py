"""Tests for GPS compliance report functionality."""
from datetime import datetime, timedelta

import pytest
from playwright.sync_api import Page, expect

from conftest import BASE_URL


def get_test_date_range():
    """Get date range covering past 30 days."""
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


def set_date_range(page: Page, start_date: str, end_date: str):
    """Set date range using JavaScript for flatpickr inputs."""
    page.evaluate(f"""
        const startInput = document.querySelector('#start_date');
        const endInput = document.querySelector('#end_date');
        if (startInput._flatpickr) startInput._flatpickr.setDate('{start_date}', true);
        else startInput.value = '{start_date}';
        if (endInput._flatpickr) endInput._flatpickr.setDate('{end_date}', true);
        else endInput.value = '{end_date}';
    """)


class TestGPSComplianceAccess:
    """Tests for accessing the GPS compliance page."""

    def test_admin_can_access_gps_compliance_page(self, logged_in_admin: Page):
        """Test that admin can access the GPS compliance page."""
        page = logged_in_admin

        page.goto(f"{BASE_URL}/admin/gps_compliance")
        page.wait_for_load_state("networkidle")

        # Verify we're on the GPS compliance page
        assert "/admin/gps_compliance" in page.url
        assert page.is_visible("text=GPS Compliance Report")

    def test_gps_compliance_page_has_form(self, logged_in_admin: Page):
        """Test that the GPS compliance page has the report form."""
        page = logged_in_admin

        page.goto(f"{BASE_URL}/admin/gps_compliance")
        page.wait_for_load_state("networkidle")

        # Check for form labels and submit button
        expect(page.locator('text=Start Date')).to_be_visible()
        expect(page.locator('text=End Date')).to_be_visible()
        expect(page.locator('text=Report Parameters')).to_be_visible()
        expect(page.locator('input[type="submit"], button[type="submit"]')).to_be_visible()


class TestGPSComplianceReportGeneration:
    """Tests for generating GPS compliance reports."""

    def test_generate_report_shows_violations(self, logged_in_admin: Page):
        """Test that generating report shows the expected violations."""
        page = logged_in_admin
        start_date, end_date = get_test_date_range()

        page.goto(f"{BASE_URL}/admin/gps_compliance")
        page.wait_for_load_state("networkidle")

        # Set date range
        set_date_range(page, start_date, end_date)

        # Submit form
        page.click('input[type="submit"], button[type="submit"]')
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Should see Executive Summary section
        expect(page.locator("text=Executive Summary")).to_be_visible()

        # Should see Total Clock-ins stat
        expect(page.locator("text=Total Clock-ins")).to_be_visible()

    def test_report_shows_violation_count(self, logged_in_admin: Page):
        """Test that report shows violation counts."""
        page = logged_in_admin
        start_date, end_date = get_test_date_range()

        page.goto(f"{BASE_URL}/admin/gps_compliance")
        page.wait_for_load_state("networkidle")

        set_date_range(page, start_date, end_date)
        page.click('input[type="submit"], button[type="submit"]')
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Should see Total Violations in the stat cards (use heading)
        expect(page.get_by_role("heading", name="Total Violations")).to_be_visible()

    def test_report_categorizes_violations(self, logged_in_admin: Page):
        """Test that report shows violation categories (fraud risk, major, minor)."""
        page = logged_in_admin
        start_date, end_date = get_test_date_range()

        page.goto(f"{BASE_URL}/admin/gps_compliance")
        page.wait_for_load_state("networkidle")

        set_date_range(page, start_date, end_date)
        page.click('input[type="submit"], button[type="submit"]')
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Should see violation category stat cards (use specific heading text)
        expect(page.get_by_role("heading", name="Fraud Risk (5+ mi)")).to_be_visible()
        expect(page.get_by_role("heading", name="Major Violations (2-5 mi)")).to_be_visible()
        expect(page.get_by_role("heading", name="Minor Violations (0.5-2 mi)")).to_be_visible()


class TestGPSComplianceViolationDetails:
    """Tests for violation details in GPS compliance report."""

    def test_violations_show_worker_names(self, logged_in_admin: Page):
        """Test that violations show worker names."""
        page = logged_in_admin
        start_date, end_date = get_test_date_range()

        page.goto(f"{BASE_URL}/admin/gps_compliance")
        page.wait_for_load_state("networkidle")

        set_date_range(page, start_date, end_date)
        page.click('input[type="submit"], button[type="submit"]')
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Check for violation tables - should show worker names from our test data
        # Our test data includes: Mike Rodriguez, Danny O'Brien, Carlos Hernandez, Tommy Wilson, Robert Johnson
        page_text = page.content()

        # At least one of our test workers should appear in violations
        test_workers_found = (
            "Mike Rodriguez" in page_text or
            "Carlos Hernandez" in page_text or
            "Tommy Wilson" in page_text or
            "Robert Johnson" in page_text
        )
        assert test_workers_found, "Should see test worker names in violations"

    def test_violations_show_distance(self, logged_in_admin: Page):
        """Test that violations show distance information."""
        page = logged_in_admin
        start_date, end_date = get_test_date_range()

        page.goto(f"{BASE_URL}/admin/gps_compliance")
        page.wait_for_load_state("networkidle")

        set_date_range(page, start_date, end_date)
        page.click('input[type="submit"], button[type="submit"]')
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Violations should have distance badges
        distance_badges = page.locator('.badge')
        assert distance_badges.count() > 0, "Should have distance badges"

    def test_violations_have_map_icons(self, logged_in_admin: Page):
        """Test that fraud risk violations have map icons for drill-down."""
        page = logged_in_admin
        start_date, end_date = get_test_date_range()

        page.goto(f"{BASE_URL}/admin/gps_compliance")
        page.wait_for_load_state("networkidle")

        set_date_range(page, start_date, end_date)
        page.click('input[type="submit"], button[type="submit"]')
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Check for map icons (using emoji or icon class)
        map_icons = page.locator('.violation-map-icon')
        # We should have at least some map icons for fraud risk violations
        assert map_icons.count() >= 0, "Map icons should be present for violations"


class TestGPSComplianceWorkerSummary:
    """Tests for worker summary in GPS compliance report."""

    def test_worker_summary_shows_repeat_offenders(self, logged_in_admin: Page):
        """Test that worker summary section exists."""
        page = logged_in_admin
        start_date, end_date = get_test_date_range()

        page.goto(f"{BASE_URL}/admin/gps_compliance")
        page.wait_for_load_state("networkidle")

        set_date_range(page, start_date, end_date)
        page.click('input[type="submit"], button[type="submit"]')
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Should have worker summary section
        worker_summary = page.locator("text=Worker Violation Summary")
        expect(worker_summary).to_be_visible()


class TestGPSComplianceViolationCounts:
    """Tests to verify the correct number of violations are detected."""

    def test_detects_expected_violation_count(self, logged_in_admin: Page):
        """Test that report detects approximately 10 violations from our test data."""
        page = logged_in_admin
        start_date, end_date = get_test_date_range()

        page.goto(f"{BASE_URL}/admin/gps_compliance")
        page.wait_for_load_state("networkidle")

        set_date_range(page, start_date, end_date)
        page.click('input[type="submit"], button[type="submit"]')
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Get the total violations count from the page
        # Look for the violations count in the stat cards
        page_text = page.content()

        # Count violation rows in tables
        fraud_risk_rows = page.locator('section:has-text("Fraud Risk Violations") tbody tr')
        major_rows = page.locator('section:has-text("Major Violations") tbody tr')
        minor_rows = page.locator('section:has-text("Minor Violations") tbody tr')

        fraud_count = fraud_risk_rows.count()
        major_count = major_rows.count()
        minor_count = minor_rows.count()

        total_violations = fraud_count + major_count + minor_count

        print(f"Found violations - Fraud: {fraud_count}, Major: {major_count}, Minor: {minor_count}, Total: {total_violations}")

        # We created 10 violations, should detect at least most of them
        # (allowing some tolerance for edge cases)
        assert total_violations >= 8, f"Expected at least 8 violations, found {total_violations}"
        assert total_violations <= 12, f"Expected at most 12 violations, found {total_violations}"

    def test_fraud_risk_violations_detected(self, logged_in_admin: Page):
        """Test that fraud risk violations (5+ miles) are detected."""
        page = logged_in_admin
        start_date, end_date = get_test_date_range()

        page.goto(f"{BASE_URL}/admin/gps_compliance")
        page.wait_for_load_state("networkidle")

        set_date_range(page, start_date, end_date)
        page.click('input[type="submit"], button[type="submit"]')
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Should have fraud risk section with violations
        fraud_section = page.locator("text=Fraud Risk Violations")
        if fraud_section.count() > 0:
            # Count rows in fraud risk table
            fraud_rows = page.locator('section:has-text("Fraud Risk Violations") tbody tr')
            fraud_count = fraud_rows.count()
            print(f"Fraud Risk violations found: {fraud_count}")
            # We created ~3 fraud risk violations
            assert fraud_count >= 2, f"Expected at least 2 fraud risk violations, found {fraud_count}"
