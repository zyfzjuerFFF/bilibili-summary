# bili_summary/bilibili.py
"""Bilibili API封装模块"""
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import httpx
import json


@dataclass
class VideoInfo:
    """视频信息"""
    bvid: str
    cid: int
    title: str
    description: str
    duration: int
    owner_name: str
    pic: str = ""
    pubdate: int = 0


@dataclass
class SubtitleItem:
    """字幕项"""
    from_time: float
    to_time: float
    content: str


@dataclass
class SubtitleInfo:
    """字幕信息"""
    id: int
    language: str
    language_doc: str
    subtitle_url: str
    is_ai_generated: bool = False


class BilibiliAPI:
    """Bilibili API客户端"""

    BASE_URL = "https://api.bilibili.com"

    def __init__(self):
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0"
            },
            timeout=30.0,
        )

    async def get_video_info(self, bvid: str) -> VideoInfo:
        """
        获取视频基本信息

        Args:
            bvid: BV号

        Returns:
            VideoInfo对象
        """
        url = f"{self.BASE_URL}/x/web-interface/view"
        params = {"bvid": bvid}

        response = await self.client.get(url, params=params)
        data = response.json()

        if data.get("code") != 0:
            raise Exception(f"获取视频信息失败: {data.get('message', '未知错误')}")

        video_data = data["data"]
        return VideoInfo(
            bvid=video_data["bvid"],
            cid=video_data["cid"],
            title=video_data["title"],
            description=video_data["desc"],
            duration=video_data["duration"],
            owner_name=video_data["owner"]["name"],
            pic=video_data.get("pic", ""),
            pubdate=video_data.get("pubdate", 0),
        )

    async def get_subtitle_list(self, bvid: str, cid: int) -> List[SubtitleInfo]:
        """
        获取视频字幕列表

        Args:
            bvid: BV号
            cid: 视频cid

        Returns:
            字幕信息列表
        """
        url = f"{self.BASE_URL}/x/player/wbi/v2"
        params = {"bvid": bvid, "cid": cid}

        response = await self.client.get(url, params=params)
        data = response.json()

        if data.get("code") != 0:
            return []

        subtitle_data = data.get("data", {}).get("subtitle", {})
        subtitles = subtitle_data.get("subtitles", [])

        return [
            SubtitleInfo(
                id=s.get("id", 0),
                language=s.get("lan", ""),
                language_doc=s.get("lan_doc", ""),
                subtitle_url="https:" + s["subtitle_url"]
                if s["subtitle_url"].startswith("//")
                else s["subtitle_url"],
                is_ai_generated=s.get("type", "") == "AI",
            )
            for s in subtitles
        ]

    async def download_subtitle(self, subtitle_url: str) -> List[SubtitleItem]:
        """
        下载字幕内容

        Args:
            subtitle_url: 字幕URL

        Returns:
            字幕项列表
        """
        response = await self.client.get(subtitle_url)
        data = response.json()

        body = data.get("body", [])
        return [
            SubtitleItem(
                from_time=item.get("from", 0),
                to_time=item.get("to", 0),
                content=item.get("content", ""),
            )
            for item in body
        ]

    async def has_official_subtitle(self, bvid: str, cid: int) -> bool:
        """
        检查是否有官方字幕

        Args:
            bvid: BV号
            cid: 视频cid

        Returns:
            是否有官方字幕
        """
        subtitles = await self.get_subtitle_list(bvid, cid)
        return len(subtitles) > 0

    def format_subtitle_text(self, subtitles: List[SubtitleItem]) -> str:
        """
        将字幕项格式化为文本

        Args:
            subtitles: 字幕项列表

        Returns:
            格式化后的字幕文本
        """
        return "\n".join([item.content for item in subtitles])

    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()
