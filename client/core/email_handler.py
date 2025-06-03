import smtplib
import socket
import traceback
import poplib
import os
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders, message_from_bytes
import re # 导入re模块用于更安全的清理
import hashlib # <--- 添加这一行

# 新增的 imports
import math # temp 中 predict_dataset 使用
import pandas as pd # temp 中 load_formatted_data 使用
import codecs # temp 中 load_stop_word, get_mail_content, save_train_word_dict, load_train_word_dict 使用
import jieba # temp 中 create_word_dict, preprocess_text 使用
# from tqdm import tqdm # tqdm 主要用于训练过程，如果只加载预训练模型，可能不是直接必须，但最好保留
from bs4 import BeautifulSoup # temp 中 get_text_from_email 使用
# import base64 # base64 通常由 email.encoders 处理，但如果直接使用可以保留
import pgpy # temp 中 PGP 功能使用

# Spam detection helper functions from temp/client/core/email_handler.py
def load_formatted_data():
    """
    加载格式化后的标签-路径列表
    spam列为1代表是垃圾邮件，0代表普通邮件
    path列代表该邮件路径
    :return:(DataFrame)index
    """
    # 加载数据集
    index = pd.read_csv('index', sep=' ', names=['spam', 'path']) # 假设 'index' 文件在项目根目录
    index.spam = index.spam.apply(lambda x: 1 if x == 'spam' else 0)
    index.path = index.path.apply(lambda x: x[1:])
    return index


def load_stop_word():
    """
    读出停用词列表
    :return: (List)_stop_words
    """
    with codecs.open("./stop", "r", encoding="utf-8", errors="ignore") as f: # 假设 'stop' 文件在项目根目录, 使用 utf-8
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
            lines = lines[i:]
            break
    content = ''.join(''.join(lines).strip().split())
    return content


def create_word_dict(content, stop_words_list):
    """
    依据邮件的词汇字符串统计词汇出现记录，依据停止词列表除去某些词语
    :param content: 邮件的词汇字符串
    :param stop_words_list:停止词列表
    :return:(Dict)word_dict
    """
    word_dict = {}
    content = re.findall(u"[\u4e00-\u9fa5]", content) # 只保留中文字符
    content = ''.join(content)
    word_list_temp = jieba.cut(content)
    for word in word_list_temp:
        if word != '' and word not in stop_words_list:
            word_dict[word] = 1 # 使用1表示词语出现
    return word_dict


# train_dataset 函数主要用于训练模型，如果您不打算在客户端中重新训练模型，可以不添加此函数。
# 我们将主要使用 load_train_word_dict 来加载预训练模型。

def predict_dataset(train_word_dict, spam_count, ham_count, data, stop_words):
    """
    使用朴素贝叶斯算法判断邮件是否为垃圾邮件。
    """
    word_dict = data['word_dict']
    total_emails = spam_count + ham_count
    # 避免 spam_count 或 ham_count 为0导致 log(0)
    log_p_spam = math.log((spam_count + 1e-9) / (total_emails + 2e-9)) 
    log_p_ham = math.log((ham_count + 1e-9) / (total_emails + 2e-9))
    
    log_likelihood_spam = 0.0
    log_likelihood_ham = 0.0
    
    for word, count in word_dict.items(): # count 在这里实际是1，表示出现
        if word in stop_words: # 此检查在 create_word_dict 中已部分完成，但双重检查无害
            continue
        
        word_stats = train_word_dict.get(word, {"spam": 0, "ham": 0})
        # 拉普拉斯平滑
        p_word_given_spam = (word_stats["spam"] + 1) / (spam_count + 2) 
        p_word_given_ham = (word_stats["ham"] + 1) / (ham_count + 2)
        
        log_likelihood_spam += math.log(p_word_given_spam)
        log_likelihood_ham += math.log(p_word_given_ham)
    
    return 1 if (log_p_spam + log_likelihood_spam) > (log_p_ham + log_likelihood_ham) else 0


def load_train_word_dict():
    """
    加载训练好的词汇字典
    返回格式: {word: {"spam": count, "ham": count}}
    """
    file_path = "./train_word_dict" # 假设 'train_word_dict' 文件在项目根目录
    try:
        with codecs.open(file_path, "r", encoding="gbk", errors="ignore") as f: # 尝试 UTF-8
            content = f.read().strip()
            
        if content.startswith("{") and content.endswith("}"):
            # 使用 ast.literal_eval 更安全
            import ast
            train_dict_from_file = ast.literal_eval(content)
            
            # 确保内部结构是 {"spam": count, "ham": count}
            # temp 文件中的 load_train_word_dict 有一个转换逻辑，我们直接采用目标格式
            # temp中的转换是: {word: {"spam": counts[1], "ham": counts[0]}}
            # 这意味着文件中存储的可能是 [ham_count, spam_count] 列表或元组
            # 如果 train_word_dict 文件本身存储的就是 {"spam": X, "ham": Y}，则不需要转换
            # 假设 train_word_dict 文件是 {word: [ham_count, spam_count]}
            # formatted_dict = {}
            # for word, counts in train_dict_from_file.items():
            #     if isinstance(counts, (list, tuple)) and len(counts) == 2:
            #         formatted_dict[word] = {"spam": counts[1], "ham": counts[0]}
            #     elif isinstance(counts, dict) and "spam" in counts and "ham" in counts: # 如果已经是正确格式
            #         formatted_dict[word] = counts
            #     else:
            #         # print(f"Skipping malformed entry for word '{word}' in train_word_dict")
            #         continue # 跳过格式不正确的条目
            # return formatted_dict
            # 根据 temp/client/core/email_handler.py 的 load_train_word_dict, 它期望的源文件格式是 eval 后直接是 {word: [ham_count, spam_count]}
            # 然后转换为 {word: {"spam": counts[1], "ham": counts[0]}}
            # 如果您的 train_word_dict 文件内容已经是 {word: {"spam": count, "ham": count}}，则直接返回 train_dict_from_file
            # 我们先假设文件是最终格式，如果不是，需要按 temp 中的逻辑转换
            if train_dict_from_file and isinstance(next(iter(train_dict_from_file.values())), dict):
                 return train_dict_from_file # 假设文件已经是 {word: {"spam": X, "ham": Y}}
            else: # 假设文件是 {word: [ham, spam]}
                converted_dict = {
                    word: {"spam": counts[1], "ham": counts[0]}
                    for word, counts in train_dict_from_file.items()
                    if isinstance(counts, (list, tuple)) and len(counts) == 2
                }
                if not converted_dict and train_dict_from_file: # 如果转换失败但文件非空，说明格式可能不对
                    print(f"Warning: train_word_dict format might be unexpected. Loaded as is.")
                    return train_dict_from_file # fallback to raw load
                return converted_dict


        else:
            print(f"Warning: Invalid train_word_dict file format in '{file_path}'. Should be a string representation of a dictionary.")
            return {}
    except FileNotFoundError:
        print(f"Error: train_word_dict file not found at '{file_path}'. Spam filtering will not work correctly.")
        return {}
    except Exception as e:
        print(f"加载 train_word_dict 失败: {e}")
        return {}


def is_spam(email_content_text, train_word_dict, spam_count, ham_count, stop_words):
    """
    判断邮件是否为垃圾邮件
    :param email_content_text: 邮件的纯文本内容
    :param train_word_dict: 训练好的词汇字典
    :param spam_count: 垃圾邮件总数
    :param ham_count: 普通邮件总数
    :param stop_words: 停用词列表
    :return: True 是垃圾邮件，False 不是
    """
    if not email_content_text or not train_word_dict: # 如果没有内容或模型未加载，则认为不是垃圾邮件
        return False
    word_dict = create_word_dict(email_content_text, stop_words)
    if not word_dict: # 如果文本处理后没有有效词汇
        return False
    return predict_dataset(train_word_dict, spam_count, ham_count, {"word_dict": word_dict}, stop_words) == 1


class EmailHandler:
    def __init__(self, user_email, smtp_host='localhost', smtp_port=1025, pop3_host='localhost', pop3_port=1100):
        self.user_email = user_email
        self.smtp_server_info = (smtp_host, smtp_port)
        self.pop3_server_info = (pop3_host, pop3_port)

        sanitized_user_email = self._sanitize_foldername(self.user_email)
        base_user_storage_path = os.path.join('eml_storage', sanitized_user_email)

        self.inbox_storage_path = os.path.join(base_user_storage_path, 'inbox')
        self.sent_storage_path = os.path.join(base_user_storage_path, 'sent')
        # 新增：垃圾邮件存储路径
        self.spam_storage_path = os.path.join(base_user_storage_path, 'trash') # 'trash' 文件夹名
        
        os.makedirs(self.inbox_storage_path, exist_ok=True)
        os.makedirs(self.sent_storage_path, exist_ok=True)
        os.makedirs(self.spam_storage_path, exist_ok=True) # 创建 trash 文件夹

        # 加载垃圾邮件检测模型 (来自 temp)
        print("正在加载垃圾邮件分类模型...")
        self.stop_words = load_stop_word()
        self.train_word_dict = load_train_word_dict()
        # 这两个值是 temp/client/core/email_handler.py 中预设的，基于其训练集
        self.spam_count = 34429  # 训练集中垃圾邮件的总数 (来自temp)
        self.ham_count = 17268   # 训练集中正常邮件的总数 (来自temp)
        if not self.train_word_dict or not self.stop_words:
            print("警告: 垃圾邮件分类模型或停用词表加载失败，垃圾邮件分类功能可能无法正常工作。")
        else:
            print("垃圾邮件分类模型加载完毕。")

    # _sanitize_foldername 和 _sanitize_filename 方法保持不变 (它们已存在于 GemMail_Project)
    def _sanitize_foldername(self, name):
        """清理字符串，使其适合作为文件夹名。"""
        name = re.sub(r'[^\w\s-]', '', name).strip()
        name = re.sub(r'[-\s]+', '_', name)
        return name

    def _sanitize_filename(self, name):
        """清理字符串，使其适合作为文件名。"""
        name = re.sub(r'[^\w\.\s-]', '', name).strip()
        name = re.sub(r'[-\s]+', '_', name)
        return name if name else "untitled"


    def send_email(self, sender, recipient, subject, body, attachment_path=None,
                   encrypt=False, # 新增 PGP 参数
                   sender_private_key_path=None, 
                   sender_private_key_passphrase=None,
                   recipient_public_key_path=None):
        """
        发送邮件，支持附件和端到端加密签名。
        """
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = recipient
        msg['Subject'] = subject

        if encrypt and sender_private_key_path and recipient_public_key_path: # 确保密钥路径存在
            try:
                # 注意：encrypt_and_sign_email 是 EmailHandler 的一个方法
                encrypted_body_str, signature_str = self.encrypt_and_sign_email(
                    body, # 假设 body 是纯文本进行加密
                    sender_private_key_path, 
                    sender_private_key_passphrase, 
                    recipient_public_key_path
                )
                # 邮件正文为密文
                # PGP 加密的内容通常是纯文本，所以这里用 'plain'
                # 如果原始 body 是 HTML，加密前应考虑如何处理或转换为纯文本
                msg.attach(MIMEText(encrypted_body_str, 'plain', _charset='utf-8'))
                
                # 签名作为附件
                sig_part = MIMEBase('application', 'pgp-signature') # 正确的MIME类型
                sig_part.set_payload(signature_str)
                encoders.encode_base64(sig_part) # PGP签名通常是ASCII编码的，但作为附件可以Base64
                sig_part.add_header('Content-Disposition', 'attachment', filename='signature.asc')
                msg.attach(sig_part)
                print("邮件已加密并签名。")
            except Exception as e:
                print(f"邮件加密签名失败: {e}. 将以普通方式发送。")
                # 加密失败，回退到发送普通HTML邮件
                msg.attach(MIMEText(body, 'html', _charset='utf-8'))
        else:
            msg.attach(MIMEText(body, 'html', _charset='utf-8')) # GemMail_Project 原逻辑是发送HTML

        if attachment_path:
            try:
                with open(attachment_path, 'rb') as f:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(attachment_path)}"') # 引号处理文件名中的空格
                msg.attach(part)
            except Exception as e:
                print(f"添加附件失败: {e}")
        
        try:
            with smtplib.SMTP(*self.smtp_server_info) as server:
                server.sendmail(sender, [recipient], msg.as_string())
            
            safe_subject_part = self._sanitize_filename(subject[:30]) if subject else "no_subject"
            sent_email_filename = f"sent_{int(time.time())}_{safe_subject_part}.eml"
            sent_email_path = os.path.join(self.sent_storage_path, sent_email_filename) 
            with open(sent_email_path, 'wb') as f:
                f.write(msg.as_bytes())

            return True, "邮件发送成功！"
        except Exception as e:
            return False, f"发送失败: {e}"

    def fetch_inbox(self, email_address, password):
        """获取收件箱邮件列表并下载到用户专属的本地收件箱或垃圾邮件箱。(不使用UIDL)"""
        if email_address != self.user_email: # 确保 self.user_email 在 __init__ 中已定义
            return False, f"用户邮箱不匹配: 预期 {self.user_email}, 得到 {email_address}"
        
        pop_server = None 
        emails_data = []

        try:
            timeout_seconds = 30 
            # 确保 self.pop3_server_info 在 __init__ 中已定义
            #print(f"DEBUG: Attempting POP3 connection to host {self.pop3_server_info[0]} on port {self.pop3_server_info[1]} with timeout {timeout_seconds}s")
            
            if self.pop3_server_info[1] == 995: 
                pop_server = poplib.POP3_SSL(*self.pop3_server_info, timeout=timeout_seconds)
            else: 
                pop_server = poplib.POP3(*self.pop3_server_info, timeout=timeout_seconds)
            #print(f"DEBUG: POP3 object created. Waiting for server banner...")
            
            #print(f"DEBUG: Sending USER command for '{email_address}'")
            pop_server.user(email_address)
            #print(f"DEBUG: USER command sent. Waiting for server response...")
            
            #print(f"DEBUG: Sending PASS command...")
            pop_server.pass_(password)
            #print(f"DEBUG: PASS command sent. Logged in if successful.")
            
            num_messages_info = pop_server.stat()
            num_messages = num_messages_info[0]
            #print(f"DEBUG: STAT successful. Number of messages: {num_messages}")
            
            # UIDL 命令相关代码已移除
            #print(f"DEBUG: UIDL command will not be used.")

            #print(f"DEBUG: Starting to retrieve {num_messages} messages...")

            for i in range(1, num_messages + 1):
                #print(f"DEBUG: Retrieving message {i} (server index)...")
                retr_response = pop_server.retr(i)
                msg_bytes_lines = retr_response[1]
                msg_bytes = b'\n'.join(msg_bytes_lines) # <--- msg_bytes 在这里定义
                msg_obj = message_from_bytes(msg_bytes)
                #print(f"DEBUG: Message {i} retrieved.")

                unique_id_for_filename = None
                # 由于不使用 UIDL, unique_id_for_filename 将通过 Message-ID 或时间戳生成
                message_id_header = msg_obj.get('Message-ID', '').strip()
                if message_id_header:
                    unique_id_for_filename = message_id_header
                else:
                    # 如果 Message-ID 缺失，则使用邮件内容的哈希值作为唯一标识符
                    # 这样可以确保即使没有 Message-ID，相同内容的邮件也会有相同的 unique_id_for_filename
                    hasher = hashlib.md5() # 您也可以选择 hashlib.sha256() 等其他哈希算法
                    hasher.update(msg_bytes) # 使用邮件的原始字节内容进行哈希
                    unique_id_for_filename = f"content_hash_{hasher.hexdigest()}"

                # 确保 self._sanitize_filename 方法存在
                safe_filename_part = self._sanitize_filename(unique_id_for_filename)
                filename_eml = f"{safe_filename_part}.eml"

                is_mail_spam = False
                # 确保 self.train_word_dict 和 self._classify_email 存在或被正确处理
                if hasattr(self, 'train_word_dict') and self.train_word_dict:
                    try:
                        if hasattr(self, '_classify_email'):
                            is_mail_spam = self._classify_email(msg_obj)
                            #print(f"DEBUG: Mail {filename_eml} classified as {'spam' if is_mail_spam else 'ham'}")
                        else:
                            #print(f"DEBUG: _classify_email method not found. Defaulting to ham.")
                            pass
                    except Exception as e_classify:
                        #print(f"  DEBUG: Error classifying mail {filename_eml}: {e_classify}. Defaulting to ham.")
                        is_mail_spam = False
                
                # 确保 self.spam_storage_path 和 self.inbox_storage_path 在 __init__ 中已定义
                target_dir = self.spam_storage_path if is_mail_spam else self.inbox_storage_path
                file_path = os.path.join(target_dir, filename_eml)
                
                alt_target_dir = self.inbox_storage_path if is_mail_spam else self.spam_storage_path
                if os.path.exists(file_path) or os.path.exists(os.path.join(alt_target_dir, filename_eml)):
                    #print(f"DEBUG: Mail '{filename_eml}' already exists locally. Skipping download.")
                    continue 

                os.makedirs(target_dir, exist_ok=True) 
                with open(file_path, "wb") as f:
                    f.write(msg_bytes)
                #print(f"DEBUG: Mail '{filename_eml}' saved to {file_path}")
                
                emails_data.append({
                    "id": i, 
                    "from": msg_obj.get('From', 'N/A'),
                    "subject": msg_obj.get('Subject', '无主题'),
                    "date": msg_obj.get('Date', '无日期'),
                    "path": file_path,
                    "is_spam": is_mail_spam 
                })
            
            #print(f"DEBUG: All messages processed. Quitting POP3 session.")
            return True, emails_data
        
        except poplib.error_proto as e: 
            #print(f"DEBUG: POP3 protocol error: {e}\n{traceback.format_exc()}")
            return False, f"POP3 协议错误: {e}"
        except socket.timeout: 
            #print(f"DEBUG: POP3 socket timeout occurred.\n{traceback.format_exc()}")
            return False, "服务器连接超时，请检查网络或服务器状态。"
        except Exception as e: 
            #print(f"DEBUG: Unexpected error during email fetching: {e}\n{traceback.format_exc()}")
            return False, f"获取邮件时发生未知错误: {e}"
        finally:
            if pop_server:
                try:
                    pop_server.quit()
                    #print("DEBUG: POP3 session quit command sent.")
                except Exception as e_quit:
                    #print(f"DEBUG: Error during POP3 quit: {e_quit}")
                    pass
        
    def get_local_emails(self, folder_path):
        """
        从本地文件夹加载.eml文件。
        如果加载的是收件箱 (self.inbox_storage_path)，
        则会对其中的邮件进行垃圾邮件检查（如果尚未分类），并将垃圾邮件移动到 self.spam_storage_path。
        """
        emails = []
        if not os.path.exists(folder_path):
            return emails

        filenames_to_process = [f for f in os.listdir(folder_path) if f.endswith(".eml")]
        
        # 如果是收件箱，需要检查并移动垃圾邮件
        if folder_path == self.inbox_storage_path and self.train_word_dict:
            files_to_remove_from_inbox = [] # 记录需要从当前列表移除（因为被移动了）的邮件
            for filename in list(filenames_to_process): # 使用副本迭代，因为可能修改列表
                file_path_inbox = os.path.join(self.inbox_storage_path, filename)
                try:
                    with open(file_path_inbox, 'rb') as f:
                        msg = message_from_bytes(f.read())
                    
                    # 检查是否为垃圾邮件
                    # 我们只对收件箱中、且尚未被明确分类（即仍在收件箱路径下）的邮件进行此检查
                    if self._classify_email(msg):
                        # 是垃圾邮件，移动到 spam_storage_path
                        target_spam_path = os.path.join(self.spam_storage_path, filename)
                        
                        # 防止目标文件已存在导致 rename 失败
                        if os.path.exists(target_spam_path):
                            # print(f"垃圾邮件 '{filename}' 已存在于垃圾箱中，删除收件箱中的副本。")
                            os.remove(file_path_inbox)
                        else:
                            os.makedirs(self.spam_storage_path, exist_ok=True) # 确保垃圾箱目录存在
                            os.rename(file_path_inbox, target_spam_path)
                            # print(f"已将检测到的垃圾邮件 '{filename}' 从收件箱移动到垃圾箱。")
                        
                        # 标记此文件已被处理（移动），不应再作为收件箱邮件加载
                        if filename in filenames_to_process: # 从原始列表中移除
                             filenames_to_process.remove(filename)
                        # 即使移动了，我们也应该在垃圾箱视图中能看到它，所以添加到 overall emails 列表
                        # 但 get_local_emails 的目的是加载 *指定folder_path* 的邮件
                        # 所以这里不应该把移走的邮件加到当前 folder_path (inbox) 的返回结果里
                        # 它会在加载 spam_storage_path 时被获取
                        continue # 继续处理下一封收件箱邮件
                
                except FileNotFoundError: # 文件可能在迭代过程中已被移动
                    if filename in filenames_to_process:
                        filenames_to_process.remove(filename)
                    continue
                except Exception as e:
                    print(f"在收件箱中处理邮件 '{filename}' 失败: {e}")
                    # 即使处理失败，也继续尝试加载它作为普通邮件（如果它还在收件箱）

        # 加载指定 folder_path 中的剩余邮件（或非收件箱路径的所有邮件）
        for filename in filenames_to_process:
            current_file_path = os.path.join(folder_path, filename)
            if not os.path.exists(current_file_path): # 可能已被移动且未从filenames_to_process正确移除
                continue
            try:
                with open(current_file_path, 'rb') as f:
                    msg = message_from_bytes(f.read())
                
                is_spam_flag = False
                if folder_path == self.spam_storage_path:
                    is_spam_flag = True
                elif folder_path == self.inbox_storage_path and self.train_word_dict: 
                    # 对于仍在收件箱的邮件，可以再次确认分类（理论上已被上面逻辑处理，但作为保险）
                    # is_spam_flag = self._classify_email(msg) 
                    # 此处不应再分类，因为上面的逻辑已处理。如果它还在这里，说明它不是垃圾邮件。
                    is_spam_flag = False

                emails.append({
                    "from": msg.get('From', 'N/A'),
                    "to": msg.get('To', 'N/A'), # GemMail_Project 原有
                    "subject": msg.get('Subject', '无主题'),
                    "date": msg.get('Date', '无日期'),
                    "path": current_file_path,
                    "is_spam": is_spam_flag # 添加标记
                })
            except Exception as e:
                print(f"加载本地邮件 '{filename}' 从 '{folder_path}' 失败: {e}")
        
        # 按文件修改时间降序排序，最新的邮件在最前面
        return sorted(emails, key=lambda x: os.path.getmtime(x['path']), reverse=True)
    
    # ... (在 __init__ 或其他方法之后)

    def get_text_from_email(self, msg):
        """提取邮件的纯文本内容 (来自 temp)"""
        body_text = None
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                if "attachment" in content_disposition:
                    continue # 跳过附件

                if part.is_multipart(): # 如果部件本身是 multipart，则递归或进一步遍历
                    continue

                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or 'utf-8'
                    try:
                        text_part = payload.decode(charset, errors='ignore')
                        if content_type == "text/plain":
                            body_text = text_part # 优先纯文本
                            break # 找到纯文本就用它
                        elif content_type == "text/html" and not body_text: # 如果没有纯文本，再考虑HTML
                            soup = BeautifulSoup(text_part, "html.parser")
                            body_text = soup.get_text() # 从HTML中提取纯文本
                    except Exception as e:
                        # print(f"Error decoding part: {e}")
                        continue
        else: # 非 multipart 邮件
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or 'utf-8'
                try:
                    text_part = payload.decode(charset, errors='ignore')
                    if msg.get_content_type() == "text/html":
                        soup = BeautifulSoup(text_part, "html.parser")
                        body_text = soup.get_text()
                    else: # 默认视为纯文本
                        body_text = text_part
                except Exception as e:
                    # print(f"Error decoding single part message: {e}")
                    pass
        return body_text

    def preprocess_text(self, text, stop_words): # (来自 temp)
        """清洗和分词中文文本"""
        if not text:
            return ""
        text_no_non_chinese = re.sub(r"[^\u4e00-\u9fa5]", "", text)  # 去除非中文字符
        if not text_no_non_chinese: # 如果去除后为空，则返回空，避免jieba处理空字符串
            return ""
        words = jieba.cut(text_no_non_chinese)
        # 确保 self.stop_words 已加载
        current_stop_words = stop_words if stop_words is not None else []
        processed_text = " ".join([word for word in words if word and word not in current_stop_words])
        return processed_text

    def _classify_email(self, msg): # (来自 temp)
        """从邮件对象中提取正文并分类，增加异常捕获"""
        try:
            email_text_content = self.get_text_from_email(msg)
            if not email_text_content:
                # 如果无法提取文本内容，默认为非垃圾邮件
                return False 
            
            # 调用 is_spam 进行分类
            # is_spam 内部的 create_word_dict 会使用 self.stop_words
            # is_spam 内部的 predict_dataset 会使用 self.train_word_dict, self.spam_count, self.ham_count
            result = is_spam(
                email_content_text=email_text_content, 
                train_word_dict=self.train_word_dict,
                spam_count=self.spam_count,
                ham_count=self.ham_count,
                stop_words=self.stop_words 
            )
            return result
        except Exception as e:
            # print(f"警告: 邮件分类时发生错误: {e}。该邮件将默认为非垃圾邮件。")
            # 在实际部署中，您可能希望记录更详细的错误信息和相关的邮件信息
            return False # 如果分类过程中发生任何异常，默认该邮件为非垃圾邮件
    
    def encrypt_and_sign_email(self, plain_text, sender_private_key_path, sender_private_key_passphrase, recipient_public_key_path):
        """使用PGP加密并签名邮件内容。plain_text 应该是字符串。"""
        try:
            recipient_key, _ = pgpy.PGPKey.from_file(recipient_public_key_path)
        except Exception as e:
            raise ValueError(f"无法加载接收方公钥 '{recipient_public_key_path}': {e}")

        try:
            sender_key, _ = pgpy.PGPKey.from_file(sender_private_key_path)
            if sender_key.is_protected:
                if not sender_private_key_passphrase:
                    raise ValueError("发送方私钥已加密但未提供密码。")
                with sender_key.unlock(sender_private_key_passphrase) as unlocked_sender_key:
                    # 创建文本消息
                    message = pgpy.PGPMessage.new(plain_text, cleartext=True, encoding="utf-8") # 指定编码
                    # 加密
                    encrypted_message_obj = recipient_key.encrypt(message)
                    # 签名
                    signature_obj = unlocked_sender_key.sign(encrypted_message_obj) # 签名加密后的消息
            else: # 私钥未受保护
                message = pgpy.PGPMessage.new(plain_text, cleartext=True, encoding="utf-8")
                encrypted_message_obj = recipient_key.encrypt(message)
                signature_obj = sender_key.sign(encrypted_message_obj)

            return str(encrypted_message_obj), str(signature_obj) # 返回字符串形式
        except pgpy.errors.PGPDecryptionError:
             raise ValueError("发送方私钥密码错误。")
        except Exception as e:
            raise ValueError(f"加密或签名过程中出错: {e}")


    def verify_and_decrypt_email(self, encrypted_text_blob, signature_blob, 
                                 recipient_private_key_path, recipient_private_key_passphrase, 
                                 sender_public_key_path):
        """验证签名并解密PGP邮件内容。输入应为字符串。"""
        try:
            recipient_key, _ = pgpy.PGPKey.from_file(recipient_private_key_path)
            if recipient_key.is_protected:
                if not recipient_private_key_passphrase:
                    raise ValueError("接收方私钥已加密但未提供密码。")
        except Exception as e:
            raise ValueError(f"无法加载接收方私钥 '{recipient_private_key_path}': {e}")
        
        try:
            sender_key, _ = pgpy.PGPKey.from_file(sender_public_key_path)
        except Exception as e:
            raise ValueError(f"无法加载发送方公钥 '{sender_public_key_path}': {e}")

        try:
            encrypted_message = pgpy.PGPMessage.from_blob(encrypted_text_blob)
            signature = pgpy.PGPSignature.from_blob(signature_blob)

            # 验证签名
            # PGP标准是先签名后加密，或签名原始数据与加密数据一起发送。
            # temp中的逻辑是签名加密后的数据。
            if not sender_key.verify(encrypted_message, signature): # 验证的是加密消息本身和签名
                # 尝试验证原始消息（如果签名的是原始消息） - 这需要对签名方式有明确约定
                # 如果签名的是原始数据，解密后才能验证。
                # 按照temp的encrypt_and_sign_email, 签名的是加密后的数据。
                raise ValueError("签名验证失败，邮件可能被篡改或来自非预期发件人！")

            # 解密
            # 需要用解锁后的密钥进行解密
            if recipient_key.is_protected:
                with recipient_key.unlock(recipient_private_key_passphrase) as unlocked_recipient_key:
                    decrypted_message_obj = unlocked_recipient_key.decrypt(encrypted_message)
            else:
                decrypted_message_obj = recipient_key.decrypt(encrypted_message)

            if not decrypted_message_obj:
                 raise ValueError("解密失败，可能是密钥不匹配或密文损坏。")
            
            # 确保解密后的消息是字符串
            decrypted_payload = decrypted_message_obj.message
            if isinstance(decrypted_payload, bytes):
                return decrypted_payload.decode('utf-8', errors='ignore')
            return str(decrypted_payload)

        except pgpy.errors.PGPDecryptionError: # 特定的PGP解密错误
            raise ValueError("解密失败，很可能是接收方私钥密码错误或密钥不匹配。")
        except ValueError as ve: # 重新抛出已定义的 ValueError
            raise ve
        except Exception as e: # 其他PGP库或常规错误
            raise ValueError(f"解密或验证过程中发生错误: {e}")


    def decrypt_and_verify_email_from_message(self, msg, recipient_private_key_path, 
                                           recipient_private_key_passphrase, sender_public_key_path):
        """
        从 email.message.Message 对象中提取密文和签名，然后解密并验证。
        返回解密后的正文字符串。
        """
        encrypted_text_payload = None
        signature_payload = None
        
        if msg.is_multipart():
            main_text_part = None
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                filename = part.get_filename()

                if "attachment" in content_disposition and filename == "signature.asc":
                    # PGP 签名通常是 application/pgp-signature
                    if part.get_content_type() == "application/pgp-signature":
                         signature_payload = part.get_payload(decode=True) # Base64解码
                         if isinstance(signature_payload, bytes):
                            signature_payload = signature_payload.decode('ascii', errors='ignore') # 签名通常是ASCII
                # 加密的文本正文通常是 text/plain 或 application/octet-stream
                # 并且不是附件 (除非整个邮件被包装为附件)
                elif not filename and content_type == 'text/plain' and not main_text_part : # 优先取第一个非附件的 text/plain
                    payload_decoded = part.get_payload(decode=True) # Base64解码
                    charset = part.get_content_charset() or 'utf-8'
                    try:
                        main_text_part = payload_decoded.decode(charset, errors='ignore')
                    except:
                        main_text_part = payload_decoded # 如果解码失败，保留原始字节串（尽管可能性较小）
            encrypted_text_payload = main_text_part
        else: # 非 multipart 邮件，整个 payload 可能是加密文本
            payload_decoded = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or 'utf-8'
            try:
                encrypted_text_payload = payload_decoded.decode(charset, errors='ignore')
            except:
                 encrypted_text_payload = payload_decoded

        if not encrypted_text_payload:
            raise ValueError("在邮件中未找到加密的文本正文。")
        if not signature_payload:
            # 尝试从邮件头获取签名 (不标准，但作为后备)
            # PGP/MIME 标准是将签名作为 multipart/signed 的一部分或作为附件
            # print("警告: 未在附件中找到签名 'signature.asc'。解密将不进行签名验证。")
            # 如果没有签名，不能调用 verify_and_decrypt_email
            # 只能尝试解密（不推荐，因为无法验证完整性）
            raise ValueError("在邮件附件中未找到 'signature.asc' 签名文件。")

        return self.verify_and_decrypt_email(
            encrypted_text_payload, signature_payload,
            recipient_private_key_path, recipient_private_key_passphrase,
            sender_public_key_path
        )