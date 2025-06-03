import sys
import os
import webbrowser
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QListWidget, QTextBrowser, QPushButton, QLabel,
                             QSplitter, QListWidgetItem, QMessageBox, QFileDialog)
from PyQt6.QtGui import QIcon, QFont
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl

from client.core.email_handler import EmailHandler
from client.widgets.login_dialog import LoginDialog
from client.widgets.compose_window import ComposeWindow
from email import message_from_bytes

class EmailWorker(QThread):
    finished = pyqtSignal(object)

    def __init__(self, handler, action, credentials=None, data=None):
        super().__init__()
        self.handler = handler
        self.action = action
        self.credentials = credentials
        self.data = data

    def run(self):
        result = None
        if self.action == "fetch":
            result = self.handler.fetch_inbox(self.credentials[0], self.credentials[1])
        elif self.action == "send":
            result = self.handler.send_email(**self.data)
        self.finished.emit(result)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GemMail - 您的现代化邮件客户端")
        self.setGeometry(100, 100, 1200, 800)
        
        # 不再在这里初始化 email_handler
        self.email_handler = None 
        self.current_user = None
        self.current_password = None
        self.current_message = None 
        self.current_message_is_encrypted = False # 新增标记，用于跟踪当前邮件是否已解密
        self.current_decrypted_content = None # 新增，存储解密后的内容
        
        self.init_ui()
        self.email_viewer.anchorClicked.connect(self.save_attachment)
        self.show()
        # 在UI显示后再调用登录
        self.prompt_login()

    def init_ui(self):
        # --- 左侧功能栏 ---
        left_panel = QVBoxLayout()
        left_panel.setSpacing(15)
        
        self.user_label = QLabel("未登录")
        self.user_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        
        self.compose_button = QPushButton(" 写邮件")
        self.compose_button.clicked.connect(self.open_compose_window)
        
        self.inbox_button = QPushButton(" 收件箱")
        self.inbox_button.clicked.connect(self.show_inbox)
        
        self.sent_button = QPushButton(" 已发送") # 新增“已发送”按钮
        self.sent_button.clicked.connect(self.show_sent_folder)

         # 新增“垃圾邮件”按钮
        self.spam_button = QPushButton(" 垃圾邮件")
        self.spam_button.clicked.connect(self.show_spam_folder) # 需要创建 show_spam_folder 方法

        self.refresh_button = QPushButton(" 刷新")
        self.refresh_button.clicked.connect(self.show_inbox) # 刷新应该重新加载收件箱

        left_panel.addWidget(self.user_label, alignment=Qt.AlignmentFlag.AlignCenter)
        left_panel.addWidget(self.compose_button)
        left_panel.addWidget(self.inbox_button)
        left_panel.addWidget(self.sent_button) # 将按钮添加到布局
        left_panel.addWidget(self.spam_button) #
        left_panel.addWidget(self.refresh_button)
        left_panel.addStretch()
        
        left_widget = QWidget()
        left_widget.setLayout(left_panel)

        # --- 中间邮件列表 ---
        self.email_list = QListWidget()
        self.email_list.itemClicked.connect(self.display_email)

        # --- 右侧邮件内容 ---
        self.email_viewer = QTextBrowser()
        self.email_viewer.setOpenExternalLinks(False) # 手动处理链接点击

        # --- 使用QSplitter创建可调整的三栏布局 ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(self.email_list)
        main_splitter.addWidget(self.email_viewer)
        
        main_splitter.setStretchFactor(0, 1) # 左侧栏比例
        main_splitter.setStretchFactor(1, 2) # 中间列表比例
        main_splitter.setStretchFactor(2, 5) # 右侧内容比例

        self.setCentralWidget(main_splitter)

    def prompt_login(self):
        dialog = LoginDialog(self)
        if dialog.exec():
            server_ip, email, password = dialog.get_credentials() #
            
            try:
                # 在这里将用户的 email 传递给 EmailHandler 的构造函数
                self.email_handler = EmailHandler(user_email=email, smtp_host=server_ip, pop3_host=server_ip) 
            except Exception as e:
                QMessageBox.critical(self, "连接错误", f"无法创建EmailHandler: {e}")
                self.close()
                return

            self.current_user = email
            self.current_password = password
            self.user_label.setText(f"欢迎, {email}")
            self.show_inbox()
        else:
            self.close()

    def prompt_login(self):
        dialog = LoginDialog(self)
        if dialog.exec():
            # 获取包含服务器IP的凭据
            server_ip, email, password = dialog.get_credentials()
            
            # 使用用户输入的IP地址来初始化EmailHandler
            try:
                self.email_handler = EmailHandler(user_email=email, smtp_host=server_ip, pop3_host=server_ip)
            except Exception as e:
                QMessageBox.critical(self, "连接错误", f"无法创建EmailHandler: {e}")
                self.close()
                return

            self.current_user = email
            self.current_password = password
            self.user_label.setText(f"欢迎, {email}")
            self.show_inbox()
        else:
            self.close()

    def show_inbox(self):
        if not self.current_user or not self.email_handler:
            # print("用户未登录或 email_handler 未初始化，无法显示收件箱。")
            if not self.current_user: # 如果是未登录，prompt_login会处理
                 self.prompt_login() # 确保登录流程被调用
            return
        
        # fetch_inbox 现在只下载新邮件并分类存储。
        # UI的刷新应基于 get_local_emails。
        # 所以，首先触发一次 fetch (在后台)
        self.email_list.clear()
        self.email_viewer.clear()
        self.current_message = None
        self.email_list.addItem("正在从服务器获取新邮件并刷新...")

        self.worker = EmailWorker(self.email_handler, "fetch", (self.current_user, self.current_password))
        # on_fetch_finished 会被调用，它内部再调用 show_folder_contents
        self.worker.finished.connect(self.on_fetch_finished) 
        self.worker.start()

    def on_fetch_finished(self, result):
        self.email_list.clear()
        success, data_from_fetch = result # data_from_fetch 是新下载的邮件列表
        
        if success:
            # print(f"Fetched {len(data_from_fetch)} new emails.")
            # fetch_inbox 返回的已经是包含 is_spam 标记的邮件列表
            # get_local_emails 会加载包括新下载在内的所有本地邮件，并进行动态分类
            # 因此，我们直接调用 get_local_emails 来刷新收件箱视图
            # 这也确保了如果 get_local_emails 内部移动了邮件到垃圾箱，视图能正确反映
            self.show_folder_contents(self.email_handler.inbox_storage_path, "收件箱")
        else:
            QMessageBox.critical(self, "错误", f"获取邮件失败: {data_from_fetch}")
            # 如果获取失败，仍尝试加载本地缓存的收件箱
            self.show_folder_contents(self.email_handler.inbox_storage_path, "收件箱 (缓存)")

    # 新增一个通用方法来显示任何文件夹的内容
    def show_folder_contents(self, folder_path, folder_name_display):
        self.email_list.clear()
        self.email_viewer.clear()
        self.current_message = None

        if not self.email_handler:
             self.email_list.addItem(f"{folder_name_display} 未加载 (邮件处理器未初始化)。")
             return

        self.email_list.addItem(f"正在加载 {folder_name_display} 中的邮件...")
        
        # get_local_emails 现在会处理收件箱的动态分类
        # 对于其他文件夹（已发送、垃圾邮件），它只是加载内容
        local_emails = self.email_handler.get_local_emails(folder_path)
        self.email_list.clear()

        if not local_emails:
            self.email_list.addItem(f"{folder_name_display} 是空的。")
        else:
            for email_data in local_emails:
                sender_key = 'from' if folder_path == self.email_handler.inbox_storage_path or folder_path == self.email_handler.spam_storage_path else 'to'
                item_text = f"{'发件人' if sender_key == 'from' else '收件人'}: {email_data.get(sender_key, 'N/A')}\n主题: {email_data.get('subject', '无主题')}"
                
                # 可选：为垃圾邮件添加视觉提示
                if email_data.get('is_spam') and folder_path != self.email_handler.spam_storage_path: # 如果在收件箱但标记为垃圾邮件 (理论上不应发生，因已被移动)
                    item_text = "[疑似垃圾邮件] " + item_text
                elif folder_path == self.email_handler.spam_storage_path:
                     item_text = "[垃圾邮件] " + item_text

                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, email_data)
                self.email_list.addItem(item)

    def show_sent_folder(self):
        if not self.email_handler: return
        self.show_folder_contents(self.email_handler.sent_storage_path, "已发送")
    
    def show_spam_folder(self):
        """显示本地“垃圾邮件”文件夹中的邮件。"""
        if not self.email_handler:
            QMessageBox.warning(self, "提示", "邮件处理器未初始化。")
            return
            
        self.email_list.clear()
        self.email_viewer.clear()
        self.current_message = None # 清除当前邮件状态
        self.email_list.addItem("正在加载垃圾邮件...")
        
        # self.email_handler.spam_storage_path 应该是用户专属的垃圾邮件路径
        spam_emails = self.email_handler.get_local_emails(self.email_handler.spam_storage_path)
        self.email_list.clear()
        
        if not spam_emails:
            self.email_list.addItem("垃圾邮件文件夹是空的。")
        else:
            for email_data in spam_emails:
                # 邮件列表项可以根据 is_spam 状态改变外观，不过这里都是垃圾邮件
                item_text = f"发件人: {email_data.get('from', 'N/A')}\n主题: {email_data.get('subject', '无主题')}"
                if email_data.get('is_spam'): # 可以加个标记，虽然在此文件夹理论上都为True
                    item_text = "[垃圾邮件] " + item_text
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, email_data)
                self.email_list.addItem(item)
    
    def display_email(self, item):
        email_data = item.data(Qt.ItemDataRole.UserRole)
        if not email_data or 'path' not in email_data:
            self.email_viewer.setPlainText("无法加载邮件数据。")
            return

        self.current_message_is_encrypted = False # 重置状态
        self.current_decrypted_content = None

        try:
            with open(email_data['path'], 'rb') as f:
                self.current_message = message_from_bytes(f.read())
        except Exception as e:
            self.email_viewer.setPlainText(f"无法读取邮件文件: {e}")
            return
        
        html_body = ""
        text_body = ""
        attachments = []
        is_pgp_encrypted_email = False # 标记是否检测到PGP/MIME结构

        # 检查邮件是否可能是PGP加密的 (基于 temp 中 decrypt_and_verify_email_from_message 的逻辑)
        # 简单检查：Content-Type: multipart/encrypted 或存在 signature.asc 附件
        # 一个更可靠的检查是在尝试解密时进行。
        # 这里我们先做个初步判断，UI上可以提示用户。
        
        # 简单的PGP结构检测 (不完美，但可用于UI提示)
        # PGP/MIME 签名邮件是 multipart/signed
        # PGP/MIME 加密邮件是 multipart/encrypted
        content_type_header = self.current_message.get_content_type()
        if content_type_header == 'multipart/encrypted':
            is_pgp_encrypted_email = True
            # 对于加密邮件，我们通常不直接显示其内部结构，而是尝试解密
            # 暂不遍历其 parts，直接在下面尝试解密
        elif self.current_message.is_multipart():
            for part in self.current_message.walk():
                if part.get_filename() == "signature.asc" and part.get_content_type() == "application/pgp-signature":
                    # 这更像是一个签名的邮件，可能加密也可能不加密。
                    # 如果邮件主体是 text/plain 且看起来是 PGP block，也可能是加密的。
                    # is_pgp_encrypted_email = True # 暂定，需要解密才能确认
                    pass # 发现签名，但主体是否加密待定
                # 进一步检查是否存在PGP加密的数据块（通常是 application/octet-stream 作为第一部分）
                # 或 text/plain 但内容是 BEGIN PGP MESSAGE
                if part.get_content_type() == 'application/octet-stream' and not part.get_filename():
                    # 可能是加密数据
                    pass

        # 如果检测到或怀疑是加密邮件，这里可以尝试解密 (需要密钥路径和密码)
        # 目前我们没有UI获取这些，所以只做个标记或显示提示
        if is_pgp_encrypted_email: # 或者更复杂的判断
            self.current_message_is_encrypted = True
            # TODO: 将来在这里添加调用解密逻辑的UI交互
            # 例如: decrypted_content = self.prompt_for_decryption_keys_and_decrypt(self.current_message)
            # if decrypted_content:
            #    text_body = decrypted_content # 解密后通常是纯文本
            #    html_body = "" # 或者，如果解密后内容本身是HTML标记...
            # else:
            #    text_body = "此邮件已加密。请提供密钥以解密。\n\n" + self.current_message.as_string()
            placeholder_encrypted_text = "此邮件内容已加密。查看功能需要PGP密钥。\n\n"
            try:
                # 尝试提取加密文本部分给用户看个大概
                for part in self.current_message.walk():
                    if part.get_content_type() == 'application/octet-stream' and not part.get_filename(): # PGP/MIME 加密数据部分
                         payload = part.get_payload(decode=True)
                         placeholder_encrypted_text += payload.decode('ascii', errors='ignore') # 加密数据通常是ASCII
                         break
                    elif part.get_content_type() == 'text/plain' and not part.get_filename(): # 有时加密内容在text/plain
                         payload = part.get_payload(decode=True)
                         text_content = payload.decode(part.get_content_charset() or 'utf-8', errors='ignore')
                         if "BEGIN PGP MESSAGE" in text_content:
                            placeholder_encrypted_text += text_content
                            break
                text_body = placeholder_encrypted_text
            except Exception:
                 text_body = "此邮件已加密，且无法预览其原始加密文本。"


        # 如果不是（或未能成功解密）加密邮件，则按原方式处理
        if not self.current_message_is_encrypted or not text_body: # 如果没被标记为加密，或标记了但没有解密内容
            if self.current_message.is_multipart():
                for part in self.current_message.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition"))
                    
                    if "attachment" in content_disposition:
                        filename = part.get_filename()
                        if filename:
                            attachments.append(filename)
                    elif content_type == "text/html" and not html_body: # 只取第一个HTML部分
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        html_body = payload.decode(charset, errors='ignore')
                    elif content_type == "text/plain" and not text_body and not html_body: # 如果没有HTML，或HTML优先但没找到，则用纯文本
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        text_body = payload.decode(charset, errors='ignore')
            else: # 非 multipart 邮件
                payload = self.current_message.get_payload(decode=True)
                charset = self.current_message.get_content_charset() or 'utf-8'
                if self.current_message.get_content_type() == "text/html":
                    html_body = payload.decode(charset, errors='ignore')
                else: 
                    text_body = payload.decode(charset, errors='ignore')
        
        # 优先显示HTML，如果没有则显示纯文本
        display_body = html_body if html_body else f"<pre>{text_body}</pre>" # 用<pre>保留纯文本格式

        headers_html = f"""
        <b>发件人:</b> {self.current_message.get('From', 'N/A')}<br>
        <b>收件人:</b> {self.current_message.get('To', 'N/A')}<br>
        <b>主题:</b> {self.current_message.get('Subject', 'N/A')}<br>
        <b>日期:</b> {self.current_message.get('Date', 'N/A')}<br>
        """
        if email_data.get('is_spam'):
            headers_html = "<i><font color='red'>[此邮件被分类为垃圾邮件]</font></i><br>" + headers_html
        if self.current_message_is_encrypted and not self.current_decrypted_content: # 提示邮件已加密
             headers_html += "<i><font color='orange'>[此邮件内容已加密]</font></i><br>"


        attachments_html = ""
        if attachments:
            attachments_html += "<b>附件 (点击文件名可下载):</b><br>"
            for filename in attachments:
                # 确保文件名是字符串，并且清理一下以防万一
                safe_filename = str(filename) if filename else "untitled_attachment"
                attachments_html += f'&nbsp;&nbsp; - <a href="attachment:{safe_filename}">{safe_filename}</a><br>'
        
        final_html = headers_html + attachments_html + "<hr>" + display_body
        self.email_viewer.setHtml(final_html)
        
    def open_compose_window(self):
        if not self.current_user or not self.email_handler: # 检查 email_handler 也被初始化
            QMessageBox.warning(self, "提示", "请先登录！")
            return
        
        # TODO: ComposeWindow 将来需要有UI选项来启用加密并选择密钥文件
        # encrypt_enabled, sender_key, sender_pass, recipient_key = dialog.get_encryption_settings()
        
        dialog = ComposeWindow(self.current_user, self)
        if dialog.exec():
            email_data = dialog.get_email_data() # 包含 sender, recipient, subject, body, attachment_path

            # 为 PGP 参数准备默认值 (目前为不加密)
            email_data['encrypt'] = False 
            email_data['sender_private_key_path'] = None # dialog 中应提供选择
            email_data['sender_private_key_passphrase'] = None # dialog 中应提供输入
            email_data['recipient_public_key_path'] = None # dialog 中应提供选择

            # EmailWorker 的 'send' action 的 data 参数现在需要包含所有 send_email 的参数
            self.worker = EmailWorker(handler=self.email_handler, 
                                     action="send", 
                                     credentials=(self.current_user, self.current_password), # 凭据可能不需要用于发送，但保持结构一致
                                     data=email_data) # email_data 包含所有发送参数
            self.worker.finished.connect(self.on_send_finished)
            self.worker.start()
            
    def on_send_finished(self, result):
        success, message = result
        if success:
            QMessageBox.information(self, "成功", message)
            # 发送成功后自动刷新已发送文件夹
            self.show_sent_folder()
        else:
            QMessageBox.critical(self, "发送失败", message)

    def save_attachment(self, url):
        # 检查链接是否是我们自定义的附件链接
        if url.scheme() == "attachment":
            filename = url.path()
            if not self.current_message:
                return

            # 遍历当前邮件的所有部分，找到对应的附件
            for part in self.current_message.walk():
                if part.get_filename() == filename:
                    # 弹出“另存为”对话框
                    save_path, _ = QFileDialog.getSaveFileName(self, "保存附件", filename)
                    if save_path:
                        try:
                            # 获取附件的二进制内容并写入文件
                            with open(save_path, "wb") as f:
                                f.write(part.get_payload(decode=True))
                            QMessageBox.information(self, "成功", f"附件 '{filename}' 已成功保存！")
                        except Exception as e:
                            QMessageBox.critical(self, "错误", f"保存附件失败: {e}")
                    return # 找到并处理后即可退出循环
        else:
            # 如果是普通的http(s)链接，就用默认浏览器打开
            webbrowser.open(url.toString())