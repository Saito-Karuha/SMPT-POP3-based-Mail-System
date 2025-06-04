# 导入在 GemMail_Project/client/app.py 中定义的 Flask app 对象
# 确保 client/app.py 中有 app = Flask(__name__)
from client.app import app

if __name__ == '__main__':
    print("正在启动 GemMail Web 客户端...")
    # host='0.0.0.0' 使其可以从网络中的其他计算机访问
    # debug=True 用于开发模式，会自动重载代码并提供调试器
    # 生产环境中应使用 WSGI 服务器如 Gunicorn 或 uWSGI，并将 debug 设为 False
    # Flask 的开发服务器不适合处理大量并发请求，但对于测试是足够的
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)