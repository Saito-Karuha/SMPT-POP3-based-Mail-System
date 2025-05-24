# GemMail - A Python Email Client/Server Project

A complete client-server email application built with Python. This project features a custom SMTP/POP3 server and a graphical desktop client developed using PyQt6.

## Features

**Server**
* SMTP service for sending emails (`aiosmtpd`).
* POP3 service for retrieving emails (`asyncore`).
* SQLite database for storing user credentials and email data.
* Multi-client concurrency support via threading.

**Client**
* Graphical user interface built with PyQt6.
* Send emails with HTML content and attachments.
* Receive and display a list of emails from the inbox.
* View email content, including headers, body, and downloadable attachments.
* Local caching of sent and received emails in `.eml` format.

## Installation and Setup

Follow these steps to get the GemMail server and client running.

### Step 1: Clone the Repository

```bash
git clone <your-repository-url>
cd GemMail_Project
```

### Step 2: Install Dependencies

It is highly recommended to use a Python virtual environment.

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install required packages
pip install -r requirements.txt
```

### Step 3: Initialize the Database and Users

The server uses an SQLite database to store user information and emails. The project includes a script to set this up.

In your terminal, run the following command:
```bash
python server/database.py
```
This will create a `mail_server.db` file in the project root. It will also create two sample users for you to test with:
* **Email**: `user1@gemmail.com` | **Password**: `password123`
* **Email**: `user2@gemmail.com` | **Password**: `password123`

### Step 4: Configure the Server IP Address

Before starting the server, you must configure it to listen on the correct IP address.

1.  Open the `run_server.py` file.
2.  Find the `SMTP_HOST` variable.
3.  Change its value from `'localhost'` or `'0.0.0.0'` to the **actual IP address** of the computer where you are running the server. This should be the IP address that clients will use to connect (e.g., your Local Area Network IP like `192.168.1.10`, or your cloud server's public IP).

    ```python
    # example in run_server.py
    SMTP_HOST = '192.168.1.10' # <-- CHANGE THIS TO YOUR SERVER'S IP
    POP3_HOST = '0.0.0.0' 
    ```

## Usage

After completing the setup, you can run the application.

### 1. Start the Server

In a terminal, run the following command from the project's root directory:
```bash
python run_server.py
```
You should see messages indicating that the SMTP and POP3 servers are running.

### 2. Start the Client

Open a **new** terminal window and run the client application:
```bash
python run_client.py
```
A login window will appear:
1.  **Server Address**: Enter the same IP address you configured for `SMTP_HOST` in the `run_server.py` file.
2.  **Email / Password**: Use one of the sample user accounts (e.g., `user1@gemmail.com` and `password123`).
3.  Click "Login".

You can now send emails between `user1@gemmail.com` and `user2@gemmail.com` by running two separate instances of the client.

## Project Structure

```
GemMail_Project/
│
├── client/              # Contains all client-side code
│   ├── core/
│   │   └── email_handler.py # Handles SMTP/POP3 logic for the client
│   ├── widgets/
│   │   ├── login_dialog.py  # UI for the login window
│   │   └── compose_window.py# UI for the email composition window
│   └── main_window.py       # Main client application window and logic
│
├── server/              # Contains all server-side code
│   ├── database.py        # Script to initialize the SQLite database
│   └── main.py            # Core SMTP and POP3 server implementation
│
├── eml_storage/         # Default directory for storing local .eml files
│
├── requirements.txt     # Project dependencies
├── run_client.py        # Executable script to start the client
└── run_server.py        # Executable script to start the server
```
