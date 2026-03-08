"""工具函数模块"""
import re
from urllib.parse import urlparse


def extract_bv(url_or_bv: str) -> str:
    """
    从URL或BV号中提取BV号

    Args:
        url_or_bv: 视频URL或BV号

    Returns:
        BV号字符串

    Raises:
        ValueError: 无法提取BV号时
    """
    # 如果本身就是BV号格式
    if re.match(r"^BV[a-zA-Z0-9]+", url_or_bv):
        return url_or_bv

    # 从URL中提取
    pattern = r"BV[a-zA-Z0-9]+"
    match = re.search(pattern, url_or_bv)

    if match:
        return match.group(0)

    raise ValueError(f"无法从输入中提取BV号: {url_or_bv}")


def format_duration(seconds: int) -> str:
    """
    将秒数格式化为时长字符串

    Args:
        seconds: 秒数

    Returns:
        格式化的时长字符串 (MM:SS 或 HH:MM:SS)
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def validate_url(url: str) -> bool:
    """
    验证是否为支持的B站URL

    Args:
        url: 待验证的URL

    Returns:
        是否有效
    """
    try:
        parsed = urlparse(url)
        valid_hosts = ["www.bilibili.com", "bilibili.com", "b23.tv"]
        return parsed.netloc in valid_hosts or any(
            parsed.netloc.endswith(h) for h in valid_hosts
        )
    except Exception:
        return False


def parse_timestamp(ms: int) -> str:
    """
    将毫秒时间戳转换为可读格式

    Args:
        ms: 毫秒数

    Returns:
        格式化的时长字符串
    """
    return format_duration(ms // 1000)
