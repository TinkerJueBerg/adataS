# -*- coding: utf-8 -*-
"""
使用本地HTTP服务器测试频率限制功能
固定限制为每分钟30次，分别测试小于30次和大于30次的请求时间
"""
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from adata.common.utils.sunrequests import sun_requests


class TestHandler(SimpleHTTPRequestHandler):
    """简单的测试请求处理器"""

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'OK')

    def log_message(self, format, *args):
        pass


def start_server(port=8888):
    """启动本地HTTP服务器"""
    server = HTTPServer(('127.0.0.1', port), TestHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    return server


def test_rate_limit(request_count):
    """测试指定请求数量的耗时"""
    port = 8888
    domain = f"127.0.0.1:{port}"
    limit_count = 30

    # 重置并设置限制为30次/分钟
    sun_requests.reset_rate_limit()
    sun_requests.set_rate_limit(domain, limit_count)

    print(f"\n限制: {limit_count}次/分钟, 请求: {request_count}次")

    start_time = time.time()

    for i in range(request_count):
        try:
            url = f"http://{domain}/test"
            res = sun_requests.request("get", url, times=1)
            elapsed = time.time() - start_time
            status = "✓" if res and res.status_code == 200 else "✗"
            print(f"  请求 {i+1}: {status} 耗时: {elapsed:.2f}s")
        except Exception as e:
            print(f"  请求 {i+1}: ✗ 错误: {e}")

    total_elapsed = time.time() - start_time
    print(f"总耗时: {total_elapsed:.2f}s")

    return total_elapsed


if __name__ == "__main__":
    print("频率限制功能测试（固定限制: 30次/分钟）")
    print("="*50)

    # 启动本地服务器
    server = start_server(8888)
    print(f"本地服务器启动于 http://127.0.0.1:8888")

    try:
        # 测试1: 25次请求（小于30次限制，应该立即完成）
        print("\n【测试1】25次请求（小于30次限制）")
        elapsed1 = test_rate_limit(25)

        # 测试2: 35次请求（大于30次限制，需要等待）
        print("\n【测试2】35次请求（大于30次限制）")
        elapsed2 = test_rate_limit(35)

        # 总结
        print("\n" + "="*50)
        print("测试结果总结")
        print("="*50)
        print(f"25次请求: {elapsed1:.2f}s (预期: 立即完成)")
        print(f"35次请求: {elapsed2:.2f}s (预期: 约60s，因为5次超过限制)")

        if elapsed1 < 1 and elapsed2 >= 60:
            print("\n✓ 频率限制功能验证通过！")
        else:
            print("\n✗ 频率限制功能验证失败！")

    finally:
        server.shutdown()
        print(f"\n服务器已关闭")
