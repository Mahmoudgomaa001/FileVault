# FileVault

FileVault is a simple, self-hosted file sharing application designed for ease of use. It allows you to quickly share files between devices using a secure, QR-code-based login system, with an alternative 6-digit code for convenience.

## Features

- **Multiple Authentication Methods:**
    - **QR Code:** Scan a QR code from a logged-in device to instantly authenticate a new device.
    - **"Get Code" (Pull):** Generate a temporary 6-digit code on an authenticated device and enter it on a new device to log in.
    - **"Approve with Code" (Push):** View a 6-digit code on a new device's login screen and enter it on an authenticated device to approve the session.
- **File Management:** Upload, download, and organize your files and folders.
- **Public/Private Accounts:** Keep your files private with password protection, or make them public for easy sharing.
- **PWA Support:** Install FileVault as a Progressive Web App (PWA) on your mobile device for a native-like experience.
- **Share Target:** Use your device's native share functionality to send files directly to FileVault.
- **Theming:** Choose between a dark, light, or barbie-themed interface.

## Setup and Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/AskJules/qr-file-transfer.git
    cd qr-file-transfer
    ```

2.  **Install dependencies:**
    Make sure you have Python 3 and `pip` installed. Then, install the required packages:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the application:**
    ```bash
    python app.py
    ```
    The application will be available at `http://0.0.0.0:5000`. You can access it from other devices on your local network using your computer's local IP address (e.g., `http://192.168.1.10:5000`).

## Usage

### Logging In a New Device

There are three ways to log in a new device using a device that is already authenticated:

#### Method 1: QR Code
1.  On the new device, go to the login page. A QR code will be displayed.
2.  On your authenticated device, click the "My QR" button in the header. This will open a QR scanner.
3.  Scan the QR code from the new device to log it in.

#### Method 2: "Get Code" (Pull method)
This is useful when you can't use a camera. You "pull" a code from your authenticated device.
1.  On your **authenticated device**, click the "**Get Code**" button in the header. A modal will appear with a 6-digit code that is valid for 5 minutes.
2.  On the **new device**, go to the login page.
3.  Enter the 6-digit code into the input field and click "Login with Code".

#### Method 3: "Approve with Code" (Push method)
This is also useful when you can't use a camera. You "push" an approval from your authenticated device.
1.  On the **new device**, go to the login page. You will see a 6-digit code displayed below the QR code.
2.  On your **authenticated device**, click the "**Approve**" button in the header.
3.  Enter the 6-digit code that you see on the new device's screen and click "Approve Device".

### Managing Files

-   **Upload:** Drag and drop files into the upload area, or click to select files.
-   **Download:** Click the download icon on any file.
-   **Preview:** Click on a file to preview it directly in the browser (for supported file types).
-   **Folders:** Create new folders to organize your files.
-   **Deleting:** Delete files and folders using the trash icon.

### Accounts

Each device is initially assigned a unique, randomly generated account name (e.g., `lucky-duck-042`). The first device to use an account becomes its admin. The admin device can:
-   Change the account's privacy settings (public or private with a password).
-   Create new accounts.
-   Rename accounts.
-   Transfer admin rights to another device.
