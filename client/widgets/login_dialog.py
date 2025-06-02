from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QPushButton, QLabel, QFormLayout

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("登录 GemMail")

        # 新增服务器地址输入框，并给一个默认值
        self.server_ip_input = QLineEdit("127.0.0.1", self) 
        self.email_input = QLineEdit(self)
        self.password_input = QLineEdit(self)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        layout = QFormLayout()
        # 将新输入框添加到布局中
        layout.addRow(QLabel("服务器地址:"), self.server_ip_input)
        layout.addRow(QLabel("邮箱:"), self.email_input)
        layout.addRow(QLabel("密码:"), self.password_input)
        
        self.login_button = QPushButton("登录", self)
        self.login_button.clicked.connect(self.accept)
        
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addWidget(self.login_button)
        self.setLayout(main_layout)

    def get_credentials(self):
        # 返回包含服务器地址的元组
        return (
            self.server_ip_input.text(),
            self.email_input.text(), 
            self.password_input.text()
        )