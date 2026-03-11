# -*- coding: utf-8 -*-
"""
代理:https://jahttp.zhimaruanjian.com/getapi/

@desc: adata 请求工具类
@author: 1nchaos
@time:2023/3/30
@log: 封装请求次数
"""

import threading
import time
from urllib.parse import urlparse

import requests


class SunProxy(object):
    _data = {}
    _instance_lock = threading.Lock()

    def __init__(self):
        pass

    def __new__(cls, *args, **kwargs):
        if not hasattr(SunProxy, "_instance"):
            with SunProxy._instance_lock:
                if not hasattr(SunProxy, "_instance"):
                    SunProxy._instance = object.__new__(cls)

    @classmethod
    def set(cls, key, value):
        cls._data[key] = value

    @classmethod
    def get(cls, key):
        return cls._data.get(key)

    @classmethod
    def delete(cls, key):
        if key in cls._data:
            del cls._data[key]


class RateLimiter:
    """
    基于滑动窗口算法的频率限制器
    支持按域名配置不同的频率限制
    """

    _instance = None
    _instance_lock = threading.Lock()

    # 默认频率限制：每分钟30次请求
    DEFAULT_REQUESTS_PER_MINUTE = 30

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._instance_lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # 使用类属性来存储数据，确保单例模式正确工作
        if not hasattr(self, '_domain_requests'):
            # 存储每个域名的请求时间列表 {domain: [timestamp1, timestamp2, ...]}
            self._domain_requests = {}
        if not hasattr(self, '_domain_limits'):
            # 存储每个域名的频率限制配置 {domain: requests_per_minute}
            self._domain_limits = {}
        if not hasattr(self, '_lock'):
            # 锁，保证线程安全
            self._lock = threading.Lock()

    def set_rate_limit(self, domain: str, requests_per_minute: int):
        """
        设置指定域名的频率限制

        :param domain: 域名，例如 'push2his.eastmoney.com'
        :param requests_per_minute: 每分钟最大请求次数
        """
        # 字典赋值操作是线程安全的
        self._domain_limits[domain] = requests_per_minute

    def get_rate_limit(self, domain: str) -> int:
        """
        获取指定域名的频率限制，如果没有单独配置则返回默认值

        :param domain: 域名
        :return: 每分钟最大请求次数
        """
        # 读取操作不需要加锁，直接返回默认值或已有值
        return self._domain_limits.get(domain, self.DEFAULT_REQUESTS_PER_MINUTE)

    def reset_rate_limit(self, domain: str = None):
        """
        重置频率限制配置

        :param domain: 域名，如果为None则重置所有配置
        """
        if domain:
            if domain in self._domain_limits:
                del self._domain_limits[domain]
            if domain in self._domain_requests:
                del self._domain_requests[domain]
        else:
            self._domain_limits.clear()
            self._domain_requests.clear()

    def acquire(self, url: str):
        """
        获取请求许可，如果超过频率限制则等待

        :param url: 请求的URL
        """
        domain = self._extract_domain(url)
        limit = self.get_rate_limit(domain)

        with self._lock:
            now = time.time()

            # 初始化该域名的请求列表
            if domain not in self._domain_requests:
                self._domain_requests[domain] = []

            request_list = self._domain_requests[domain]

            # 清理60秒之前的请求记录（滑动窗口）
            cutoff_time = now - 60
            self._domain_requests[domain] = [t for t in request_list if t >= cutoff_time]
            request_list = self._domain_requests[domain]

            # 如果当前请求数已达限制，计算需要等待的时间
            wait_time = 0
            if len(request_list) >= limit:
                # 计算最早的那个请求还有多久超出60秒窗口
                wait_time = request_list[0] + 60 - now
                if wait_time < 0:
                    wait_time = 0

            # 记录当前请求时间
            request_list.append(now)

        # 如果需要等待，在锁外进行等待
        if wait_time > 0:
            time.sleep(wait_time)

    def _extract_domain(self, url: str) -> str:
        """
        从URL中提取域名

        :param url: URL
        :return: 域名
        """
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception:
            return "unknown"

    def get_stats(self, domain: str = None) -> dict:
        """
        获取频率限制统计信息

        :param domain: 域名，如果为None则返回所有域名的统计
        :return: 统计信息字典
        """
        with self._lock:
            now = time.time()
            cutoff_time = now - 60

            if domain:
                request_list = self._domain_requests.get(domain, [])
                # 统计有效的请求数
                valid_count = len([t for t in request_list if t >= cutoff_time])
                limit = self.get_rate_limit(domain)
                return {
                    "domain": domain,
                    "current_requests": valid_count,
                    "limit": limit,
                    "remaining": max(0, limit - valid_count),
                }
            else:
                stats = {}
                for d, request_list in self._domain_requests.items():
                    valid_count = len([t for t in request_list if t >= cutoff_time])
                    limit = self.get_rate_limit(d)
                    stats[d] = {
                        "current_requests": valid_count,
                        "limit": limit,
                        "remaining": max(0, limit - valid_count),
                    }
                return stats


class SunRequests(object):
    def __init__(self, sun_proxy: SunProxy = None) -> None:
        super().__init__()
        self.sun_proxy = sun_proxy
        self._rate_limiter = RateLimiter()

    def set_rate_limit(self, domain: str, requests_per_minute: int):
        """
        设置指定域名的请求频率限制

        :param domain: 域名，例如 'push2his.eastmoney.com' 或 'finance.pae.baidu.com'
        :param requests_per_minute: 每分钟最大请求次数，默认30次
        """
        self._rate_limiter.set_rate_limit(domain, requests_per_minute)

    def reset_rate_limit(self, domain: str = None):
        """
        重置频率限制配置

        :param domain: 域名，如果为None则重置所有配置
        """
        self._rate_limiter.reset_rate_limit(domain)

    def get_rate_limit_stats(self, domain: str = None) -> dict:
        """
        获取频率限制统计信息

        :param domain: 域名，如果为None则返回所有域名的统计
        :return: 统计信息字典
        """
        return self._rate_limiter.get_stats(domain)

    def request(
        self,
        method="get",
        url=None,
        times=3,
        retry_wait_time=1588,
        proxies=None,
        wait_time=None,
        **kwargs,
    ):
        """
        简单封装的请求，参考requests，增加循环次数和次数之间的等待时间
        :param proxies: 代理配置
        :param method: 请求方法： get；post
        :param url: url
        :param times: 次数，int
        :param retry_wait_time: 重试等待时间，毫秒
        :param wait_time: 等待时间：毫秒；表示每个请求的间隔时间，在请求之前等待sleep，主要用于防止请求太频繁的限制。
        :param kwargs: 其它 requests 参数，用法相同
        :return: res
        """
        # 1. 获取设置代理
        proxies = self.__get_proxies(proxies)
        # 2. 请求数据结果
        res = None
        for i in range(times):
            if wait_time:
                time.sleep(wait_time / 1000)

            # 频率限制检查
            if url:
                self._rate_limiter.acquire(url)

            res = requests.request(method=method, url=url, proxies=proxies, **kwargs)
            if res.status_code in (200, 404):
                return res
            time.sleep(retry_wait_time / 1000)
            if i == times - 1:
                return res
        return res

    def __get_proxies(self, proxies):
        """
        获取代理配置
        """
        if proxies is None:
            proxies = {}
        is_proxy = SunProxy.get("is_proxy")
        ip = SunProxy.get("ip")
        proxy_url = SunProxy.get("proxy_url")
        if not ip and is_proxy and proxy_url:
            ip = (
                requests.get(url=proxy_url)
                .text.replace("\r\n", "")
                .replace("\r", "")
                .replace("\n", "")
                .replace("\t", "")
            )
        if is_proxy and ip:
            if ip.startswith("http"):
                proxies = {"https": f"{ip}", "http": f"{ip}"}
            else:
                proxies = {"https": f"http://{ip}", "http": f"http://{ip}"}
        return proxies


sun_requests = SunRequests()
