from server.main import run_servers
from server.database import initialize_database

if __name__ == "__main__":
    print("正在检查并初始化数据库...")
    initialize_database()
    
    print("正在启动邮件服务器...")
    # 注意：这里的端口可以根据需要修改
    # SMTP_HOST = 'localhost'
    SMTP_HOST = '10.180.143.59'
    SMTP_PORT = 1025
    # POP3_HOST = 'localhost'
    POP3_HOST = '0.0.0.0'
    POP3_PORT = 1100
    
    run_servers(SMTP_HOST, SMTP_PORT, POP3_HOST, POP3_PORT)