"""Shared fixtures for Playwright tests."""
import os
import pytest
from playwright.sync_api import Page


# Base URL for the application
BASE_URL = "https://app.buildertimepro.com"


# Test user credentials - set via environment variables or use defaults
# To override, set environment variables:
#   WORKER_EMAIL, WORKER_PASSWORD
#   FOREMAN_EMAIL, FOREMAN_PASSWORD
TEST_WORKER_EMAIL = os.environ.get("WORKER_EMAIL", "worker1@example.com")
TEST_WORKER_PASSWORD = os.environ.get("WORKER_PASSWORD", "password123")
TEST_FOREMAN_EMAIL = os.environ.get("FOREMAN_EMAIL", "foreman@example.com")
TEST_FOREMAN_PASSWORD = os.environ.get("FOREMAN_PASSWORD", "password123")
TEST_ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")
TEST_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "password123")


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context for all tests."""
    return {
        **browser_context_args,
        "ignore_https_errors": True,
    }


def login_user(page: Page, email: str, password: str) -> bool:
    """
    Login a user with the given credentials.

    Args:
        page: Playwright page object
        email: User's email address
        password: User's password

    Returns:
        True if login succeeded, False otherwise
    """
    page.goto(f"{BASE_URL}/login")

    # Fill in login form
    page.fill('input[name="email"]', email)
    page.fill('input[name="password"]', password)

    # Click submit button (could be <button> or <input type="submit">)
    page.click('input[type="submit"], button[type="submit"]')

    # Wait for navigation and check if login succeeded
    page.wait_for_load_state("networkidle")

    # Check we're not still on the login page
    return "/login" not in page.url


@pytest.fixture
def logged_in_worker(page: Page):
    """Fixture that logs in as a worker and returns the page."""
    success = login_user(page, TEST_WORKER_EMAIL, TEST_WORKER_PASSWORD)
    if not success:
        pytest.skip(f"Could not log in as worker with email {TEST_WORKER_EMAIL}")
    return page


@pytest.fixture
def logged_in_foreman(page: Page):
    """Fixture that logs in as a foreman and returns the page."""
    success = login_user(page, TEST_FOREMAN_EMAIL, TEST_FOREMAN_PASSWORD)
    if not success:
        pytest.skip(f"Could not log in as foreman with email {TEST_FOREMAN_EMAIL}")
    return page


@pytest.fixture
def logged_in_admin(page: Page):
    """Fixture that logs in as an admin and returns the page."""
    success = login_user(page, TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD)
    if not success:
        pytest.skip(f"Could not log in as admin with email {TEST_ADMIN_EMAIL}")
    return page


@pytest.fixture
def logout(page: Page):
    """Logout the current user."""
    page.goto(f"{BASE_URL}/logout")
    page.wait_for_load_state("networkidle")
