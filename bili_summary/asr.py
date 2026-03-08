# bili_summary/asr.py
"""阿里云百炼ASR模块"""
from typing import List, Dict, Any
import httpx
import os
import asyncio
import dashscope
from dashscope.audio.asr import Transcription

from bili_summary.config import Config


class AliyunASR:
    """阿里云百炼语音识别客户端"""

    def __init__(self, config: Config):
        self.config = config
        self.api_key = config.aliyun.api_key
        self.region = config.aliyun.region
        self.model = config.aliyun.asr.model
        dashscope.api_key = self.api_key

    async def transcribe(self, audio_file_path: str) -> List[Dict[str, Any]]:
        """
        识别音频文件

        Args:
            audio_file_path: 音频文件路径

        Returns:
            识别结果列表，每项包含 text, begin_time, end_time
        """
        abs_path = os.path.abspath(audio_file_path)
        file_url = f"file://{abs_path}"
        # First, upload the local file to DashScope's internal OSS for processing
        import dashscope.utils.oss_utils as oss_utils
        oss_url = await asyncio.to_thread(oss_utils.upload_file, self.model, file_url, self.api_key)

        # Submit task using SDK which handles OSS uploading behind the scenes
        response = await asyncio.to_thread(
            Transcription.async_call,
            model=self.model,
            file_urls=[oss_url],
            headers={"X-DashScope-OssResourceResolve": "enable"},
            parameters={
                "disfluency_removal": True,
                "diarization_enabled": False,
            }
        )
        
        if response.status_code != 200:
            raise Exception(f"ASR请求失败: {response.message} (code: {response.code})")
            
        task_id = response.output.task_id
        
        # Poll result
        for _ in range(120): # 最多轮询4分钟
            await asyncio.sleep(2)
            res = await asyncio.to_thread(Transcription.fetch, task_id)
            if res.status_code != 200:
                raise Exception(f"查询任务失败: {res.message}")
                
            task_status = res.output.task_status
            if task_status == "SUCCEEDED":
                results = res.output.results
                if not results:
                    return []
                
                # DashScope returns results array containing 'transcription_url'
                transcription_url = results[0].get("transcription_url")
                if not transcription_url:
                    # some models might return sentences directly in 'results' instead of a URL
                    if "sentences" in res.output:
                         sentences = res.output.get("sentences", [])
                         return [
                            {
                                "begin_time": s.get("begin_time", 0),
                                "end_time": s.get("end_time", 0),
                                "text": s.get("text", ""),
                            }
                            for s in sentences
                        ]
                    else:
                        raise Exception(f"未获取到记录URL或结果: {res.output}")
                    
                async with httpx.AsyncClient(timeout=60.0) as client:
                    trans_res = await client.get(transcription_url)
                    if trans_res.status_code != 200:
                        raise Exception(f"获取识别结果失败: HTTP {trans_res.status_code}")
                    
                    data = trans_res.json()
                    transcripts = data.get("transcripts", [])
                    if not transcripts:
                        return []
                        
                    sentences = transcripts[0].get("sentences", [])
                    return [
                        {
                            "begin_time": s.get("begin_time", 0),
                            "end_time": s.get("end_time", 0),
                            "text": s.get("text", ""),
                        }
                        for s in sentences
                    ]
            elif task_status in ("FAILED", "CANCELLED"):
                raise Exception(f"任务失败: {res.output}")
                
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
