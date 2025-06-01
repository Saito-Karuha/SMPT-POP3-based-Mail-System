import smtplib
import poplib
import os
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders, message_from_bytes
from email.utils import formatdate
from email.header import Header
from email import message_from_bytes
from email.header import decode_header

def decode_mime_header(header_value):
    if not header_value:
        return ''
    decoded_fragments = decode_header(header_value)
    decoded_string = ''
    for fragment, charset in decoded_fragments:
        if charset:
            decoded_string += fragment.decode(charset, errors='ignore')
        else:
            if isinstance(fragment, bytes):
                decoded_string += fragment.decode('utf-8', errors='ignore')
            else:
                decoded_string += fragment
    return decoded_string

def extract_email_body(msg):
    # 如果是 multipart 类型
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", "")).lower()
            if "attachment" in content_disposition:
                continue  # 跳过附件
            if content_type == "text/plain":
                try:
                    return part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore')
                except:
                    continue
        # 如果找不到 text/plain，尝试找 text/html
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                try:
                    return part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore')
                except:
                    continue
    else:
        # 非 multipart 的邮件
        try:
            return msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8', errors='ignore')
        except:
            return ''
    return '(无正文内容)'

class EmailHandler:
    def __init__(self, smtp_host='localhost', smtp_port=1025, pop3_host='localhost', pop3_port=1100):
        self.smtp_server_info = (smtp_host, smtp_port)
        self.pop3_server_info = (pop3_host, pop3_port)
        # 为收件箱和已发送文件夹创建不同的存储路径
        self.inbox_storage_path = 'eml_storage/inbox'
        self.sent_storage_path = 'eml_storage/sent'
        os.makedirs(self.inbox_storage_path, exist_ok=True)
        os.makedirs(self.sent_storage_path, exist_ok=True)

    def send_email(self, sender, recipient, subject, body, attachment_path=None):
        """发送邮件，支持附件，并在成功后本地保存。"""
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = recipient
        msg['Subject'] = Header(subject, 'utf-8')
        msg['Date'] = formatdate(localtime=True)
        msg.attach(MIMEText(body, 'html', 'utf-8'))

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
            
            # 发送成功后，将邮件保存到“已发送”文件夹
            # 使用时间戳和主题确保文件名唯一
            sent_email_filename = f"sent_{int(time.time())}_{subject[:20].replace(' ', '_')}.eml"
            sent_email_path = os.path.join(self.sent_storage_path, sent_email_filename)
            with open(sent_email_path, 'wb') as f:
                f.write(msg.as_bytes())

            return True, "邮件发送成功！"
        except Exception as e:
            return False, f"发送失败: {e}"

    def fetch_inbox(self, email_address, password):
        """获取收件箱邮件列表并下载到本地。"""
        try:
            pop_server = poplib.POP3(*self.pop3_server_info)
            pop_server.user(email_address)
            pop_server.pass_(password)
            
            num_messages = len(pop_server.list()[1])
            emails = []
            for i in range(num_messages):
                # 原始邮件字节流
                msg_bytes = b'\n'.join(pop_server.retr(i + 1)[1])
                msg = message_from_bytes(msg_bytes)
                
                # 使用唯一标识符来命名文件，防止重复
                file_path = os.path.join(self.inbox_storage_path, f"email_{email_address}_{msg.get('Message-ID', i+1)}.eml")
                with open(file_path, "wb") as f:
                    f.write(msg_bytes)
                
                emails.append({
                    "id": i + 1,
                    "from": msg['From'],
                    "subject": msg['Subject'],
                    "date": msg['Date'],
                    "path": file_path
                })
                # 下面这行已被移除，以防止邮件从服务器删除
                # pop_server.dele(i + 1) 

            pop_server.quit()
            return True, emails
        except poplib.error_proto as e:
            return False, f"登录或接收失败: {e}"
        except Exception as e:
            return False, f"发生未知错误: {e}"

    def get_local_emails(self, folder_path):
        """
        从本地文件夹加载.eml文件。
        这是解决报错需要添加的新函数。
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
                        subject_raw = msg.get('Subject', '无主题')
                        subject = decode_mime_header(subject_raw)
                        email_body = extract_email_body(msg)
                        emails.append({
                            "from": msg.get('From', 'N/A'),
                            "to": msg.get('To', 'N/A'),
                            "subject": subject,
                            "date": msg.get('Date', '无日期'),
                            "body": email_body,
                            "path": file_path
                        })
                except Exception as e:
                    print(f"加载邮件失败 {filename}: {e}") # 增加错误处理
        # 按文件修改时间降序排序，最新的邮件在最前面
        return sorted(emails, key=lambda x: os.path.getmtime(x['path']), reverse=True)