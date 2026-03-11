# -*- coding: utf-8 -*-
"""
域名IP维度请求频率限制：限制对每个域名IP的请求频率（默认30次/分钟）
"""
import time
import socket
import functools
from urllib.parse import urlparse
from collections import defaultdict

# 存储IP的请求计数和时间窗口 {ip: (count, start_time)}
IP_REQUEST_COUNTER = defaultdict(lambda: (0, time.time()))
# 全局默认频率配置 (请求次数, 时间窗口秒数)
DEFAULT_RATE_LIMIT = (30, 60)
# 自定义IP频率配置（优先级高于全局）
CUSTOM_RATE_LIMIT = {}


def get_ip_from_domain(domain: str) -> str:
    """
    从域名解析出对应的IP地址（处理异常，保证鲁棒性）
    :param domain: 域名（如 eastmoney.com）
    :return: 对应的IP，解析失败返回空字符串
    """
    try:
        # 解析域名对应的IP（返回第一个IPv4地址）
        ip = socket.gethostbyname(domain)
        return ip
    except (socket.gaierror, ValueError):
        return ""


def set_ip_rate_limit(ip: str, max_requests: int, time_window: int = 60):
    """
    自定义某个IP的频率限制（优先级高于全局）
    :param ip: 目标服务器IP（如 119.29.29.29）
    :param max_requests: 时间窗口内最大请求数
    :param time_window: 时间窗口（秒），默认60秒
    """
    CUSTOM_RATE_LIMIT[ip] = (max_requests, time_window)


def rate_limit_by_domain_ip(func):
    """
    域名IP维度频率控制装饰器：包裹requests.request方法
    核心逻辑：解析请求URL的域名→转IP→限制对该IP的请求频率
    """

    @functools.wraps(func)
    def wrapper(method, url, *args, **kwargs):
        # 1. 解析URL的域名
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        if not domain:
            return func(method, url, *args, **kwargs)

        # 2. 域名转IP（核心：从域名维度转为IP维度）
        target_ip = get_ip_from_domain(domain)
        if not target_ip:
            return func(method, url, *args, **kwargs)

        # 3. 获取该IP的频率配置（自定义 > 全局）
        max_reqs, time_window = CUSTOM_RATE_LIMIT.get(target_ip, DEFAULT_RATE_LIMIT)

        # 4. 检查并更新IP请求计数器
        current_time = time.time()
        count, start_time = IP_REQUEST_COUNTER[target_ip]

        # 时间窗口重置：超过窗口时间则重新计数
        if current_time - start_time > time_window:
            IP_REQUEST_COUNTER[target_ip] = (1, current_time)
            return func(method, url, *args, **kwargs)

        # 频率超限：等待至时间窗口结束（避免被目标IP封禁）
        if count >= max_reqs:
            wait_time = time_window - (current_time - start_time)
            # 可选：打印日志，方便排查
            # print(f"IP {target_ip} 请求超限，等待 {wait_time:.1f} 秒")
            time.sleep(wait_time)
            # 重置计数器
            IP_REQUEST_COUNTER[target_ip] = (1, time.time())
            return func(method, url, *args, **kwargs)

        # 正常请求：计数+1
        IP_REQUEST_COUNTER[target_ip] = (count + 1, start_time)
        return func(method, url, *args, **kwargs)

    return wrapper