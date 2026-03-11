# adata/common/utils/requests.py
import requests as req
from adata.common.rate_limit import rate_limit_by_domain_ip, set_ip_rate_limit

# 核心：给request方法添加IP维度的频率限制装饰器
@rate_limit_by_domain_ip
def request(method, url, headers=None, proxies=None, **kwargs):
    """你的原有请求封装方法"""
    response = req.request(
        method=method,
        url=url,
        headers=headers or {},
        proxies=proxies or {},
        timeout=kwargs.get('timeout', 10),
        **kwargs
    )
    response.raise_for_status()
    return response

# 可选：自定义某个IP的频率限制（比如对特定IP放宽/收紧限制）
# set_ip_rate_limit("119.29.29.29", 50)  # 该IP允许50次/分钟
# set_ip_rate_limit("223.5.5.5", 20)     # 该IP仅允许20次/分钟