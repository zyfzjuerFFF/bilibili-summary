# bili_summary/bilibili.py
"""Bilibili API封装模块"""
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import httpx
import json
import html
import re


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


@dataclass
class SearchResultItem:
    """搜索结果项"""
    bvid: str
    title: str
    owner_name: str


class BilibiliAPI:
    """Bilibili API客户端"""

    BASE_URL = "https://api.bilibili.com"
    PASSPORT_URL = "https://passport.bilibili.com"

    def __init__(self, sessdata: Optional[str] = None):
        cookies = httpx.Cookies()
        if sessdata:
            cookies.set("SESSDATA", sessdata, domain=".bilibili.com", path="/")

        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0",
                "Referer": "https://www.bilibili.com/",
            },
            cookies=cookies,
            timeout=30.0,
        )

    def _parse_json_response(self, response: httpx.Response, action: str) -> Dict[str, Any]:
        """解析 JSON 响应，并在非 JSON 时给出清晰错误"""
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            snippet = response.text.strip().replace("\n", " ")[:120]
            raise Exception(
                f"{action}失败: Bilibili 返回了非 JSON 响应 "
                f"(HTTP {response.status_code}, 内容片段: {snippet or '<empty>'})"
            ) from exc

    def _clean_search_title(self, title: str) -> str:
        """清理搜索结果标题中的 HTML 高亮标签。"""
        clean = re.sub(r"<[^>]+>", "", title)
        return html.unescape(clean).strip()

    def _split_search_keywords(self, keyword: str) -> List[str]:
        """按空白拆分搜索词，得到必须全部命中的关键词。"""
        return [part.lower() for part in re.split(r"\s+", keyword.strip()) if part]

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
        data = self._parse_json_response(response, "获取视频信息")

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

    async def get_subtitle_list(self, bvid: str, cid: int) -> tuple[List[SubtitleInfo], str]:
        """
        获取视频字幕列表

        Args:
            bvid: BV号
            cid: 视频cid

        Returns:
            (字幕信息列表, 提示信息)
        """
        url = f"{self.BASE_URL}/x/player/wbi/v2"
        params = {"bvid": bvid, "cid": cid}

        response = await self.client.get(url, params=params)
        data = self._parse_json_response(response, "获取字幕列表")

        if data.get("code") != 0:
            return [], f"API请求失败: {data.get('message', '未知错误')}"
            
        need_login = data.get("data", {}).get("need_login_subtitle", False)

        subtitle_data = data.get("data", {}).get("subtitle", {})
        subtitles = subtitle_data.get("subtitles", [])
        
        msg = "成功获取字幕列表" if subtitles else "视频无字幕"
        if not subtitles and need_login:
            msg = "获取原生字幕需登录，当前未登录无法获取"

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
        ], msg

    async def download_subtitle(self, subtitle_url: str) -> List[SubtitleItem]:
        """
        下载字幕内容

        Args:
            subtitle_url: 字幕URL

        Returns:
            字幕项列表
        """
        response = await self.client.get(subtitle_url)
        data = self._parse_json_response(response, "下载字幕")

        body = data.get("body", [])
        return [
            SubtitleItem(
                from_time=item.get("from", 0),
                to_time=item.get("to", 0),
                content=item.get("content", ""),
            )
            for item in body
        ]

    async def search_videos(
        self,
        keyword: str,
        limit: int = 20,
        order: str = "totalrank",
    ) -> List[SearchResultItem]:
        """
        根据关键词搜索视频。

        Args:
            keyword: 搜索关键词
            limit: 返回数量上限
            order: 排序方式，支持 totalrank / pubdate

        Returns:
            搜索结果列表
        """
        if limit <= 0:
            return []

        required_keywords = self._split_search_keywords(keyword)
        await self.client.get("https://www.bilibili.com")

        results: List[SearchResultItem] = []
        page = 1

        while len(results) < limit:
            url = f"{self.BASE_URL}/x/web-interface/search/type"
            params = {
                "search_type": "video",
                "keyword": keyword,
                "order": order,
                "page": page,
            }

            response = await self.client.get(url, params=params)
            data = self._parse_json_response(response, "搜索视频")

            if data.get("code") != 0:
                raise Exception(f"搜索视频失败: {data.get('message', '未知错误')}")

            items = data.get("data", {}).get("result", []) or []
            if not items:
                break

            for item in items:
                bvid = item.get("bvid", "").strip()
                if not bvid:
                    continue
                title = self._clean_search_title(item.get("title", "")) or bvid
                normalized_title = title.lower()
                if required_keywords and not all(part in normalized_title for part in required_keywords):
                    continue
                results.append(
                    SearchResultItem(
                        bvid=bvid,
                        title=title,
                        owner_name=item.get("author", "").strip() or "未知UP主",
                    )
                )
                if len(results) >= limit:
                    break

            page += 1

        return results[:limit]

    async def has_official_subtitle(self, bvid: str, cid: int) -> bool:
        """
        检查是否有官方字幕

        Args:
            bvid: BV号
            cid: 视频cid

        Returns:
            是否有官方字幕
        """
        subtitles, _ = await self.get_subtitle_list(bvid, cid)
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

    async def generate_qr_code(self) -> tuple[str, str]:
        """
        生成登录二维码
        
        Returns:
            (二维码内容URL, qrcode_key)
        """
        url = f"{self.PASSPORT_URL}/x/passport-login/web/qrcode/generate"
        response = await self.client.get(url)
        data = self._parse_json_response(response, "获取二维码")
        
        if data.get("code") != 0:
            raise Exception(f"获取二维码失败: {data.get('message', '未知错误')}")
            
        return data["data"]["url"], data["data"]["qrcode_key"]

    async def poll_qr_code(self, qrcode_key: str) -> tuple[bool, str, Optional[str]]:
        """
        轮询二维码状态
        
        Args:
            qrcode_key: 二维码的key
            
        Returns:
            (是否已登录, 提示信息, SESSDATA)
        """
        url = f"{self.PASSPORT_URL}/x/passport-login/web/qrcode/poll"
        params = {"qrcode_key": qrcode_key}
        
        response = await self.client.get(url, params=params)
        data = self._parse_json_response(response, "轮询二维码")
        
        if data.get("code") != 0:
            return False, f"轮询失败: {data.get('message', '未知错误')}", None
            
        # 0：成功，86038：二维码已失效，86090：二维码已扫码未确认，86101：未扫码
        status_code = data["data"]["code"]
        message = data["data"]["message"]
        
        if status_code == 0:
            # 登录成功，提取 Cookie 中的 SESSDATA
            sessdata = response.cookies.get("SESSDATA") or self.client.cookies.get("SESSDATA")
            return True, "登录成功", sessdata
            
        return False, message, None

    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()
