# bili_summary/downloader.py
"""音频下载模块"""
import tempfile
import os
from pathlib import Path
from typing import Optional
import yt_dlp


class AudioDownloader:
    """音频下载器"""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or tempfile.gettempdir()

    def _get_ydl_opts(self) -> dict:
        """获取yt-dlp配置"""
        return {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                    "preferredquality": "192",
                }
            ],
            "outtmpl": os.path.join(self.output_dir, "%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
        }

    def extract_audio(self, bvid: str) -> str:
        """
        从B站视频提取音频

        Args:
            bvid: BV号

        Returns:
            音频文件路径
        """
        url = f"https://www.bilibili.com/video/{bvid}"
        opts = self._get_ydl_opts()

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info.get("id", bvid)

            # 获取最终音频文件路径 (yt-dlp会根据postprocessor生成最终文件名)
            audio_path = ydl.prepare_filename(info)
            # 由于postprocessor会将文件转为m4a格式，需要替换扩展名
            audio_path = audio_path.rsplit(".", 1)[0] + ".m4a"
            return audio_path

    def cleanup(self, file_path: str):
        """
        清理临时文件

        Args:
            file_path: 文件路径
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass
