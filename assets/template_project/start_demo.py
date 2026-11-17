# -*- coding: utf-8 -*-
"""启动 demo 被测应用（本地静态服务，默认 8765 端口）。

用法：python start_demo.py
停止：Ctrl+C
"""

import http.server
import os
import socketserver

PORT = int(os.getenv("DEMO_PORT", "8765"))
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super(Handler, self).__init__(*args, directory=ROOT, **kwargs)

    def log_message(self, fmt, *args):
        pass  # 静默请求日志


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print("demo 应用已启动: http://127.0.0.1:%d/login.html" % PORT)
        httpd.serve_forever()
