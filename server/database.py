import sqlite3
import hashlib

DATABASE_FILE = 'mail_server.db'

def initialize_database():
    """初始化数据库，创建表并添加示例用户。"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            recipient TEXT NOT NULL,
            subject TEXT,
            body BLOB NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    sample_users = {
        "user1@gemmail.com": "1",
        "user2@gemmail.com": "1",
        "user3@gemmail.com": "1",
    }
    for email, password in sample_users.items():
        cursor.execute("SELECT email FROM users WHERE email = ?", (email,))
        if cursor.fetchone() is None:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            cursor.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (email, password_hash))
    conn.commit()
    conn.close()
    print("数据库已初始化。")

# 在直接运行时，初始化数据库
if __name__ == '__main__':
    initialize_database()

# user1@gemmail.com