# bili_summary/asr.py
"""阿里云百炼ASR模块"""
import json
import time
import base64
import hmac
import hashlib
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode
import httpx

from bili_summary.config import Config


class AliyunASR:
    """阿里云百炼语音识别客户端"""

    def __init__(self, config: Config):
        self.config = config
        self.access_key_id = config.aliyun.access_key_id
        self.access_key_secret = config.aliyun.access_key_secret
        self.region = config.aliyun.region
        self.model = config.aliyun.asr.model

        # 阿里云百炼API端点
        self.endpoint = f"https://dashscope.aliyuncs.com"

    def _sign_request(self, method: str, uri: str, params: Dict) -> Dict:
        """
        签名请求

        Args:
            method: HTTP方法
            uri: 请求URI
            params: 请求参数

        Returns:
            包含签名的headers
        """
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_key_secret}",
            "Date": timestamp,
        }

        return headers

    async def transcribe(self, audio_file_path: str) -> List[Dict[str, Any]]:
        """
        识别音频文件

        Args:
            audio_file_path: 音频文件路径

        Returns:
            识别结果列表，每项包含 text, begin_time, end_time
        """
        # 读取音频文件并转为base64
        with open(audio_file_path, "rb") as f:
            audio_data = base64.b64encode(f.read()).decode("utf-8")

        url = f"{self.endpoint}/api/v1/services/audio/asr/transcription"

        headers = {
            "Authorization": f"Bearer {self.access_key_id}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "input": {"audio": audio_data, "audio_format": "m4a"},
            "parameters": {"disfluency_removal": True},
        }

        async with httpx.AsyncClient(timeout=300.0) as client:
            # 提交任务
            response = await client.post(url, headers=headers, json=payload)
            result = response.json()

            if response.status_code != 200:
                raise Exception(f"ASR请求失败: {result}")

            # 获取结果
            output = result.get("output", {})
            sentences = output.get("sentences", [])

            return [
                {
                    "begin_time": s.get("begin_time", 0),
                    "end_time": s.get("end_time", 0),
                    "text": s.get("text", ""),
                }
                for s in sentences
            ]

    def format_as_subtitle(self, results: List[Dict[str, Any]]) -> str:
        """
        将ASR结果格式化为字幕文本

        Args:
            results: ASR结果列表

        Returns:
            格式化的字幕文本
        """
        return "\n".join([r["text"] for r in results])
