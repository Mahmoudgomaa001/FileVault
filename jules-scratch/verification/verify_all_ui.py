import socket
from playwright.sync_api import sync_playwright, expect

def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        local_ip = get_local_ip()

        # 1. Verify Login Page
        page.goto(f"http://{local_ip}:5000/login", wait_until="networkidle")
        expect(page.locator(".login-container")).to_be_visible()
        page.screenshot(path="jules-scratch/verification/login_page_final.png")

        # 2. Login using the default button
        page.locator('a:has-text("Continue with a new/default account")').click()

        # 3. Verify Settings Modal
        # Wait for the main page to load
        expect(page.locator("#fileGrid")).to_be_visible()

        # Open settings
        page.locator("#settingsBtn").click()
        expect(page.locator("#settingsModal")).to_be_visible()

        # Generate token to see the new elements
        page.locator("#generateTokenBtn").click()

        # Wait for the token and code to appear
        expect(page.locator("#apiTokenInput")).not_to_be_empty()
        expect(page.locator("#permanentCodeInput")).not_to_be_empty()

        # Take screenshot of the settings modal
        page.locator("#settingsModal .modal-content").screenshot(path="jules-scratch/verification/settings_modal.png")

        browser.close()

if __name__ == "__main__":
    run()
