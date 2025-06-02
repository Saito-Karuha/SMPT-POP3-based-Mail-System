import smtplib
import poplib
import os
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders, message_from_bytes
import re # 导入re模块用于更安全的清理

class EmailHandler:
    def __init__(self, user_email, smtp_host='localhost', smtp_port=1025, pop3_host='localhost', pop3_port=1100): # 添加 user_email 参数
        self.user_email = user_email # 存储用户邮箱
        self.smtp_server_info = (smtp_host, smtp_port)
        self.pop3_server_info = (pop3_host, pop3_port)

        # 创建用户专属的基础存储路径
        # 使用辅助函数清理邮箱地址，使其适合作为文件夹名
        sanitized_user_email = self._sanitize_foldername(self.user_email)
        base_user_storage_path = os.path.join('eml_storage', sanitized_user_email)

        # 为收件箱和已发送文件夹创建不同的用户专属存储路径
        self.inbox_storage_path = os.path.join(base_user_storage_path, 'inbox')
        self.sent_storage_path = os.path.join(base_user_storage_path, 'sent')
        os.makedirs(self.inbox_storage_path, exist_ok=True)
        os.makedirs(self.sent_storage_path, exist_ok=True)

    def _sanitize_foldername(self, name):
        """清理字符串，使其适合作为文件夹名。"""
        # 移除非字母数字字符，替换为空格，然后用下划线替换空格
        name = re.sub(r'[^\w\s-]', '', name).strip()
        name = re.sub(r'[-\s]+', '_', name)
        return name

    def _sanitize_filename(self, name):
        """清理字符串，使其适合作为文件名。"""
        # 移除非字母数字字符、点、下划线或连字符
        name = re.sub(r'[^\w\.\s-]', '', name).strip()
        name = re.sub(r'[-\s]+', '_', name)
        return name if name else "untitled"


    def send_email(self, sender, recipient, subject, body, attachment_path=None):
        """发送邮件，支持附件，并在成功后本地保存到用户专属的“已发送”文件夹。"""
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        if attachment_path:
            with open(attachment_path, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(attachment_path)}')
            msg.attach(part)
        
        try:
            with smtplib.SMTP(*self.smtp_server_info) as server:
                server.sendmail(sender, [recipient], msg.as_string())
            
            # 发送成功后，将邮件保存到用户专属的“已发送”文件夹
            # 使用时间戳和清理过的主题确保文件名唯一且安全
            safe_subject_part = self._sanitize_filename(subject[:30]) if subject else "no_subject"
            sent_email_filename = f"sent_{int(time.time())}_{safe_subject_part}.eml"
            # self.sent_storage_path 现在是用户专属的
            sent_email_path = os.path.join(self.sent_storage_path, sent_email_filename) 
            with open(sent_email_path, 'wb') as f:
                f.write(msg.as_bytes())

            return True, "邮件发送成功！"
        except Exception as e:
            return False, f"发送失败: {e}"

    def fetch_inbox(self, email_address, password):
        """获取收件箱邮件列表并下载到用户专属的本地收件箱。"""
        # 确保登录邮箱与 EmailHandler 实例化的用户邮箱一致
        if email_address != self.user_email:
            return False, f"用户邮箱不匹配: 预期 {self.user_email}, 得到 {email_address}"
        try:
            pop_server = poplib.POP3(*self.pop3_server_info)
            pop_server.user(email_address)
            pop_server.pass_(password)
            
            num_messages = len(pop_server.list()[1])
            emails = []
            for i in range(num_messages):
                msg_bytes = b'\n'.join(pop_server.retr(i + 1)[1])
                msg = message_from_bytes(msg_bytes)
                
                # 使用唯一标识符（如Message-ID）来命名文件，防止重复，并进行清理
                message_id_header = msg.get('Message-ID')
                if message_id_header:
                    safe_filename_part = self._sanitize_filename(message_id_header)
                else:
                    # 如果 Message-ID 不存在，创建一个基于时间的唯一标识
                    safe_filename_part = f"no_id_{int(time.time())}_{i+1}"
                
                # self.inbox_storage_path 现在是用户专属的
                file_path = os.path.join(self.inbox_storage_path, f"{safe_filename_part}.eml") 
                
                # 检查邮件是否已存在，避免重复下载 (可选优化)
                # if os.path.exists(file_path):
                #     # 如果需要，可以在这里更新邮件列表中的现有邮件信息
                #     continue 

                with open(file_path, "wb") as f:
                    f.write(msg_bytes)
                
                emails.append({
                    "id": i + 1, # 这是邮件在服务器上的索引
                    "from": msg['From'],
                    "subject": msg['Subject'],
                    "date": msg['Date'],
                    "path": file_path # 指向用户专属文件夹中的邮件
                })
                # pop_server.dele(i + 1) # 保持注释，不从服务器删除

            pop_server.quit()
            return True, emails
        except poplib.error_proto as e:
            return False, f"登录或接收失败: {e}"
        except Exception as e:
            return False, f"发生未知错误: {e}"

    def get_local_emails(self, folder_path):
        """
        从本地文件夹加载.eml文件。
        这个函数不需要修改，因为它操作的是传入的 folder_path，
        而这个 path 在调用时已经是用户专属的了。
        """
        emails = []
        if not os.path.exists(folder_path):
            return emails
            
        for filename in os.listdir(folder_path):
            if filename.endswith(".eml"):
                file_path = os.path.join(folder_path, filename)
                try:
                    with open(file_path, 'rb') as f:
                        msg = message_from_bytes(f.read())
                        emails.append({
                            "from": msg.get('From', 'N/A'),
                            "to": msg.get('To', 'N/A'),
                            "subject": msg.get('Subject', '无主题'),
                            "date": msg.get('Date', '无日期'),
                            "path": file_path
                        })
                except Exception as e:
                    print(f"加载邮件失败 {filename}: {e}") 
        return sorted(emails, key=lambda x: os.path.getmtime(x['path']), reverse=True)