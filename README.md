# FileVault

FileVault is a simple, self-hosted file sharing application designed for ease of use. It allows you to quickly share files between devices using a secure, QR-code-based login system, with an alternative 5-digit code for convenience.

## Features

- **Easy Authentication:** Log in to new devices quickly by scanning a QR code or entering a 5-digit code from an already authenticated device.
- **File Management:** Upload, download, and organize your files and folders.
- **Public/Private Accounts:** Keep your files private with password protection, or make them public for easy sharing.
- **PWA Support:** Install FileVault as a Progressive Web App (PWA) on your mobile device for a native-like experience.
- **Share Target:** Use your device's native share functionality to send files directly to FileVault.
- **Dark/Light/Barbie-Themed:** Choose between a dark, light, or barbie-themed interface.

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

### Logging In

-   **QR Code:** On a new device, the login page will display a QR code. Scan this code with a device that is already logged in to authenticate the new device.
-   **5-Digit Code:** Alternatively, you can use the 5-digit code displayed on the login page. On an authenticated device, click "Enter Code" and type in the 5-digit code to log in the new device.

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
