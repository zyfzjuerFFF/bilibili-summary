# bili_summary/asr.py
"""阿里云百炼ASR模块"""
import base64
from typing import List, Dict, Any
import httpx

from bili_summary.config import Config


class AliyunASR:
    """阿里云百炼语音识别客户端"""

    def __init__(self, config: Config):
        self.config = config
        self.api_key = config.aliyun.api_key
        self.region = config.aliyun.region
        self.model = config.aliyun.asr.model

        # 阿里云百炼API端点
        self.endpoint = "https://dashscope.aliyuncs.com"

    async def _upload_file(self, audio_file_path: str) -> str:
        """
        上传音频文件到DashScope获取文件URL

        Args:
            audio_file_path: 音频文件路径

        Returns:
            文件的URL
        """
        url = f"{self.endpoint}/api/v1/files"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        # 读取文件内容
        with open(audio_file_path, "rb") as f:
            file_content = f.read()

        # 构建multipart/form-data请求
        boundary = "----FormBoundary7MA4YWxkTrZu0gW"
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"

        # 构建请求体
        body = []
        body.append(f"--{boundary}".encode())
        body.append(b'Content-Disposition: form-data; name="purpose"')
        body.append(b"")
        body.append(b"transcription")
        body.append(f"--{boundary}".encode())
        body.append(f'Content-Disposition: form-data; name="file"; filename="{audio_file_path.split("/")[-1]}"'.encode())
        body.append(b"Content-Type: audio/m4a")
        body.append(b"")
        body.append(file_content)
        body.append(f"--{boundary}--".encode())
        body.append(b"")

        request_body = b"\r\n".join(body)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                headers=headers,
                content=request_body,
            )
            result = response.json()

        if response.status_code not in (200, 201):
            raise Exception(f"文件上传失败: {result}")

        # 获取文件ID - 从 uploaded_files 数组中获取
        data = result.get("data", {})
        uploaded_files = data.get("uploaded_files", [])

        if not uploaded_files:
            raise Exception(f"无法获取上传文件信息: {result}")

        file_id = uploaded_files[0].get("file_id")
        if not file_id:
            raise Exception(f"无法获取文件ID: {result}")

        # 构建文件URL
        return f"{self.endpoint}/api/v1/files/{file_id}/content"

    async def transcribe(self, audio_file_path: str) -> List[Dict[str, Any]]:
        """
        识别音频文件

        Args:
            audio_file_path: 音频文件路径

        Returns:
            识别结果列表，每项包含 text, begin_time, end_time
        """
        # 第一步：上传文件获取URL
        file_url = await self._upload_file(audio_file_path)

        # 第二步：使用URL调用ASR
        url = f"{self.endpoint}/api/v1/services/audio/asr/transcription"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-OssResourceResolve": "enable",  # 启用OSS资源解析
        }

        payload = {
            "model": self.model,
            "input": {
                "file_urls": [file_url],  # 使用 file_urls 数组
            },
            "parameters": {
                "disfluency_removal": True,
                "diarization_enabled": False,
            },
        }

        async with httpx.AsyncClient(timeout=300.0) as client:
            # 提交任务
            response = await client.post(url, headers=headers, json=payload)
            result = response.json()

            if response.status_code != 200:
                raise Exception(f"ASR请求失败: {result}")

            # 获取结果 - 可能需要轮询
            output = result.get("output", {})

            # 检查是否有task_id需要轮询
            task_id = output.get("task_id")
            if task_id:
                # 轮询获取结果
                return await self._poll_result(client, task_id, headers)

            # 直接返回结果
            sentences = output.get("sentences", [])
            return [
                {
                    "begin_time": s.get("begin_time", 0),
                    "end_time": s.get("end_time", 0),
                    "text": s.get("text", ""),
                }
                for s in sentences
            ]

    async def _poll_result(
        self, client: httpx.AsyncClient, task_id: str, headers: Dict
    ) -> List[Dict[str, Any]]:
        """
        轮询获取ASR结果

        Args:
            client: HTTP客户端
            task_id: 任务ID
            headers: 请求头

        Returns:
            识别结果列表
        """
        import asyncio

        url = f"{self.endpoint}/api/v1/tasks/{task_id}"

        for _ in range(60):  # 最多轮询60次，每次2秒
            response = await client.get(url, headers=headers)
            result = response.json()

            if response.status_code != 200:
                raise Exception(f"查询任务失败: {result}")

            output = result.get("output", {})
            task_status = output.get("task_status", "")

            if task_status == "SUCCEEDED":
                sentences = output.get("results", [])
                return [
                    {
                        "begin_time": s.get("begin_time", 0),
                        "end_time": s.get("end_time", 0),
                        "text": s.get("text", ""),
                    }
                    for s in sentences
                ]
            elif task_status in ("FAILED", "CANCELLED"):
                raise Exception(f"任务失败: {output}")

            # 等待2秒
            await asyncio.sleep(2)

        raise Exception("任务超时")

    def format_as_subtitle(self, results: List[Dict[str, Any]]) -> str:
        """
        将ASR结果格式化为字幕文本

        Args:
            results: ASR结果列表

        Returns:
            格式化的字幕文本
        """
        return "\n".join([r["text"] for r in results])
