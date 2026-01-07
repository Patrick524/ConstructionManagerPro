"""Tests for passkey (WebAuthn) functionality."""
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "https://app.buildertimepro.com"

# User agent strings for different devices
WINDOWS_CHROME_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
MACOS_SAFARI_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
IPHONE_SAFARI_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
IPAD_SAFARI_UA = "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"


class TestPasskeyLoginVisibility:
    """Test that passkey login button only shows on iOS devices."""

    def test_passkey_hidden_on_windows(self, browser):
        """Passkey button should NOT be visible on Windows."""
        context = browser.new_context(
            user_agent=WINDOWS_CHROME_UA,
            ignore_https_errors=True,
        )
        page = context.new_page()

        page.goto(f"{BASE_URL}/login")
        page.wait_for_load_state("networkidle")

        # Wait for JavaScript to execute
        page.wait_for_timeout(1000)

        # The passkey section should be hidden (display: none)
        passkey_section = page.locator("#passkey-section")
        expect(passkey_section).to_be_hidden()

        context.close()

    def test_passkey_hidden_on_macos(self, browser):
        """Passkey button should NOT be visible on macOS (desktop)."""
        context = browser.new_context(
            user_agent=MACOS_SAFARI_UA,
            ignore_https_errors=True,
        )
        page = context.new_page()

        page.goto(f"{BASE_URL}/login")
        page.wait_for_load_state("networkidle")

        # Wait for JavaScript to execute
        page.wait_for_timeout(1000)

        # The passkey section should be hidden
        passkey_section = page.locator("#passkey-section")
        expect(passkey_section).to_be_hidden()

        context.close()

    def test_passkey_section_exists_in_html(self, browser):
        """Verify passkey section exists in HTML (just hidden by JS)."""
        context = browser.new_context(
            user_agent=WINDOWS_CHROME_UA,
            ignore_https_errors=True,
        )
        page = context.new_page()

        page.goto(f"{BASE_URL}/login")
        page.wait_for_load_state("networkidle")

        # The passkey section should exist in DOM
        passkey_section = page.locator("#passkey-section")
        expect(passkey_section).to_have_count(1)

        # The button should exist inside
        passkey_btn = page.locator("#passkey-login-btn")
        expect(passkey_btn).to_have_count(1)

        context.close()


class TestPasskeyManagementPage:
    """Test the worker passkey management page."""

    def test_passkey_page_requires_login(self, browser):
        """Passkey management page should require authentication."""
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        page.goto(f"{BASE_URL}/worker/passkeys")
        page.wait_for_load_state("networkidle")

        # Should redirect to login
        assert "/login" in page.url

        context.close()

    def test_passkey_page_shows_ios_message_on_windows(self, browser):
        """Non-iOS devices should see 'iPhone Required' message."""
        context = browser.new_context(
            user_agent=WINDOWS_CHROME_UA,
            ignore_https_errors=True,
        )
        page = context.new_page()

        # Login as worker first
        page.goto(f"{BASE_URL}/login")
        page.fill('input[name="email"]', "worker1@example.com")
        page.fill('input[name="password"]', "password123")
        page.click('input[type="submit"], button[type="submit"]')
        page.wait_for_load_state("networkidle")

        # Go to passkey management page
        page.goto(f"{BASE_URL}/worker/passkeys")
        page.wait_for_load_state("networkidle")

        # Wait for JavaScript to execute
        page.wait_for_timeout(1000)

        # Should show "iPhone Required" message
        support_message = page.locator("#passkey-support-message")
        expect(support_message).to_contain_text("iPhone Required")

        # Registration form should be hidden
        register_form = page.locator("#passkey-register-form")
        expect(register_form).to_be_hidden()

        context.close()

    def test_passkey_page_accessible_to_worker(self, browser):
        """Workers should be able to access the passkey management page."""
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        # Login as worker
        page.goto(f"{BASE_URL}/login")
        page.fill('input[name="email"]', "worker1@example.com")
        page.fill('input[name="password"]', "password123")
        page.click('input[type="submit"], button[type="submit"]')
        page.wait_for_load_state("networkidle")

        # Go to passkey management page
        page.goto(f"{BASE_URL}/worker/passkeys")
        page.wait_for_load_state("networkidle")

        # Should be on the passkeys page
        assert "/worker/passkeys" in page.url

        # Should see the page title
        expect(page.locator("h1")).to_contain_text("Passkey Settings")

        context.close()

    def test_passkey_link_in_worker_menu(self, browser):
        """Workers should see Passkey Settings link in dropdown menu."""
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        # Login as worker
        page.goto(f"{BASE_URL}/login")
        page.fill('input[name="email"]', "worker1@example.com")
        page.fill('input[name="password"]', "password123")
        page.click('input[type="submit"], button[type="submit"]')
        page.wait_for_load_state("networkidle")

        # Open user dropdown menu
        page.click("#navbarDropdown")
        page.wait_for_timeout(500)

        # Should see Passkey Settings link
        passkey_link = page.locator('a:has-text("Passkey Settings")')
        expect(passkey_link).to_be_visible()

        context.close()
