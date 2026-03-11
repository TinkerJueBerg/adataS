# -*- coding: utf-8 -*-
"""
测试域名IP维度请求频率限制装饰器
验证核心功能：
1. 对同一IP的请求频率限制（默认30次/分钟）
2. 超限后自动等待
3. 不同IP的请求互不影响
"""
import time
import requests
import threading
from unittest.mock import patch
from adata.common.rate_limit import (
    rate_limit_by_domain_ip,
    get_ip_from_domain,
    IP_REQUEST_COUNTER,
    DEFAULT_RATE_LIMIT
)

# -------------------------- 测试准备 --------------------------
# 模拟两个不同的测试域名（绑定固定IP，避免解析真实IP的不确定性）
TEST_DOMAIN_1 = "test-domain-1.com"
TEST_DOMAIN_2 = "test-domain-2.com"
TEST_IP_1 = "192.168.1.1"
TEST_IP_2 = "192.168.1.2"


# 重写域名解析函数，固定返回测试IP（避免依赖真实DNS）
def mock_get_ip_from_domain(domain):
    if domain == TEST_DOMAIN_1:
        return TEST_IP_1
    elif domain == TEST_DOMAIN_2:
        return TEST_IP_2
    return ""


# 装饰后的测试请求函数
@rate_limit_by_domain_ip
def test_request(method, url):
    """模拟请求函数，仅返回当前时间戳"""
    return {
        "url": url,
        "timestamp": time.time(),
        "status": "success"
    }


# -------------------------- 测试用例 --------------------------
def test_single_ip_rate_limit():
    """测试单个IP的频率限制（默认30次/分钟）"""
    print("\n=== 测试1：单个IP频率限制（30次/分钟） ===")
    # 重置计数器
    IP_REQUEST_COUNTER.clear()

    start_time = time.time()
    success_count = 0
    wait_occurred = False

    # 模拟35次请求（前30次正常，第31次应该触发等待）
    for i in range(35):
        url = f"https://{TEST_DOMAIN_1}/api/stock/{i}"
        try:
            # 记录每次请求的开始时间
            req_start = time.time()
            result = test_request("GET", url)
            req_end = time.time()

            success_count += 1
            # 检查是否触发了等待（单次请求耗时>0.1秒视为等待）
            if req_end - req_start > 0.1:
                wait_occurred = True
                print(f"  第{i + 1}次请求触发等待，耗时：{req_end - req_start:.2f}秒")

        except Exception as e:
            print(f"  第{i + 1}次请求失败：{e}")

    end_time = time.time()
    total_duration = end_time - start_time

    # 验证结果
    assert success_count == 35, f"预期35次请求成功，实际：{success_count}"
    assert wait_occurred, "预期触发等待，但未检测到"
    assert total_duration > 60, f"预期总耗时>60秒（因等待），实际：{total_duration:.2f}秒"

    print(f"  ✅ 测试通过：")
    print(f"    - 总请求数：35次")
    print(f"    - 总耗时：{total_duration:.2f}秒（包含等待时间）")
    print(f"    - 触发等待：{'是' if wait_occurred else '否'}")


def test_multi_ip_isolation():
    """测试不同IP的请求互不影响"""
    print("\n=== 测试2：不同IP请求隔离 ===")
    # 重置计数器
    IP_REQUEST_COUNTER.clear()

    # 对IP1发送30次请求（达到上限）
    for i in range(30):
        url = f"https://{TEST_DOMAIN_1}/api/stock/{i}"
        test_request("GET", url)

    # 检查IP1的计数
    ip1_count, ip1_start = IP_REQUEST_COUNTER.get(TEST_IP_1, (0, 0))
    print(f"  IP1 ({TEST_IP_1}) 请求计数：{ip1_count}")

    # 对IP2发送10次请求（应该全部正常，不受IP1影响）
    ip2_success = 0
    for i in range(10):
        url = f"https://{TEST_DOMAIN_2}/api/stock/{i}"
        result = test_request("GET", url)
        if result["status"] == "success":
            ip2_success += 1

    # 检查IP2的计数
    ip2_count, ip2_start = IP_REQUEST_COUNTER.get(TEST_IP_2, (0, 0))
    print(f"  IP2 ({TEST_IP_2}) 请求计数：{ip2_count}")

    # 验证结果
    assert ip1_count == 30, f"IP1预期计数30，实际：{ip1_count}"
    assert ip2_count == 10, f"IP2预期计数10，实际：{ip2_count}"
    assert ip2_success == 10, f"IP2预期成功10次，实际：{ip2_success}"

    print(f"  ✅ 测试通过：不同IP的请求计数相互隔离")


def test_custom_ip_rate_limit():
    """测试自定义IP频率限制"""
    print("\n=== 测试3：自定义IP频率限制 ===")
    from adata.common.rate_limit import set_ip_rate_limit

    # 重置计数器
    IP_REQUEST_COUNTER.clear()

    # 为TEST_IP_1设置自定义限制：10次/分钟
    set_ip_rate_limit(TEST_IP_1, max_requests=10, time_window=60)

    start_time = time.time()
    wait_occurred = False

    # 模拟15次请求（第11次应该触发等待）
    for i in range(15):
        url = f"https://{TEST_DOMAIN_1}/api/stock/{i}"
        req_start = time.time()
        test_request("GET", url)
        req_end = time.time()

        if req_end - req_start > 0.1:
            wait_occurred = True
            print(f"  第{i + 1}次请求触发等待（自定义限制），耗时：{req_end - req_start:.2f}秒")

    end_time = time.time()

    # 验证结果
    assert wait_occurred, "自定义限制下预期触发等待，但未检测到"
    assert end_time - start_time > 60, f"自定义限制下预期总耗时>60秒，实际：{end_time - start_time:.2f}秒"

    print(f"  ✅ 测试通过：自定义IP频率限制生效")


def test_concurrent_requests():
    """测试并发请求场景下的频率限制"""
    print("\n=== 测试4：并发请求频率限制 ===")
    # 重置计数器
    IP_REQUEST_COUNTER.clear()

    request_count = [0]
    lock = threading.Lock()

    def worker():
        """并发工作线程"""
        for i in range(10):
            url = f"https://{TEST_DOMAIN_1}/api/concurrent/{i}"
            test_request("GET", url)
            with lock:
                request_count[0] += 1

    # 创建4个线程，每个线程发送10次请求（总计40次）
    threads = []
    start_time = time.time()

    for _ in range(4):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()

    # 等待所有线程完成
    for t in threads:
        t.join()

    end_time = time.time()
    total_duration = end_time - start_time

    # 验证结果
    assert request_count[0] == 40, f"预期并发请求总数40，实际：{request_count[0]}"
    assert total_duration > 60, f"并发场景下预期总耗时>60秒，实际：{total_duration:.2f}秒"

    print(f"  ✅ 测试通过：")
    print(f"    - 并发线程数：4个")
    print(f"    - 总请求数：{request_count[0]}次")
    print(f"    - 总耗时：{total_duration:.2f}秒")


# -------------------------- 执行测试 --------------------------
if __name__ == "__main__":
    # 替换真实的域名解析函数为模拟函数
    with patch("adata.common.rate_limit.get_ip_from_domain", mock_get_ip_from_domain):
        print("开始测试域名IP维度请求频率限制...")

        try:
            test_single_ip_rate_limit()
            test_multi_ip_isolation()
            test_custom_ip_rate_limit()
            test_concurrent_requests()

            print("\n🎉 所有测试用例执行成功！")
        except AssertionError as e:
            print(f"\n❌ 测试失败：{e}")
        except Exception as e:
            print(f"\n❌ 测试异常：{e}")