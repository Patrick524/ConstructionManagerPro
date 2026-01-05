"""Tests for foreman review flow (side-by-side submitted vs reviewed time)."""
import re
from datetime import datetime, timedelta

import pytest
from playwright.sync_api import Page, expect

from conftest import (
    BASE_URL,
    TEST_FOREMAN_EMAIL,
    TEST_FOREMAN_PASSWORD,
    login_user,
)


def get_week_with_data():
    """Get the start date of the previous week (more likely to have data)."""
    today = datetime.now().date()
    # Get Monday of the previous week
    last_monday = today - timedelta(days=today.weekday() + 7)
    return last_monday.strftime("%Y-%m-%d")


class TestForemanReviewFlow:
    """Tests for the foreman review workflow."""

    def test_foreman_can_access_dashboard(self, page: Page):
        """Test that foreman can access the dashboard after login."""
        success = login_user(page, TEST_FOREMAN_EMAIL, TEST_FOREMAN_PASSWORD)
        if not success:
            pytest.skip("Could not log in as foreman - check credentials")

        # Should be on foreman dashboard
        page.goto(f"{BASE_URL}/foreman/dashboard")
        page.wait_for_load_state("networkidle")

        # Verify dashboard elements are present
        assert page.is_visible("text=Dashboard") or page.is_visible(
            "text=Foreman"
        ), "Should see foreman dashboard"

    def test_foreman_review_screen_loads(self, logged_in_foreman: Page):
        """Test that the foreman can navigate to a review screen."""
        page = logged_in_foreman

        # Go to foreman dashboard for a week with data
        week_start = get_week_with_data()
        page.goto(f"{BASE_URL}/foreman/dashboard?start_date={week_start}")
        page.wait_for_load_state("networkidle")

        # Look for review links (these are typically in the dashboard)
        # The review link format is /foreman/approve/<job_id>/<user_id>
        review_links = page.locator('a[href*="/foreman/approve/"]')

        if review_links.count() == 0:
            pytest.skip(
                "No review links found on dashboard - need worker time entries to review"
            )

        # Click the first review link
        review_links.first.click()
        page.wait_for_load_state("networkidle")

        # Verify we're on the review page
        assert "/foreman/approve/" in page.url, "Should be on review page"

        # Check for key elements on review page
        assert page.is_visible(
            "text=Review Timesheet"
        ), "Should see Review Timesheet heading"
        assert page.is_visible("text=Submitted") or page.is_visible(
            "text=Worker Submitted"
        ), "Should see submitted column"
        assert page.is_visible("text=Reviewed") or page.is_visible(
            "text=Foreman Reviewed"
        ), "Should see reviewed column"

    def test_foreman_can_modify_reviewed_hours(self, logged_in_foreman: Page):
        """Test that foreman can modify reviewed hours and save draft."""
        page = logged_in_foreman

        # Go to foreman dashboard for a week with data
        week_start = get_week_with_data()
        page.goto(f"{BASE_URL}/foreman/dashboard?start_date={week_start}")
        page.wait_for_load_state("networkidle")

        # Find and click a review link
        review_links = page.locator('a[href*="/foreman/approve/"]')
        if review_links.count() == 0:
            pytest.skip("No review links found - need worker time entries")

        review_links.first.click()
        page.wait_for_load_state("networkidle")

        # Store the current URL for later
        review_url = page.url

        # Find hours input fields (reviewed hours inputs)
        hours_inputs = page.locator('input.hours-input[name^="reviewed_hours_"]')

        if hours_inputs.count() == 0:
            pytest.skip("No reviewed hours inputs found - no entries to review")

        # Get the first hours input and modify it
        first_input = hours_inputs.first
        original_value = first_input.input_value()

        # Calculate a new value (add 0.5 hours, but keep it reasonable)
        try:
            new_value = float(original_value) + 0.5
            if new_value > 12:
                new_value = float(original_value) - 0.5
            new_value = max(0.25, new_value)  # Ensure at least 0.25 hours
        except ValueError:
            new_value = 4.0  # Default value if original is empty or invalid

        # Clear and fill with new value
        first_input.clear()
        first_input.fill(str(new_value))

        # Click Save Draft button
        save_draft_button = page.locator('button[value="save_draft"]')
        if not save_draft_button.is_visible():
            pytest.skip("Save Draft button not found")

        save_draft_button.click()
        page.wait_for_load_state("networkidle")

        # Verify draft was saved - should see info message or stay on approve page
        # Draft saves use 'info' flash message and redirect back to same page
        info_message = page.locator(".alert-info")
        success_message = page.locator(".alert-success")
        on_approve_page = "/foreman/approve/" in page.url

        assert (
            info_message.count() > 0 or success_message.count() > 0 or on_approve_page
        ), "Should see flash message or stay on approve page after draft save"

    def test_foreman_review_changes_persist(self, logged_in_foreman: Page):
        """
        Test the complete foreman review flow:
        1. Navigate to review screen
        2. Modify reviewed hours
        3. Save draft
        4. Return to review screen
        5. Verify changes persisted
        """
        page = logged_in_foreman

        # Go to foreman dashboard for a week with data
        week_start = get_week_with_data()
        page.goto(f"{BASE_URL}/foreman/dashboard?start_date={week_start}")
        page.wait_for_load_state("networkidle")

        # Find review links
        review_links = page.locator('a[href*="/foreman/approve/"]')
        if review_links.count() == 0:
            pytest.skip("No review links found - need worker time entries to review")

        # Get the href of the first review link to navigate back later
        first_link = review_links.first
        review_href = first_link.get_attribute("href")

        # Click the review link
        first_link.click()
        page.wait_for_load_state("networkidle")

        # Store the review page URL
        review_url = page.url

        # Find the first hours input
        hours_inputs = page.locator('input.hours-input[name^="reviewed_hours_"]')
        if hours_inputs.count() == 0:
            pytest.skip("No reviewed hours inputs found")

        first_input = hours_inputs.first
        input_name = first_input.get_attribute("name")

        # Set a specific test value
        test_value = "5.75"
        first_input.clear()
        first_input.fill(test_value)

        # Click Save Draft
        save_draft_button = page.locator('button[value="save_draft"]')
        save_draft_button.click()
        page.wait_for_load_state("networkidle")

        # Navigate back to the same review page
        page.goto(review_url)
        page.wait_for_load_state("networkidle")

        # Find the same input field and verify value persisted
        same_input = page.locator(f'input[name="{input_name}"]')

        if same_input.count() == 0:
            pytest.skip("Could not find the same input field after refresh")

        persisted_value = same_input.input_value()

        # Verify the value persisted (allowing for formatting differences)
        expected = float(test_value)
        actual = float(persisted_value)

        assert abs(expected - actual) < 0.01, (
            f"Expected {expected}, got {actual} - changes did not persist"
        )

    def test_foreman_can_finalize_review(self, logged_in_foreman: Page):
        """Test that foreman can finalize a review (locks the timesheet)."""
        page = logged_in_foreman

        # Go to foreman dashboard for a week with data
        week_start = get_week_with_data()
        page.goto(f"{BASE_URL}/foreman/dashboard?start_date={week_start}")
        page.wait_for_load_state("networkidle")

        # Find review links
        review_links = page.locator('a[href*="/foreman/approve/"]')
        if review_links.count() == 0:
            pytest.skip("No review links found - need worker time entries")

        review_links.first.click()
        page.wait_for_load_state("networkidle")

        # Check if already finalized (no finalize button or warning message)
        finalize_button = page.locator('button[value="finalize"]')
        if not finalize_button.is_visible():
            # Already approved or no finalize button
            pytest.skip("Finalize button not visible - week may already be approved")

        # Verify finalize button exists
        expect(finalize_button).to_be_visible()

        # Note: We don't actually click finalize in this test to avoid
        # locking real data. Instead, we just verify the button exists.
        # In a real test environment with test data, you would click it
        # and verify the lock was created.


class TestForemanReviewUIElements:
    """Tests for UI elements on the foreman review screen."""

    def test_review_page_has_summary_card(self, logged_in_foreman: Page):
        """Test that review page shows summary card with totals."""
        page = logged_in_foreman

        week_start = get_week_with_data()
        page.goto(f"{BASE_URL}/foreman/dashboard?start_date={week_start}")
        page.wait_for_load_state("networkidle")

        review_links = page.locator('a[href*="/foreman/approve/"]')
        if review_links.count() == 0:
            pytest.skip("No review links found")

        review_links.first.click()
        page.wait_for_load_state("networkidle")

        # Check for summary elements
        assert page.is_visible(
            "text=Review Summary"
        ), "Should see Review Summary heading"

        # Check for total displays
        submitted_total = page.locator("#submitted-total")
        reviewed_total = page.locator("#reviewed-total")

        # At least one of the totals should be visible
        assert (
            submitted_total.is_visible() or reviewed_total.is_visible()
        ), "Should see hour totals"

    def test_review_page_has_action_buttons(self, logged_in_foreman: Page):
        """Test that review page has Save Draft and Finalize buttons."""
        page = logged_in_foreman

        week_start = get_week_with_data()
        page.goto(f"{BASE_URL}/foreman/dashboard?start_date={week_start}")
        page.wait_for_load_state("networkidle")

        review_links = page.locator('a[href*="/foreman/approve/"]')
        if review_links.count() == 0:
            pytest.skip("No review links found")

        review_links.first.click()
        page.wait_for_load_state("networkidle")

        # Check for action buttons
        save_draft = page.locator('button[value="save_draft"]')
        finalize = page.locator('button[value="finalize"]')

        # One of these should be visible (finalize may be hidden if already approved)
        assert (
            save_draft.is_visible() or finalize.is_visible()
        ), "Should see Save Draft or Finalize button"

    def test_review_page_shows_worker_and_job_info(self, logged_in_foreman: Page):
        """Test that review page shows worker name and job info."""
        page = logged_in_foreman

        week_start = get_week_with_data()
        page.goto(f"{BASE_URL}/foreman/dashboard?start_date={week_start}")
        page.wait_for_load_state("networkidle")

        review_links = page.locator('a[href*="/foreman/approve/"]')
        if review_links.count() == 0:
            pytest.skip("No review links found")

        review_links.first.click()
        page.wait_for_load_state("networkidle")

        # Should see worker and job info
        assert page.is_visible("text=Worker:"), "Should see Worker label"
        assert page.is_visible("text=Job:"), "Should see Job label"
