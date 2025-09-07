# FileVault

FileVault is a simple, self-hosted, web-based file sharing application. It allows you to easily transfer files between devices, create multiple user accounts (folders), and share files with others.

## Features

- **Web-based UI**: Access your files from any device with a web browser.
- **Multiple Login Options**:
    - **QR Code Login**: Scan a QR code on a new device with an already logged-in device to approve the session.
    - **6-Digit Code Login**: Log in on a new device by entering a temporary or permanent 6-digit code obtained from an already logged-in device.
- **Multiple Accounts**: Create and manage multiple, separate accounts (folders) from a single admin device.
- **File & Folder Management**: Upload, download, delete, and organize files and folders.
- **Privacy Control**: Set accounts to be public or private (password-protected).
- **PWA Support**: Install the application on your mobile device for a native-like experience.
- **Share Target**: Use the Android/iOS share functionality to send files directly to the application.
- **API Access**: Generate permanent API tokens for programmatic access to your files.

## Getting Started

### Prerequisites

- Python 3.7+
- `pip` for installing dependencies

### Installation

1.  Clone the repository:
    ```sh
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  Install the required dependencies:
    ```sh
    pip install -r requirements.txt
    ```

### Running the Application

1.  Start the Flask server:
    ```sh
    python app.py
    ```

2.  The application will be available at `http://0.0.0.0:5000`. To access it from other devices on your local network, use the IP address of the machine running the server (e.g., `http://192.168.1.10:5000`).

## Login Methods

FileVault provides flexible ways to log in on new devices.

### Method 1: QR Code Scan (Approve a New Device)

1.  On the new device, navigate to the application's URL. You will see a login page with a QR code.
2.  On your already logged-in device, tap the "My QR" button in the header. This will open your camera.
3.  Scan the QR code displayed on the new device.
4.  The new device will be instantly logged into your account.

### Method 2: 6-Digit Code

You can also log in by entering a 6-digit code. You can get this code from an already logged-in device in two ways:

-   **Temporary Code**:
    1.  On your logged-in device, tap the "My QR" button in the header.
    2.  A modal will appear showing both a QR code and a temporary 6-digit code.
    3.  On the new device, enter this 6-digit code into the "Login with Code" form.
    4.  This will log you into the same account. The code is temporary and expires in 10 minutes.

-   **Permanent Code**:
    1.  On your (admin) logged-in device, go to `Settings` > `Permanent API Token & Code`.
    2.  Click "Generate" to get a permanent API token and its corresponding permanent 6-digit code.
    3.  On the new device, enter this 6-digit code into the "Login with Code" form.
    4.  This will grant the new device permanent access via the API token.

## Account Management

The first device to access the application becomes the default "admin" device for the first account. The admin device can:
- Create new accounts (folders).
- Rename accounts.
- Transfer admin rights to another device.
- Set accounts to public or private.
- Generate permanent API tokens.
