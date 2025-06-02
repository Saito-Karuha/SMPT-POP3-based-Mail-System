# (这里的代码与上一版我们优化的 server.py 基本相同，只是被封装成了函数)
import asyncore
import asyncio
import threading
import sqlite3
import hashlib
from email import message_from_bytes
from aiosmtpd.controller import Controller

DATABASE_FILE = 'mail_server.db'

# --- 数据库辅助函数 ---
def verify_user_credentials(email, password):
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        cursor.execute("SELECT 1 FROM users WHERE email = ? AND password_hash = ?", (email, password_hash))
        return cursor.fetchone() is not None

def store_email_in_db(sender, recipients, data):
    msg = message_from_bytes(data)
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        for recipient in recipients:
            cursor.execute("SELECT 1 FROM users WHERE email = ?", (recipient,))
            if cursor.fetchone():
                cursor.execute(
                    "INSERT INTO emails (sender, recipient, subject, body) VALUES (?, ?, ?, ?)",
                    (sender, recipient, msg['subject'], data)
                )

def get_emails_for_user(email):
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, body FROM emails WHERE recipient = ? ORDER BY timestamp DESC", (email,))
        return cursor.fetchall()

def delete_email_from_db(email_id):
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM emails WHERE id = ?", (email_id,))

# --- aiosmtpd 邮件处理程序 ---
class CustomSMTPHandler:
    async def handle_DATA(self, server, session, envelope):
        data = envelope.content
        store_email_in_db(envelope.mail_from, envelope.rcpt_tos, data)
        return '250 OK'

# --- POP3 服务器 ---
class POP3Session(asyncore.dispatcher_with_send):
    # ... (这部分代码与上一版完全相同，为了简洁此处省略)
    def __init__(self, sock):
        super().__init__(sock)
        self.state = 'AUTH'
        self.user = None
        self.emails_to_delete = set()
        self.send(b"+OK POP3 server ready\r\n")

    def handle_read(self):
        try:
            data = self.recv(8192).decode().strip()
            if not data: return
            command, *args = data.split()
            
            if command.upper() == 'USER':
                self.user = args[0]
                self.send(b"+OK\r\n")
            elif command.upper() == 'PASS':
                if verify_user_credentials(self.user, args[0]):
                    self.state = 'TRANSACTION'
                    self.send(b"+OK Logged in.\r\n")
                else:
                    self.send(b"-ERR Invalid password.\r\n")
                    self.close()
            elif command.upper() == 'STAT' and self.state == 'TRANSACTION':
                emails = get_emails_for_user(self.user)
                total_size = sum(len(e[1]) for e in emails)
                self.send(f"+OK {len(emails)} {total_size}\r\n".encode())
            elif command.upper() == 'LIST' and self.state == 'TRANSACTION':
                emails = get_emails_for_user(self.user)
                self.send(f"+OK {len(emails)} messages\r\n".encode())
                for i, email in enumerate(emails):
                     self.send(f"{i+1} {len(email[1])}\r\n".encode())
                self.send(b".\r\n")
            elif command.upper() == 'RETR' and self.state == 'TRANSACTION':
                emails = get_emails_for_user(self.user)
                msg_index = int(args[0]) - 1
                if 0 <= msg_index < len(emails):
                    body = emails[msg_index][1]
                    self.send(f"+OK {len(body)} octets\r\n".encode())
                    self.send(body + b"\r\n.\r\n")
            elif command.upper() == 'DELE' and self.state == 'TRANSACTION':
                emails = get_emails_for_user(self.user)
                msg_index = int(args[0]) - 1
                if 0 <= msg_index < len(emails):
                    self.emails_to_delete.add(emails[msg_index][0])
                    self.send(f"+OK Message {args[0]} deleted.\r\n".encode())
            elif command.upper() == 'QUIT':
                for email_id in self.emails_to_delete:
                    delete_email_from_db(email_id)
                self.send(b"+OK Goodbye.\r\n")
                self.close()
        except (ConnectionResetError, BrokenPipeError):
            self.close()
        except Exception as e:
            self.close()


class POP3Server(asyncore.dispatcher):
    def __init__(self, host, port):
        super().__init__()
        self.create_socket()
        self.set_reuse_addr()
        self.bind((host, port))
        self.listen(10)
        
    def handle_accepted(self, sock, addr):
        POP3Session(sock)

# --- 启动器 ---
def run_servers(smtp_host, smtp_port, pop3_host, pop3_port):
    def run_pop3():
        POP3Server(pop3_host, pop3_port)
        asyncore.loop(use_poll=True)

    pop3_thread = threading.Thread(target=run_pop3, name="POP3-Thread")
    pop3_thread.daemon = True
    pop3_thread.start()
    
    controller = Controller(CustomSMTPHandler(), hostname=smtp_host, port=smtp_port)
    print(f"SMTP 服务器正在监听 {smtp_host}:{smtp_port}")
    print(f"POP3 服务器正在监听 {pop3_host}:{pop3_port}")
    controller.start()
    
    try:
        while True:
            pass
    except KeyboardInterrupt:
        controller.stop()