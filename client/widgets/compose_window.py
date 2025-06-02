import os
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QTextEdit, QPushButton, QFileDialog, QFormLayout, QLabel

class ComposeWindow(QDialog):
    def __init__(self, sender_email, parent=None):
        super().__init__(parent)
        self.setWindowTitle("写邮件")
        self.sender = sender_email
        self.attachment_path = None

        self.to_input = QLineEdit()
        self.subject_input = QLineEdit()
        self.body_input = QTextEdit() # 支持富文本/HTML
        
        form_layout = QFormLayout()
        form_layout.addRow(QLabel("收件人:"), self.to_input)
        form_layout.addRow(QLabel("主题:"), self.subject_input)
        
        self.attach_button = QPushButton("添加附件")
        self.attach_button.clicked.connect(self.add_attachment)
        self.send_button = QPushButton("发送")
        self.send_button.clicked.connect(self.accept)

        layout = QVBoxLayout()
        layout.addLayout(form_layout)
        layout.addWidget(self.body_input)
        layout.addWidget(self.attach_button)
        layout.addWidget(self.send_button)
        self.setLayout(layout)
        self.resize(600, 500)

    def add_attachment(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择附件")
        if path:
            self.attachment_path = path
            self.attach_button.setText(f"已选择附件: {os.path.basename(path)}")
            
    def get_email_data(self):
        return {
            "sender": self.sender,
            "recipient": self.to_input.text(),
            "subject": self.subject_input.text(),
            "body": self.body_input.toHtml(),
            # 将键名从 "attachment" 修改为 "attachment_path"
            "attachment_path": self.attachment_path
        }