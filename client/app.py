from flask import Flask, render_template, request, redirect, session, url_for, flash, send_from_directory, send_file, abort
from werkzeug.utils import secure_filename
from core.email_handler import EmailHandler
from urllib.parse import unquote
from flask import jsonify
from datetime import datetime
from email import message_from_bytes
import os
import uuid
from email.header import decode_header
import tempfile
import io


app = Flask(__name__)
app.secret_key = '123456'  # 你可以替换为更安全的值

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'docx', 'xlsx'}

def decode_mime_words(s):
    decoded_words = decode_header(s)
    decoded_string = ''
    for word, charset in decoded_words:
        if charset:
            decoded_string += word.decode(charset)
        elif isinstance(word, bytes):
            decoded_string += word.decode('utf-8', errors='replace')
        else:
            decoded_string += word
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


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_body_from_msg(msg):
    """
    从邮件中提取纯文本正文（优先 text/plain）。
    """
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                charset = part.get_content_charset() or "utf-8"
                try:
                    return part.get_payload(decode=True).decode(charset, errors="replace")
                except Exception:
                    continue
    else:
        # 非 multipart 的情况
        charset = msg.get_content_charset() or "utf-8"
        try:
            return msg.get_payload(decode=True).decode(charset, errors="replace")
        except Exception:
            return msg.get_payload()
    return "(无正文内容)"

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

def get_attachments_from_msg(msg, save_folder='attachments'):
    """
    从邮件中提取附件，保存到本地文件夹，并返回附件信息列表。
    每个附件字典包含：filename
    """
    attachments = []

    for part in msg.walk():
        content_disposition = str(part.get("Content-Disposition", ""))
        if part.get_content_maintype() == 'multipart' or "attachment" not in content_disposition:
            continue

        filename = part.get_filename()
        if filename:
            filename = decode_mime_words(filename)  # 解码文件名
            print(filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            filepath = os.path.join(save_folder, unique_filename)
            try:
                attachments.append({
                    "filename": unique_filename,
                    "original_filename": filename  # 保存原始（解码后）文件名，方便前端显示
                })
            except Exception as e:
                print(f"保存附件失败: {e}")
            
        print(attachments)

    return attachments


@app.route('/')
def index():
    print("[INDEX] Session user:", session.get('user'))
    if 'user' in session:
        print("[INDEX] User logged in, redirecting to inbox")
        return redirect(url_for('inbox'))
    print("[INDEX] No user in session, redirecting to login")
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        print("[LOGIN] Received POST request")
        email = request.form.get('email')
        password = request.form.get('password')
        server = request.form.get('server')
        print(f"[LOGIN] Form data - email: {email}, password: {'***' if password else None}, server: {server}")

        if not all([email, password, server]):
            print("[LOGIN] Missing one or more form fields")
            flash('请填写完整信息')
            return redirect(url_for('login'))

        email_handler = EmailHandler(smtp_host=server, pop3_host=server)
        print("[LOGIN] Attempting to fetch inbox...")
        success, result = email_handler.fetch_inbox(email, password)
        print(f"[LOGIN] fetch_inbox result - success: {success}, message: {result}")

        if success:
            session['user'] = email
            session['password'] = password
            session['server'] = server
            print("[LOGIN] Login successful, session set")
            flash('登录成功')
            return redirect(url_for('inbox'))
        else:
            print("[LOGIN] Login failed")
            flash(f'登录失败: {result}')
            return redirect(url_for('login'))

    print("[LOGIN] GET request, rendering login page")
    return render_template('login.html')

from flask import send_from_directory

@app.route('/email')
def view_email():
    if 'user' not in session:
        return redirect(url_for('login'))

    encoded_path = request.args.get('path')
    if not encoded_path:
        flash("邮件路径缺失")
        return redirect(url_for('inbox'))

    file_path = unquote(encoded_path)

    if not os.path.exists(file_path):
        flash("邮件文件不存在")
        return redirect(url_for('inbox'))

    try:
        from email import message_from_bytes
        with open(file_path, 'rb') as f:
            msg = message_from_bytes(f.read())
            email = {
                "sender": msg.get('From', 'N/A'),
                "to": msg.get('To', 'N/A'),
                "subject": decode_mime_header(msg.get('Subject', '无主题')),
                "date": msg.get('Date', '无日期'),
                "body": extract_email_body(msg),
                "attachments": get_attachments_from_msg(msg)
            }
    except Exception as e:
        flash(f"读取邮件失败：{e}")
        return redirect(url_for('inbox'))

    return render_template('view_email.html', email=email)

@app.route('/download_attachment')
def download_attachment():
    if 'user' not in session:
        flash('请先登录')
        return redirect(url_for('login'))
    
    eml_path = request.args.get('eml_path')
    filename = request.args.get('filename')
    
    if not eml_path or not filename:
        flash('缺少邮件路径或附件名')
        return redirect(url_for('inbox'))
    
    # 解码url，防止路径问题
    from urllib.parse import unquote
    eml_path = unquote(eml_path)
    
    if not os.path.exists(eml_path):
        flash('邮件文件不存在')
        return redirect(url_for('inbox'))
    
    try:
        with open(eml_path, 'rb') as f:
            msg = message_from_bytes(f.read())
        
        # 在邮件中找到对应附件
        for part in msg.walk():
            content_disposition = str(part.get("Content-Disposition", "")).lower()
            part_filename = part.get_filename()
            if part_filename:
                # 解码附件名
                part_filename_decoded = decode_mime_words(part_filename)
                if part_filename_decoded == filename and "attachment" in content_disposition:
                    attachment_data = part.get_payload(decode=True)
                    if attachment_data is None:
                        break
                    # 用 BytesIO 包装，模拟文件流
                    return send_file(
                        io.BytesIO(attachment_data),
                        as_attachment=True,
                        download_name=part_filename_decoded,
                        mimetype=part.get_content_type()
                    )
        flash('未找到附件')
        return redirect(url_for('view_email', path=eml_path))
    except Exception as e:
        flash(f'读取附件失败: {e}')
        return redirect(url_for('view_email', path=eml_path))


@app.route('/trash')
def trash():
    if 'user' not in session:
        return redirect(url_for('login'))

    email_handler = EmailHandler(
        smtp_host=session['server'],
        pop3_host=session['server']
    )
    trash_emails = email_handler.get_local_emails(email_handler.trash_storage_path)
    print(f"[TRASH] Loaded {len(trash_emails)} emails from local storage")
    return render_template('trash.html', emails=trash_emails)


@app.route('/logout')
def logout():
    print("[LOGOUT] Clearing session and redirecting to login")
    session.clear()
    flash('已登出')
    return redirect(url_for('login'))

@app.route('/inbox')
def inbox():
    if 'user' not in session:
        print("[INBOX] No user in session, redirecting to login")
        return redirect(url_for('login'))

    print(f"[INBOX] User {session['user']} accessing inbox")
    email_handler = EmailHandler(
        smtp_host=session['server'],
        pop3_host=session['server']
    )
    emails = email_handler.get_local_emails(email_handler.inbox_storage_path)
    print(f"[INBOX] Loaded {len(emails)} emails from local storage")
    return render_template('inbox.html', emails=emails)

@app.route('/compose', methods=['GET', 'POST'])
def compose():
    if 'user' not in session:
        print("[COMPOSE] No user in session, redirecting to login")
        return redirect(url_for('login'))
    if request.method == 'POST':
        print("[COMPOSE] POST request to send email")
        to = request.form.get('to')
        subject = request.form.get('subject')
        body = request.form.get('body')
        file = request.files.get('attachment')

        print(f"[COMPOSE] Form data - to: {to}, subject: {subject}, body length: {len(body) if body else 0}")

        attachment_path = None

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            
            # 拼接为绝对路径
            upload_folder = os.path.abspath(app.config['UPLOAD_FOLDER'])
            os.makedirs(upload_folder, exist_ok=True)  # 确保目录存在

            path = os.path.join(upload_folder, filename)
            try:
                file.save(path)
                attachment_path = path  # 已是绝对路径
                print(f"[COMPOSE] Saved attachment to {path}")
            except Exception as e:
                print(f"[COMPOSE] Failed to save attachment: {e}")

        try:
            email_handler = EmailHandler(
                smtp_host=session['server'],
                pop3_host=session['server']
            )
        except Exception as e:
            print(f"[COMPOSE] Failed to create EmailHandler: {e}")
            flash(f"初始化邮件处理器失败: {e}")
            return redirect(url_for('compose'))

        print("[COMPOSE] Starting to send email via EmailHandler...")
        try:
            success, msg = email_handler.send_email(
                sender=session['user'],
                recipient=to,
                subject=subject,
                body=body,
                attachment_path=attachment_path
            )
            print(f"[COMPOSE] send_email returned success={success}, message={msg}")
        except Exception as e:
            print(f"[COMPOSE] Exception during send_email: {e}")
            flash(f"发送邮件时发生错误: {e}")
            return redirect(url_for('compose'))

        if success:
            print("[COMPOSE] Email sent successfully")
            flash("邮件发送成功")
        else:
            print(f"[COMPOSE] Email sending failed: {msg}")
            flash(f"发送失败：{msg}")

        return redirect(url_for('inbox'))

    print("[COMPOSE] GET request, rendering compose page")
    return render_template('compose.html')


@app.route('/sent')
def sent():
    if 'user' not in session:
        return redirect(url_for('login'))
    email_handler = EmailHandler(
        smtp_host=session['server'],
        pop3_host=session['server']
    )
    # 读取本地“已发送”文件夹邮件
    emails = email_handler.get_local_emails(email_handler.sent_storage_path)
    return render_template('sent.html', emails=emails)




if __name__ == '__main__':
    print("[APP] Starting Flask app")
    app.run(debug=True)
