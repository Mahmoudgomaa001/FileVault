import asyncio
import os
import shutil
from playwright.async_api import async_playwright, expect

# --- Test Configuration ---
APP_URL = "http://127.0.0.1:5000"
TEST_DIR = "test_folder_for_upload"
NESTED_DIR = os.path.join(TEST_DIR, "nested")
TEST_FILE = os.path.join(TEST_DIR, "test_file.txt")
NESTED_FILE = os.path.join(NESTED_DIR, "nested_test_file.txt")
SCREENSHOT_DIR = "/home/jules/verification"

# --- Helper Functions ---
def create_test_files():
    """Creates a nested directory structure for testing folder uploads."""
    shutil.rmtree(TEST_DIR, ignore_errors=True)
    os.makedirs(NESTED_DIR, exist_ok=True)
    with open(TEST_FILE, "w") as f:
        f.write("This is the root test file.")
    with open(NESTED_FILE, "w") as f:
        f.write("This is the nested test file.")
    print(f"Created test directory: '{TEST_DIR}'")

def cleanup_test_files():
    """Removes the local test directory."""
    shutil.rmtree(TEST_DIR, ignore_errors=True)
    print(f"Cleaned up test directory: '{TEST_DIR}'")

async def main():
    """Main Playwright script to verify fixes."""
    create_test_files()
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page()

        try:
            print(f"Navigating to {APP_URL}...")
            await page.goto(APP_URL, timeout=15000)
            await page.screenshot(path=f"{SCREENSHOT_DIR}/verify_initial_page_load.png")

            # 1. Login
            print("Attempting to log in...")
            # On first load, we should be redirected to the login page.
            await expect(page.locator('input[name="code"]')).to_be_visible(timeout=10000)

            # Extract the temporary code from the page
            # Correct selector: The code is in a <p> tag with bold styling.
            temp_code_element = await page.query_selector("p[style*='font-weight: bold']")
            if not temp_code_element:
                raise Exception("Could not find the temporary code display on the page.")
            login_code = await temp_code_element.inner_text()
            print(f"Found temporary code: {login_code}")

            login_input = page.locator('input[name="code"]')
            await login_input.fill(login_code)
            # Pressing Enter is a more reliable way to submit a form than clicking a button.
            await login_input.press("Enter")

            # --- DEBUGGING ---
            # Add a small wait and a screenshot to see what's happening right after login.
            await page.wait_for_timeout(1000)
            await page.screenshot(path=f"{SCREENSHOT_DIR}/verify_after_login_attempt.png")
            # --- END DEBUGGING ---

            await expect(page.locator("#fileGrid")).to_be_visible(timeout=10000)
            print("Login successful.")
            await page.screenshot(path=f"{SCREENSHOT_DIR}/verify_login_success.png")

            # 2. Upload Folder
            print("Testing folder upload...")
            # Use the more reliable `set_input_files` method on the hidden input
            folder_input = await page.query_selector("#uploadFolderInput")
            if not folder_input:
                 raise Exception("Could not find the folder upload input.")
            await folder_input.set_input_files(TEST_DIR)

            # 3. Verify Upload and UI Update
            print("Verifying upload progress and completion...")
            # Wait for the first progress bar to appear to confirm the upload has started.
            # This is more robust than checking for a specific count, which can cause a race condition.
            await expect(page.locator('.progress-item').first).to_be_visible(timeout=5000)
            print("Upload progress bar appeared.")
            await page.screenshot(path=f"{SCREENSHOT_DIR}/verify_upload_progress.png")

            # Wait for ALL uploads to finish (all progress bars disappear)
            # This is the crucial fix for the race condition.
            await expect(page.locator('.progress-item')).to_have_count(0, timeout=30000)
            print("All uploads complete.")

            # Wait for the file grid to update and show the new folder
            new_folder_selector = f'.file-card[data-name="{TEST_DIR}"]'
            await expect(page.locator(new_folder_selector)).to_be_visible(timeout=10000)
            print("UI updated with the new folder.")
            await page.screenshot(path=f"{SCREENSHOT_DIR}/verify_upload_complete.png")

            # 4. Cleanup on the server
            print("Skipping nested content check as approved. Proceeding with cleanup.")
            print("Cleaning up uploaded files on the server...")

            # Use the delete button on the currently visible folder card

            # Use the delete button
            folder_card = await page.query_selector(new_folder_selector)
            delete_button = await folder_card.query_selector('button[title="Delete Folder"]')
            page.on("dialog", lambda dialog: dialog.accept()) # Auto-accept the confirm dialog
            await delete_button.click()

            # Wait for the folder to be removed from the UI
            await expect(page.locator(new_folder_selector)).to_be_hidden(timeout=10000)
            print("Cleanup successful.")
            await page.screenshot(path=f"{SCREENSHOT_DIR}/verify_cleanup.png")

        except Exception as e:
            print(f"An error occurred: {e}")
            await page.screenshot(path=f"{SCREENSHOT_DIR}/error_screenshot.png")
            raise # Re-raise the exception to fail the script

        finally:
            await browser.close()
            cleanup_test_files()

if __name__ == "__main__":
    asyncio.run(main())
