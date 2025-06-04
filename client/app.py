from flask import Flask, render_template, request, redirect, session, url_for, flash, send_from_directory, send_file, abort, jsonify
from werkzeug.utils import secure_filename
# 确保这里的导入路径正确，EmailHandler 应该在 GemMail_Project/client/core/ 中
from client.core.email_handler import EmailHandler
from urllib.parse import unquote
from datetime import datetime
from email import message_from_bytes
import os
import uuid
from email.header import decode_header
import tempfile
import io

app = Flask(__name__)
app.secret_key = 'gemmail_secret_key_123456' # 建议使用更安全的密钥，并从配置中加载

# 上传文件夹配置 (用于邮件撰写时的附件)
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'docx', 'xlsx', 'eml', 'md'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 辅助函数：解码MIME编码的邮件头部 (如主题、发件人等)
def decode_mime_words(s):
    if not s:
        return ''
    decoded_words_list = decode_header(s)
    decoded_string = ''
    for word_bytes, charset in decoded_words_list:
        if charset:
            try:
                decoded_string += word_bytes.decode(charset)
            except UnicodeDecodeError:
                # 如果指定编码解码失败，尝试用 'latin-1' 或 'utf-8' (作为备选)
                try:
                    decoded_string += word_bytes.decode('latin-1')
                except UnicodeDecodeError:
                    decoded_string += word_bytes.decode('utf-8', errors='replace')
        elif isinstance(word_bytes, bytes):
            try:
                decoded_string += word_bytes.decode('utf-8', errors='replace') # 默认尝试utf-8
            except UnicodeDecodeError:
                decoded_string += word_bytes.decode('latin-1', errors='replace') # 尝试latin-1
        else:
            decoded_string += word_bytes # 如果已经是字符串
    return decoded_string.strip()

# 辅助函数：从 email.message.Message 对象中提取邮件正文
def extract_email_body(msg):
    body = ""
    if msg.is_multipart():
        # 优先查找 text/html
        html_part = None
        text_part = None
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", "")).lower()
            if "attachment" in content_disposition:
                continue

            if part.is_multipart(): # 跳过 multipart/alternative 等容器本身
                continue

            charset = part.get_content_charset() or 'utf-8'
            payload = part.get_payload(decode=True)
            if not payload:
                continue

            if content_type == "text/html":
                try:
                    html_part = payload.decode(charset, errors='replace')
                except Exception:
                    continue
            elif content_type == "text/plain":
                try:
                    text_part = payload.decode(charset, errors='replace')
                except Exception:
                    continue

        if html_part:
            # 简单处理，实际可能需要BeautifulSoup来剥离HTML标签获取纯文本
            # 为了在 <pre> 标签中显示，我们目前可以直接返回HTML
            body = html_part
        elif text_part:
            # 将纯文本包装在 <pre> 标签中以保留格式
            body = f"<pre>{text_part}</pre>"
        else: # 如果没有 html 和 plain，尝试获取第一个可解码的部分
            for part in msg.walk(): # 再次遍历，逻辑简化
                if part.is_multipart() or "attachment" in str(part.get("Content-Disposition", "")).lower():
                    continue
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or 'utf-8'
                    body = payload.decode(charset, errors='replace')
                    if part.get_content_type() == "text/plain": body = f"<pre>{body}</pre>"
                    break # 取第一个找到的
                except:
                    continue

    else: # 非 multipart 邮件
        charset = msg.get_content_charset() or 'utf-8'
        payload = msg.get_payload(decode=True)
        if payload:
            try:
                body_content = payload.decode(charset, errors='replace')
                if msg.get_content_type() == "text/html":
                    body = body_content
                else: # 默认为纯文本或未知，用 pre 包装
                    body = f"<pre>{body_content}</pre>"
            except Exception:
                body = "(无法解码正文)"

    return body if body else '(无正文内容或无法提取)'


# 辅助函数：从 email.message.Message 对象中提取附件信息列表
def get_attachments_from_msg(msg):
    attachments = []
    for part in msg.walk():
        content_disposition = str(part.get("Content-Disposition", "")).lower()
        if "attachment" in content_disposition or part.get_filename():
            filename = part.get_filename()
            if filename:
                decoded_filename = decode_mime_words(filename)
                attachments.append({
                    "original_filename": decoded_filename,
                    # "content_type": part.get_content_type() # 可选，用于下载时设置mimetype
                })
    return attachments

@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('inbox'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        server = request.form.get('server')

        if not all([email, password, server]):
            flash('请填写所有登录信息 (邮箱, 密码, 服务器地址)。', 'error')
            return redirect(url_for('login'))

        try:
            # 使用表单提供的 email 初始化 EmailHandler，用于登录尝试
            # GemMail_Project 的 EmailHandler 需要 user_email
            email_handler_instance = EmailHandler(user_email=email, smtp_host=server, pop3_host=server)
            # fetch_inbox 会尝试登录并获取邮件，同时也验证了凭据
            # GemMail_Project 的 fetch_inbox 会将邮件下载到用户专属目录
            success, message_or_data = email_handler_instance.fetch_inbox(email, password)
        except Exception as e:
            app.logger.error(f"Login or EmailHandler init error for {email}: {e}", exc_info=True)
            flash(f'登录或连接邮件服务器失败: {e}', 'error')
            return redirect(url_for('login'))

        if success:
            session['user'] = email
            session['password'] = password # 存储密码可能不安全，但原逻辑如此
            session['server'] = server
            flash('登录成功！', 'success')
            return redirect(url_for('inbox'))
        else:
            flash(f'登录失败: {message_or_data}', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('您已成功登出。', 'info')
    return redirect(url_for('login'))

def get_email_handler():
    """辅助函数，用于获取当前会话的EmailHandler实例"""
    if 'user' not in session or 'server' not in session:
        # flash('会话已过期或未登录，请重新登录。', 'warning') # flash在这里可能无法正确显示给用户
        return None
    try:
        handler = EmailHandler(
            user_email=session['user'],
            smtp_host=session['server'],
            pop3_host=session['server']
        )
        return handler
    except Exception as e:
        app.logger.error(f"Failed to create EmailHandler for {session.get('user')}: {e}", exc_info=True)
        # flash(f"初始化邮件服务时出错: {e}", 'error') # flash在这里可能无法正确显示给用户
        return None

@app.route('/inbox')
def inbox():
    email_handler_instance = get_email_handler()
    if not email_handler_instance:
        return redirect(url_for('login'))

    # 首先尝试从服务器获取新邮件
    # fetch_inbox 内部会处理邮件的本地存储和分类
    try:
        email_handler_instance.fetch_inbox(session['user'], session['password'])
    except Exception as e:
        app.logger.warning(f"Fetching new emails for {session['user']} failed: {e}", exc_info=True)
        flash(f"刷新收件箱时遇到问题 (可能无法连接服务器): {e}", "warning")

    # 然后加载本地收件箱的邮件
    # GemMail_Project 的 get_local_emails 会处理垃圾邮件的移动（如果是收件箱路径）
    local_emails = email_handler_instance.get_local_emails(email_handler_instance.inbox_storage_path)
    return render_template('inbox.html', emails=local_emails)

@app.route('/sent')
def sent():
    email_handler_instance = get_email_handler()
    if not email_handler_instance:
        return redirect(url_for('login'))

    sent_emails = email_handler_instance.get_local_emails(email_handler_instance.sent_storage_path)
    return render_template('sent.html', emails=sent_emails)

@app.route('/trash')
def trash():
    email_handler_instance = get_email_handler()
    if not email_handler_instance:
        return redirect(url_for('login'))

    # GemMail_Project中，spam_storage_path 对应的是垃圾邮件文件夹 'trash'
    trash_emails = email_handler_instance.get_local_emails(email_handler_instance.spam_storage_path)
    return render_template('trash.html', emails=trash_emails)

@app.route('/compose', methods=['GET', 'POST'])
def compose():
    email_handler_instance = get_email_handler()
    if not email_handler_instance:
        return redirect(url_for('login'))

    if request.method == 'POST':
        to = request.form.get('to')
        subject = request.form.get('subject')
        body = request.form.get('body') # 这是HTML格式的正文
        file = request.files.get('attachment')

        if not to:
            flash("收件人不能为空。", "error")
            return render_template('compose.html')

        attachment_path = None
        if file and file.filename:
            if allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # UPLOAD_FOLDER 已经是绝对路径
                path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                try:
                    file.save(path)
                    attachment_path = path
                except Exception as e:
                    app.logger.error(f"Failed to save attachment {filename}: {e}", exc_info=True)
                    flash(f"保存附件失败: {e}", "error")
                    return render_template('compose.html')
            else:
                flash("不允许的附件类型。", "error")
                return render_template('compose.html')

        try:
            # GemMail_Project 的 send_email 有 PGP 参数，此处不使用，它们有默认值
            success, msg_send = email_handler_instance.send_email(
                sender=session['user'],
                recipient=to,
                subject=subject,
                body=body, # EmailHandler 会处理 HTML
                attachment_path=attachment_path
            )
            if success:
                flash("邮件发送成功！", "success")
                return redirect(url_for('inbox')) # 或 'sent'
            else:
                flash(f"邮件发送失败: {msg_send}", "error")
        except Exception as e:
            app.logger.error(f"Error sending email from {session['user']} to {to}: {e}", exc_info=True)
            flash(f"发送邮件时发生严重错误: {e}", "error")

        # 如果发送失败，保留已填写的表单内容
        return render_template('compose.html', to=to, subject=subject, body=body)

    return render_template('compose.html')

@app.route('/email') # 查看邮件详情
def view_email():
    email_handler_instance = get_email_handler() # 确保用户已登录
    if not email_handler_instance:
        return redirect(url_for('login'))

    encoded_path = request.args.get('path')
    if not encoded_path:
        flash("未提供邮件路径。", "error")
        return redirect(url_for('inbox'))

    try:
        # 解码路径，因为它是从 URL 参数中获取的
        file_path = unquote(encoded_path)
    except Exception as e:
        flash(f"邮件路径无效: {e}", "error")
        return redirect(url_for('inbox'))

    # 安全检查：确保路径在预期的 eml_storage 内 (基于当前用户的存储)
    # 这是 EmailHandler 内部管理的用户特定路径
    # base_user_storage_path = os.path.join('eml_storage', email_handler_instance._sanitize_foldername(session['user']))
    # if not os.path.abspath(file_path).startswith(os.path.abspath(base_user_storage_path)):
    #     flash("无权访问此邮件路径。", "error")
    #     return redirect(url_for('inbox'))
    # 更简单的检查：文件必须在 eml_storage 下
    if not os.path.abspath(file_path).startswith(os.path.abspath('eml_storage')):
        flash("禁止访问此路径。", "error")
        return redirect(url_for('inbox'))


    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        flash("请求的邮件文件不存在。", "error")
        return redirect(url_for('inbox'))

    try:
        with open(file_path, 'rb') as f:
            msg_bytes = f.read()
        msg = message_from_bytes(msg_bytes)

        # GemMail_Project 的 EmailHandler 有 get_text_from_email, 但此处我们用 app.py 内的
        # extract_email_body 和 get_attachments_from_msg
        # 注意：如果邮件是PGP加密的，extract_email_body 不会解密它
        # is_spam 标记应从 get_local_emails 获取，但这里是直接读文件，所以无法简单获取

        email_details = {
            "sender": decode_mime_words(msg.get('From', 'N/A')),
            "to": decode_mime_words(msg.get('To', 'N/A')),
            "subject": decode_mime_words(msg.get('Subject', '无主题')),
            "date": msg.get('Date', '无日期'), # 日期格式化可以在模板中用JS或Python辅助函数
            "body": extract_email_body(msg), # 返回的可能是HTML或者 <pre>包裹的纯文本
            "attachments": get_attachments_from_msg(msg),
            "path": file_path # 用于附件下载时回传给 download_attachment
        }

        # 尝试确定邮件是否在垃圾箱中以显示提示 (可选增强)
        is_in_trash_folder = file_path.startswith(os.path.abspath(email_handler_instance.spam_storage_path))
        if is_in_trash_folder:
             email_details['is_spam_hint'] = True


    except Exception as e:
        app.logger.error(f"Error reading or parsing email file {file_path}: {e}", exc_info=True)
        flash(f"读取邮件内容失败: {e}", "error")
        return redirect(url_for('inbox'))

    return render_template('view_email.html', email=email_details)


@app.route('/download_attachment')
def download_attachment():
    email_handler_instance = get_email_handler() # 确保用户已登录
    if not email_handler_instance:
        abort(401) # 未授权

    eml_file_path_encoded = request.args.get('eml_path') # 对应 view_email.html 中传递的 path
    attachment_original_filename = request.args.get('filename')

    if not eml_file_path_encoded or not attachment_original_filename:
        flash("缺少邮件路径或附件文件名。", "error")
        return redirect(request.referrer or url_for('inbox'))

    try:
        eml_file_path = unquote(eml_file_path_encoded)
        attachment_original_filename = unquote(attachment_original_filename) # 文件名也可能编码
    except Exception as e:
        flash(f"附件参数解码失败: {e}", "error")
        return redirect(request.referrer or url_for('inbox'))

    # 安全检查 (类似 view_email)
    if not os.path.abspath(eml_file_path).startswith(os.path.abspath('eml_storage')):
        flash("禁止访问此邮件路径的附件。", "error")
        return redirect(url_for('inbox'))


    if not os.path.exists(eml_file_path):
        flash("邮件文件不存在，无法下载附件。", "error")
        return redirect(request.referrer or url_for('inbox'))

    try:
        with open(eml_file_path, 'rb') as f:
            msg = message_from_bytes(f.read())

        found_part = None
        for part in msg.walk():
            content_disposition = str(part.get("Content-Disposition", "")).lower()
            part_fn = part.get_filename()
            if part_fn:
                decoded_part_fn = decode_mime_words(part_fn)
                if decoded_part_fn == attachment_original_filename and ("attachment" in content_disposition or "inline" in content_disposition):
                    found_part = part
                    break

        if found_part:
            attachment_data = found_part.get_payload(decode=True)
            if attachment_data is None:
                flash('附件数据为空。', 'error')
                return redirect(request.referrer or url_for('view_email', path=eml_file_path_encoded))

            return send_file(
                io.BytesIO(attachment_data),
                mimetype=found_part.get_content_type(),
                as_attachment=True,
                download_name=attachment_original_filename # 使用原始解码后的文件名进行下载
            )
        else:
            flash(f"在邮件中未找到名为 '{attachment_original_filename}' 的附件。", "error")

    except Exception as e:
        app.logger.error(f"Error downloading attachment '{attachment_original_filename}' from {eml_file_path}: {e}", exc_info=True)
        flash(f"下载附件时出错: {e}", "error")

    return redirect(request.referrer or url_for('view_email', path=eml_file_path_encoded))

if __name__ == '__main__':
    # 这部分主要用于直接运行app.py进行测试，生产部署时会用Gunicorn等
    # run_web_client.py 会处理应用的启动
    print("Flask app is configured. Run it using 'flask run' or a dedicated script like 'run_web_client.py'")
    # app.run(debug=True, host='0.0.0.0', port=5000) # 通常在 run_web_client.py 中调用