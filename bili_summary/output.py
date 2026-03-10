# bili_summary/output.py
"""输出格式化模块"""
import json
from typing import Dict, Any, Optional
from datetime import datetime

from bili_summary.summarizer import SummaryResult
from bili_summary.utils import format_duration


class OutputFormatter:
    """输出格式化器"""

    def __init__(self, format_type: str = "markdown"):
        self.format_type = format_type.lower()

    def format(
        self,
        summary: SummaryResult,
        video_info: Optional[Dict[str, Any]] = None,
        subtitle_source: str = "官方字幕",
    ) -> str:
        """
        格式化输出

        Args:
            summary: 总结结果
            video_info: 视频信息
            subtitle_source: 字幕来源

        Returns:
            格式化后的字符串
        """
        if self.format_type == "json":
            return self._format_json(summary, video_info, subtitle_source)
        elif self.format_type == "text":
            return self._format_text(summary, video_info, subtitle_source)
        else:
            return self._format_markdown(summary, video_info, subtitle_source)

    def format_search_results(
        self,
        keyword: str,
        sort_label: str,
        results: list[Dict[str, Any]],
    ) -> str:
        """将搜索结果的多视频总结格式化为 Markdown。"""
        lines = [f"# 搜索结果总结：{keyword}", ""]
        lines.append(f"- **搜索词**: {keyword}")
        lines.append(f"- **排序方式**: {sort_label}")
        lines.append(f"- **视频数**: {len(results)}")
        lines.append(f"- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        if results:
            lines.extend(["## 视频列表", ""])
            for item in results:
                video_info = item.get("video_info", {})
                rank = item.get("rank", 0)
                title = video_info.get("title", "未知标题")
                bvid = video_info.get("bvid", "")
                if bvid:
                    lines.append(f"{rank}. [{title}](https://www.bilibili.com/video/{bvid})")
                else:
                    lines.append(f"{rank}. {title}")
            lines.append("")

        for item in results:
            summary = item.get("summary")
            video_info = item.get("video_info", {})
            subtitle_source = item.get("subtitle_source", "未知")
            error = item.get("error", "")
            rank = item.get("rank", 0)

            lines.append(f"## {rank}. {video_info.get('title', '未知标题')}")
            lines.append("")
            lines.append(f"- **BV号**: {video_info.get('bvid', '未知')}")
            lines.append(f"- **UP主**: {video_info.get('owner_name', '未知')}")
            lines.append(f"- **时长**: {format_duration(video_info.get('duration', 0))}")
            lines.append(f"- **字幕来源**: {subtitle_source}")
            bvid = video_info.get("bvid", "")
            if bvid:
                lines.append(f"- **原视频**: https://www.bilibili.com/video/{bvid}")
            lines.append("")

            if error:
                lines.append(f"> 处理失败: {error}")
                lines.append("")
                continue

            if summary:
                lines.append(f"### {summary.title}")
                lines.append("")

                if summary.key_points:
                    lines.append("### 核心要点")
                    lines.append("")
                    for idx, point in enumerate(summary.key_points, 1):
                        lines.append(f"{idx}. {point}")
                    lines.append("")

                if summary.highlights:
                    lines.append("### 关键信息")
                    lines.append("")
                    for key, value in summary.highlights.items():
                        lines.append(f"- **{key}**: {value}")
                    lines.append("")

                if summary.timestamps:
                    lines.append("### 时间戳导航")
                    lines.append("")
                    lines.append("| 时间 | 内容 |")
                    lines.append("|------|------|")
                    for ts in summary.timestamps:
                        lines.append(f"| {ts.get('time', '--')} | {ts.get('content', '')} |")
                    lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"

    def _format_markdown(
        self,
        summary: SummaryResult,
        video_info: Optional[Dict[str, Any]],
        subtitle_source: str,
    ) -> str:
        """Markdown格式"""
        lines = [f"# {summary.title}", ""]

        # 视频信息
        if video_info:
            lines.extend(["## 视频信息", ""])
            lines.append(f"- **UP主**: {video_info.get('owner_name', '未知')}")
            lines.append(
                f"- **时长**: {format_duration(video_info.get('duration', 0))}"
            )
            lines.append(f"- **字幕来源**: {subtitle_source}")
            lines.append("")

        # 核心要点
        if summary.key_points:
            lines.extend(["## 核心要点", ""])
            for i, point in enumerate(summary.key_points, 1):
                lines.append(f"{i}. {point}")
            lines.append("")

        # 关键信息
        if summary.highlights:
            lines.extend(["## 关键信息", ""])
            for key, value in summary.highlights.items():
                lines.append(f"- **{key}**: {value}")
            lines.append("")

        # 时间戳导航
        if summary.timestamps:
            lines.extend(["## 时间戳导航", ""])
            lines.append("| 时间 | 内容 |")
            lines.append("|------|------|")
            for ts in summary.timestamps:
                lines.append(f"| {ts.get('time', '--')} | {ts.get('content', '')} |")
            lines.append("")

        # 原视频链接
        if video_info:
            bvid = video_info.get('bvid', '')
            if bvid:
                lines.extend(["---", ""])
                lines.append(f"[查看原视频](https://www.bilibili.com/video/{bvid})")

        return "\n".join(lines)

    def _format_json(
        self,
        summary: SummaryResult,
        video_info: Optional[Dict[str, Any]],
        subtitle_source: str,
    ) -> str:
        """JSON格式"""
        data = {
            "title": summary.title,
            "video_info": video_info or {},
            "subtitle_source": subtitle_source,
            "key_points": summary.key_points,
            "highlights": summary.highlights,
            "timestamps": summary.timestamps,
            "generated_at": datetime.now().isoformat(),
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _format_text(
        self,
        summary: SummaryResult,
        video_info: Optional[Dict[str, Any]],
        subtitle_source: str,
    ) -> str:
        """纯文本格式"""
        lines = [summary.title, ""]

        if video_info:
            lines.append(f"UP主: {video_info.get('owner_name', '未知')}")
            lines.append(f"字幕来源: {subtitle_source}")
            lines.append("")

        if summary.key_points:
            lines.append("核心要点:")
            for i, point in enumerate(summary.key_points, 1):
                lines.append(f"  {i}. {point}")
            lines.append("")

        if summary.highlights:
            lines.append("关键信息:")
            for key, value in summary.highlights.items():
                lines.append(f"  {key}: {value}")

        return "\n".join(lines)
