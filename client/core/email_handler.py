import smtplib
import poplib
import os
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders, message_from_bytes
import math
import re
import pandas as pd
import codecs
import jieba
from tqdm import tqdm
from bs4 import BeautifulSoup
import base64
import pgpy


def load_formatted_data():
    """
    加载格式化后的标签-路径列表
    spam列为1代表是垃圾邮件，0代表普通邮件
    path列代表该邮件路径
    :return:(DataFrame)index
    """
    # 加载数据集
    index = pd.read_csv('index', sep=' ', names=['spam', 'path'])
    index.spam = index.spam.apply(lambda x: 1 if x == 'spam' else 0)
    index.path = index.path.apply(lambda x: x[1:])
    return index


def load_stop_word():
    """
    读出停用词列表
    :return: (List)_stop_words
    """
    with codecs.open("E:\six_courses\computer_network\homework\SMPT-POP3-based-Mail-System-master\client\core\stop", "r") as f:
        lines = f.readlines()
    _stop_words = [i.strip() for i in lines]
    return _stop_words


def get_mail_content(path):
    """
    遍历得到每封邮件的词汇字符串
    :param path: 邮件路径
    :return:(Str)content
    """
    with codecs.open(path, "r", encoding="gbk", errors="ignore") as f:
        lines = f.readlines()

    for i in range(len(lines)):
        if lines[i] == '\n':
            # 去除第一个空行，即在第一个空行之前的邮件协议内容全部舍弃
            lines = lines[i:]
            break
    content = ''.join(''.join(lines).strip().split())
    # print(content)
    return content


def create_word_dict(content, stop_words_list):
    """
    依据邮件的词汇字符串统计词汇出现记录，依据停止词列表除去某些词语
    :param content: 邮件的词汇字符串
    :param stop_words_list:停止词列表
    :return:(Dict)word_dict
    """
    word_list = []
    word_dict = {}
    # word_dict key:word, value:1
    content = re.findall(u"[\u4e00-\u9fa5]", content)
    content = ''.join(content)
    word_list_temp = jieba.cut(content)
    for word in word_list_temp:
        if word != '' and word not in stop_words_list:
            word_list.append(word)
    for word in word_list:
        word_dict[word] = 1
    return word_dict


def train_dataset(dataset_to_train):
    """
    对数据集进行训练, 统计训练集中某个词在普通邮件和垃圾邮件中的出现次数
    :param dataset_to_train: 将要用来训练的数据集
    :return: Tuple(词汇出现次数字典_train_word_dict, 垃圾邮件总数spam_count, 正常邮件总数ham_count)
    """
    _train_word_dict = {}
    # 使用新格式：{"spam": count, "ham": count}
    for word_dict, spam in tqdm(zip(dataset_to_train.word_dict, dataset_to_train.spam), desc="Training"):
        for word in word_dict:
            _train_word_dict.setdefault(word, {"spam": 0, "ham": 0})
            if spam == 1:
                _train_word_dict[word]["spam"] += 1
            else:
                _train_word_dict[word]["ham"] += 1
    ham_count = dataset_to_train.spam.value_counts()[0]
    spam_count = dataset_to_train.spam.value_counts()[1]
    return _train_word_dict, spam_count, ham_count


def predict_dataset(train_word_dict, spam_count, ham_count, data, stop_words):
    """
    使用朴素贝叶斯算法判断邮件是否为垃圾邮件。
    参数:
        train_word_dict: 训练集的词汇统计字典，格式为 {word: {'spam': count, 'ham': count}}
        spam_count: 训练集中垃圾邮件的总数
        ham_count: 训练集中正常邮件的总数
        data: 包含待预测邮件的词频字典，格式为 {'word_dict': dict}
        stop_words: 停用词列表
    返回:
        1: 垃圾邮件
        0: 正常邮件
    """
    word_dict = data['word_dict']
    total_emails = spam_count + ham_count
    log_p_spam = math.log(spam_count / total_emails)
    log_p_ham = math.log(ham_count / total_emails)
    
    log_likelihood_spam = 0.0
    log_likelihood_ham = 0.0
    
    for word, count in word_dict.items():
        if word in stop_words:
            continue
        # print("train_word_dict")
        # print(train_word_dict)
        # train_word_dict = {k: v for k, v in train_word_dict.items()}
        

        word_stats = train_word_dict.get(word, {"spam": 0, "ham": 0})
        p_word_given_spam = (word_stats["spam"] + 1) / (spam_count + 2)
        p_word_given_ham = (word_stats["ham"] + 1) / (ham_count + 2)
        
        log_likelihood_spam += math.log(p_word_given_spam)
        log_likelihood_ham += math.log(p_word_given_ham)
    
    return 1 if (log_p_spam + log_likelihood_spam) > (log_p_ham + log_likelihood_ham) else 0


def save_train_word_dict(train_word_dict):
    with codecs.open("train_word_dict", "w", encoding="gbk", errors="ignore") as f:
        f.write(train_word_dict)

def load_train_word_dict():
    """
    加载训练好的词汇字典
    返回格式: {word: {"spam": count, "ham": count}}
    """
    file_path = "E:\\six_courses\\computer_network\\homework\\SMPT-POP3-based-Mail-System-master\\client\\core\\train_word_dict"
    try:
        with codecs.open(file_path, "r", encoding="gbk", errors="ignore") as f:
            content = f.read().strip()
            
        # 安全解析字典内容
        if content.startswith("{") and content.endswith("}"):
            train_dict = eval(content)  # 注意：实际项目中应使用更安全的方式如 json.loads
            # 转换为标准格式
            return {
                word: {"spam": counts[1], "ham": counts[0]} 
                for word, counts in train_dict.items()
            }
        else:
            raise ValueError("Invalid train_word_dict file format")
    except Exception as e:
        print(f"加载 train_word_dict 失败: {e}")
        return {}  # 返回空字典避免程序崩溃


def is_spam(email_content, train_word_dict, spam_count, ham_count, stop_words):
    """
    判断邮件是否为垃圾邮件
    :param email_content: 邮件内容
    :param train_word_dict: 训练好的词汇字典
    :param spam_count: 垃圾邮件总数
    :param ham_count: 普通邮件总数
    :param stop_words: 停用词列表
    :return: True 是垃圾邮件，False 不是
    """
    word_dict = create_word_dict(email_content, stop_words)
    return predict_dataset(train_word_dict, spam_count, ham_count, {"word_dict": word_dict}, stop_words) == 1




class EmailHandler:
    def __init__(self, smtp_host='localhost', smtp_port=1025, pop3_host='localhost', pop3_port=1100):
        self.smtp_server_info = (smtp_host, smtp_port)
        self.pop3_server_info = (pop3_host, pop3_port)
        # 为收件箱和已发送文件夹创建不同的存储路径
        self.inbox_storage_path = 'eml_storage/inbox'
        self.sent_storage_path = 'eml_storage/sent'
        self.spam_storage_path = 'eml_storage/trash'
        os.makedirs(self.inbox_storage_path, exist_ok=True)
        os.makedirs(self.sent_storage_path, exist_ok=True)
        os.makedirs(self.spam_storage_path, exist_ok=True)

        # 加载垃圾邮件检测模型
        self.train_word_dict = load_train_word_dict()
        self.spam_count = 34429
        self.ham_count = 17268

        self.stop_words = load_stop_word()
    def _classify_email(self, msg):
        """从邮件对象中提取正文并分类"""
        email_text = self.get_text_from_email(msg)
        if not email_text:
            return False
        processed_text = self.preprocess_text(email_text, self.stop_words)
        return is_spam(
            email_content=processed_text,
            train_word_dict=self.train_word_dict,
            spam_count=self.spam_count,
            ham_count=self.ham_count,
            stop_words=self.stop_words
        )

    def get_text_from_email(self, msg):
        """提取邮件的纯文本内容"""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    return payload.decode("utf-8", errors="ignore")
                elif content_type == "text/html":
                    payload = part.get_payload(decode=True)
                    html = payload.decode("utf-8", errors="ignore")
                    soup = BeautifulSoup(html, "html.parser")
                    return soup.get_text()
        else:
            payload = msg.get_payload(decode=True)
            if msg.get_content_type() == "text/html":
                soup = BeautifulSoup(payload.decode("utf-8", errors="ignore"), "html.parser")
                return soup.get_text()
            else:
                return payload.decode("utf-8", errors="ignore")
        return None

    def preprocess_text(self, text, stop_words):
        """清洗和分词中文文本"""
        text = re.sub(r"[^\u4e00-\u9fa5]", "", text)  # 去除非中文字符
        words = jieba.cut(text)
        processed_text = " ".join([word for word in words if word not in stop_words])
        return processed_text

    def send_email(self, sender, recipient, subject, body, attachment_path=None,
                   encrypt=False,
                   sender_private_key_path=None, sender_private_key_passphrase=None,
                   recipient_public_key_path=None):
        """
        发送邮件，支持附件和端到端加密签名。
        encrypt: 是否加密
        sender_private_key_path: 发送方私钥路径
        sender_private_key_passphrase: 发送方私钥密码
        recipient_public_key_path: 接收方公钥路径
        """
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = recipient
        msg['Subject'] = subject

        if encrypt:
            encrypted_body, signature = encrypt_and_sign_email(
                body, sender_private_key_path, sender_private_key_passphrase, recipient_public_key_path
            )
            # 邮件正文为密文
            msg.attach(MIMEText(encrypted_body, 'plain'))
            # 签名作为附件
            sig_part = MIMEText(signature, 'plain')
            sig_part.add_header('Content-Disposition', 'attachment', filename='signature.asc')
            msg.attach(sig_part)
        else:
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

                if self._classify_email(msg):
                    target_dir = self.spam_storage_path
                else:
                    target_dir = self.inbox_storage_path
                # 使用唯一标识符来命名文件，防止重复
                filename = f"email_{email_address}_{msg.get('Message-ID', i+1)}.eml"
                file_path = os.path.join(target_dir, filename)
                with open(file_path, "wb") as f:
                    f.write(msg_bytes)
                
                emails.append({
                    "id": i + 1,
                    "from": msg['From'],
                    "subject": msg['Subject'],
                    "date": msg['Date'],
                    "path": file_path,
                    "is_spam": target_dir == self.spam_storage_path
                })

            pop_server.quit()
            return True, emails
        except poplib.error_proto as e:
            return False, f"登录或接收失败: {e}"
        except Exception as e:
            return False, f"发生未知错误: {e}"

    def get_local_emails(self, folder_path):
        """
        从本地文件夹加载.eml文件。
        对 inbox 的最新邮件进行垃圾邮件检查，如果是垃圾邮件则移动到 trash 目录。
        """

        emails = []
        if not os.path.exists(folder_path):
            return emails

        # 如果是 inbox 目录，检查最新邮件是否为垃圾邮件
        if folder_path == self.inbox_storage_path:
            # 获取所有 .eml 文件并按修改时间降序排序
            eml_files = [
                f for f in os.listdir(folder_path)
                if f.endswith(".eml")
            ]
            eml_files.sort(key=lambda f: os.path.getmtime(os.path.join(folder_path, f)), reverse=True)

            # 检查最新邮件
            if eml_files:
                latest_file = eml_files[0]
                file_path = os.path.join(folder_path, latest_file)
                try:
                    with open(file_path, 'rb') as f:
                        msg = message_from_bytes(f.read())
                        # 检查是否为垃圾邮件
                        if self._classify_email(msg):
                            # 移动到 trash 目录

                            trash_path = os.path.join(self.spam_storage_path, latest_file)
                            os.rename(file_path, trash_path)
                            print(f"移动垃圾邮件到 trash: {latest_file}")
                            # 从 eml_files 中移除已处理的文件
                            eml_files.pop(0)
                except Exception as e:
                    print(f"处理最新邮件失败 {latest_file}: {e}")

            # 处理剩余邮件
            for filename in eml_files:
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

        # 非 inbox 目录（如 sent 或 trash）直接加载所有邮件
        else:
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

        # 按文件修改时间降序排序，最新的邮件在最前面
        return sorted(emails, key=lambda x: os.path.getmtime(x['path']), reverse=True)

    def encrypt_and_sign_email(plain_text, sender_private_key_path, sender_private_key_passphrase, recipient_public_key_path):
        recipient_key, _ = pgpy.PGPKey.from_file(recipient_public_key_path)
        sender_key, _ = pgpy.PGPKey.from_file(sender_private_key_path)
        if sender_key.is_protected:
            sender_key.unlock(sender_private_key_passphrase)
        message = pgpy.PGPMessage.new(plain_text)
        encrypted_message = recipient_key.encrypt(message)
        signature = sender_key.sign(encrypted_message)
        return str(encrypted_message), str(signature)

    def verify_and_decrypt_email(encrypted_text, signature_text, recipient_private_key_path, recipient_private_key_passphrase, sender_public_key_path):
        recipient_key, _ = pgpy.PGPKey.from_file(recipient_private_key_path)
        if recipient_key.is_protected:
            recipient_key.unlock(recipient_private_key_passphrase)
        sender_key, _ = pgpy.PGPKey.from_file(sender_public_key_path)
        encrypted_message = pgpy.PGPMessage.from_blob(encrypted_text)
        signature = pgpy.PGPSignature.from_blob(signature_text)
        verified = sender_key.verify(encrypted_message, signature)
        if not verified:
            raise ValueError("签名验证失败，邮件可能被篡改！")
        decrypted_message = recipient_key.decrypt(encrypted_message)
        return decrypted_message.message

    def decrypt_and_verify_email(self, msg, recipient_private_key_path, recipient_private_key_passphrase, sender_public_key_path):
        """
        解密并验证邮件内容
        msg: email.message.Message对象
        返回解密后的正文字符串
        """
        encrypted_text = None
        signature_text = None
        # 提取密文和签名
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                fname = part.get_filename()
                if ctype == "text/plain" and not fname:
                    encrypted_text = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                elif fname == "signature.asc":
                    signature_text = part.get_payload(decode=True).decode("utf-8", errors="ignore")
        else:
            encrypted_text = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
        if not encrypted_text or not signature_text:
            raise ValueError("未找到密文或签名")
        return verify_and_decrypt_email(
            encrypted_text, signature_text,
            recipient_private_key_path, recipient_private_key_passphrase,
            sender_public_key_path
        )


handler = EmailHandler()
handler.send_email(
    sender="alice@example.com",
    recipient="bob@example.com",
    subject="加密测试",
    body="你好，这是一封加密邮件！",
    encrypt=True,
    sender_private_key_path="alice_private.asc",
    sender_private_key_passphrase="alicepass",
    recipient_public_key_path="bob_public.asc"
)