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

        self.refresh_button = QPushButton(" 刷新")
        self.refresh_button.clicked.connect(self.show_inbox) # 刷新应该重新加载收件箱

        left_panel.addWidget(self.user_label, alignment=Qt.AlignmentFlag.AlignCenter)
        left_panel.addWidget(self.compose_button)
        left_panel.addWidget(self.inbox_button)
        left_panel.addWidget(self.sent_button) # 将按钮添加到布局
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
            # 获取包含服务器IP的凭据
            server_ip, email, password = dialog.get_credentials()
            
            # 使用用户输入的IP地址来初始化EmailHandler
            try:
                self.email_handler = EmailHandler(smtp_host=server_ip, pop3_host=server_ip)
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
        """获取并显示服务器收件箱的邮件。"""
        if not self.current_user:
            return
        self.email_list.clear()
        self.email_viewer.clear()
        self.email_list.addItem("正在从服务器获取邮件...")
        
        # 使用工作线程防止UI冻结
        self.worker = EmailWorker(self.email_handler, "fetch", (self.current_user, self.current_password))
        self.worker.finished.connect(self.on_fetch_finished)
        self.worker.start()

    def on_fetch_finished(self, result):
        self.email_list.clear()
        success, data = result
        if success:
            # 加载本地收件箱的邮件以显示完整历史
            all_emails = self.email_handler.get_local_emails(self.email_handler.inbox_storage_path)
            
            if not all_emails:
                self.email_list.addItem("收件箱是空的。")
            else:
                for email_data in all_emails:
                    item_text = f"发件人: {email_data.get('from', 'N/A')}\n主题: {email_data.get('subject', '无主题')}"
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.ItemDataRole.UserRole, email_data) # 存储完整数据
                    self.email_list.addItem(item)
        else:
            QMessageBox.critical(self, "错误", data)

    def show_sent_folder(self):
        """显示本地“已发送”文件夹中的邮件。"""
        self.email_list.clear()
        self.email_viewer.clear()
        self.email_list.addItem("正在加载已发送邮件...")
        
        sent_emails = self.email_handler.get_local_emails(self.email_handler.sent_storage_path)
        self.email_list.clear()
        
        if not sent_emails:
            self.email_list.addItem("已发送文件夹是空的。")
        else:
            for email_data in sent_emails:
                item_text = f"收件人: {email_data.get('to', 'N/A')}\n主题: {email_data.get('subject', '无主题')}"
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, email_data)
                self.email_list.addItem(item)
    
    def display_email(self, item):
        email_data = item.data(Qt.ItemDataRole.UserRole)
        if not email_data or 'path' not in email_data:
            return

        with open(email_data['path'], 'rb') as f:
            self.current_message = message_from_bytes(f.read())
        
        html_body = ""
        text_body = ""
        attachments = []
        
        if self.current_message.is_multipart():
            for part in self.current_message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                if "attachment" in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        attachments.append(filename)
                elif content_type == "text/html" and not html_body:
                    html_body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore')
                elif content_type == "text/plain" and not text_body:
                    text_body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore')
        else: # 非 multipart 邮件
            if self.current_message.get_content_type() == "text/html":
                html_body = self.current_message.get_payload(decode=True).decode(self.current_message.get_content_charset() or 'utf-8', errors='ignore')
            else: # 默认视为纯文本
                text_body = self.current_message.get_payload(decode=True).decode(self.current_message.get_content_charset() or 'utf-8', errors='ignore')
        
        # 优先显示HTML，如果没有则显示纯文本
        display_body = html_body if html_body else f"<pre>{text_body}</pre>"

        headers_html = f"""
        <b>发件人:</b> {self.current_message['From']}<br>
        <b>收件人:</b> {self.current_message['To']}<br>
        <b>主题:</b> {self.current_message['Subject']}<br>
        <b>日期:</b> {self.current_message['Date']}<br>
        """
        
        attachments_html = ""
        if attachments:
            attachments_html += "<b>附件 (点击文件名可下载):</b><br>"
            for filename in attachments:
                attachments_html += f'&nbsp;&nbsp; - <a href="attachment:{filename}">{filename}</a><br>'
        
        final_html = headers_html + attachments_html + "<hr>" + display_body
        self.email_viewer.setHtml(final_html)
        
    def open_compose_window(self):
        if not self.current_user:
            QMessageBox.warning(self, "提示", "请先登录！")
            return
        
        dialog = ComposeWindow(self.current_user, self)
        if dialog.exec():
            email_data = dialog.get_email_data()
            self.worker = EmailWorker(self.email_handler, "send", (self.current_user, self.current_password), email_data)
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