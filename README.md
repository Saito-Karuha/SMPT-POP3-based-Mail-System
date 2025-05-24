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
