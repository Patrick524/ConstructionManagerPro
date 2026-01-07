"""Tests for System Message feature across all user roles."""
import pytest
from playwright.sync_api import Page, expect

from conftest import BASE_URL


class TestSystemMessageWorker:
    """Tests for system message visibility for worker role."""

    def test_worker_sees_system_message(self, logged_in_worker: Page):
        """Test that worker sees the system message banner."""
        page = logged_in_worker

        # Worker should be on their page after login
        page.wait_for_load_state("networkidle")

        # Check for system message banner
        banner = page.locator(".system-message-banner")
        expect(banner).to_be_visible()

        # Verify the message content
        expect(banner).to_contain_text("Timesheets due Monday 8am.")

    def test_worker_message_contains_bullhorn_icon(self, logged_in_worker: Page):
        """Test that the message banner includes the bullhorn icon."""
        page = logged_in_worker
        page.wait_for_load_state("networkidle")

        # Check for bullhorn icon
        icon = page.locator(".system-message-banner .fa-bullhorn")
        expect(icon).to_be_visible()


class TestSystemMessageForeman:
    """Tests for system message visibility for foreman role."""

    def test_foreman_sees_system_message(self, logged_in_foreman: Page):
        """Test that foreman sees the system message banner."""
        page = logged_in_foreman

        # Foreman should be on dashboard after login
        page.wait_for_load_state("networkidle")

        # Check for system message banner
        banner = page.locator(".system-message-banner")
        expect(banner).to_be_visible()

        # Verify the message content
        expect(banner).to_contain_text("Timesheets due Monday 8am.")

    def test_foreman_message_at_bottom_of_page(self, logged_in_foreman: Page):
        """Test that the message banner is fixed at the bottom."""
        page = logged_in_foreman
        page.wait_for_load_state("networkidle")

        # Check that banner exists and has fixed positioning (via CSS)
        banner = page.locator(".system-message-banner")
        expect(banner).to_be_visible()

        # Verify it's styled as fixed position (checking computed style)
        position = banner.evaluate("el => getComputedStyle(el).position")
        assert position == "fixed", f"Expected fixed position, got {position}"


class TestSystemMessageAdmin:
    """Tests for system message visibility and management for admin role."""

    def test_admin_sees_system_message(self, logged_in_admin: Page):
        """Test that admin sees the system message banner."""
        page = logged_in_admin

        # Admin should be on dashboard after login
        page.wait_for_load_state("networkidle")

        # Check for system message banner
        banner = page.locator(".system-message-banner")
        expect(banner).to_be_visible()

        # Verify the message content
        expect(banner).to_contain_text("Timesheets due Monday 8am.")

    def test_admin_can_access_settings_page(self, logged_in_admin: Page):
        """Test that admin can access the settings page."""
        page = logged_in_admin

        # Navigate to settings
        page.goto(f"{BASE_URL}/admin/settings")
        page.wait_for_load_state("networkidle")

        # Verify we're on the settings page
        expect(page).to_have_url(f"{BASE_URL}/admin/settings")

        # Check that the settings page has the system message form
        expect(page.locator("h1")).to_contain_text("Settings")
        expect(page.locator("#message_text")).to_be_visible()

    def test_admin_settings_shows_current_message(self, logged_in_admin: Page):
        """Test that settings page displays the current message."""
        page = logged_in_admin

        page.goto(f"{BASE_URL}/admin/settings")
        page.wait_for_load_state("networkidle")

        # Check that the textarea contains the current message
        textarea = page.locator("#message_text")
        expect(textarea).to_have_value("Timesheets due Monday 8am.")

    def test_admin_settings_has_role_checkboxes(self, logged_in_admin: Page):
        """Test that settings page has checkboxes for all three roles."""
        page = logged_in_admin

        page.goto(f"{BASE_URL}/admin/settings")
        page.wait_for_load_state("networkidle")

        # Check for all three role checkboxes
        admin_checkbox = page.locator("#show_to_admin")
        foreman_checkbox = page.locator("#show_to_foreman")
        worker_checkbox = page.locator("#show_to_worker")

        expect(admin_checkbox).to_be_visible()
        expect(foreman_checkbox).to_be_visible()
        expect(worker_checkbox).to_be_visible()

        # All should be checked (since message is shown to all roles)
        expect(admin_checkbox).to_be_checked()
        expect(foreman_checkbox).to_be_checked()
        expect(worker_checkbox).to_be_checked()

    def test_admin_settings_nav_link_exists(self, logged_in_admin: Page):
        """Test that Settings link appears in admin navigation."""
        page = logged_in_admin
        page.wait_for_load_state("networkidle")

        # Check for Settings nav link
        settings_link = page.locator("a.nav-link >> text=Settings")
        expect(settings_link).to_be_visible()


class TestSystemMessageNotLoggedIn:
    """Tests for system message when not logged in."""

    def test_message_not_shown_when_not_logged_in(self, page: Page):
        """Test that system message is not shown to unauthenticated users."""
        page.goto(f"{BASE_URL}/login")
        page.wait_for_load_state("networkidle")

        # The banner div should not exist
        banner = page.locator(".system-message-banner")
        expect(banner).to_have_count(0)
