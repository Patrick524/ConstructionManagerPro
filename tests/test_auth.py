"""Tests for authentication (login) functionality."""
import pytest
from playwright.sync_api import Page, expect

from conftest import (
    BASE_URL,
    TEST_WORKER_EMAIL,
    TEST_WORKER_PASSWORD,
    TEST_FOREMAN_EMAIL,
    TEST_FOREMAN_PASSWORD,
    login_user,
)


class TestWorkerLogin:
    """Tests for worker login flow."""

    def test_worker_can_login(self, page: Page):
        """Test that a worker can log in successfully."""
        # Navigate to login page
        page.goto(f"{BASE_URL}/login")

        # Verify we're on the login page
        expect(page).to_have_url(f"{BASE_URL}/login")

        # Fill in credentials
        page.fill('input[name="email"]', TEST_WORKER_EMAIL)
        page.fill('input[name="password"]', TEST_WORKER_PASSWORD)

        # Submit the form (could be <button> or <input type="submit">)
        page.click('input[type="submit"], button[type="submit"]')

        # Wait for navigation
        page.wait_for_load_state("networkidle")

        # After successful login, worker should be redirected to timesheet
        assert "/login" not in page.url, "Worker should be redirected after login"
        assert "worker" in page.url or "timesheet" in page.url, (
            f"Worker should be on worker page, got: {page.url}"
        )

    def test_worker_login_with_invalid_password(self, page: Page):
        """Test that login fails with invalid password."""
        page.goto(f"{BASE_URL}/login")

        page.fill('input[name="email"]', TEST_WORKER_EMAIL)
        page.fill('input[name="password"]', "wrongpassword123")

        page.click('input[type="submit"], button[type="submit"]')
        page.wait_for_load_state("networkidle")

        # Should still be on login page or see error message
        # Check for flash message or that we're still on login page
        is_on_login = "/login" in page.url
        has_error = page.is_visible(".alert-danger") or page.is_visible(".flash-error")

        assert is_on_login or has_error, "Should show error or stay on login page"


class TestForemanLogin:
    """Tests for foreman login flow."""

    def test_foreman_can_login(self, page: Page):
        """Test that a foreman can log in successfully."""
        page.goto(f"{BASE_URL}/login")

        expect(page).to_have_url(f"{BASE_URL}/login")

        page.fill('input[name="email"]', TEST_FOREMAN_EMAIL)
        page.fill('input[name="password"]', TEST_FOREMAN_PASSWORD)

        page.click('input[type="submit"], button[type="submit"]')
        page.wait_for_load_state("networkidle")

        # Foreman should be redirected to their dashboard
        assert "/login" not in page.url, "Foreman should be redirected after login"
        assert "foreman" in page.url or "dashboard" in page.url, (
            f"Foreman should be on foreman page, got: {page.url}"
        )

    def test_foreman_redirected_to_dashboard(self, page: Page):
        """Test that foreman is redirected to the foreman dashboard after login."""
        success = login_user(page, TEST_FOREMAN_EMAIL, TEST_FOREMAN_PASSWORD)

        if not success:
            pytest.skip("Could not log in as foreman - check credentials")

        # Foreman should be on foreman dashboard
        assert "foreman" in page.url.lower() or "dashboard" in page.url.lower(), (
            f"Foreman should be on foreman dashboard, got: {page.url}"
        )
