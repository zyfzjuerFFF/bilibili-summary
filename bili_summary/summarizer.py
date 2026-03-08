"""视频内容总结模块"""
import json
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import httpx

from bili_summary.config import Config


@dataclass
class SummaryResult:
    """总结结果"""
    title: str
    key_points: List[str]
    highlights: Dict[str, str]
    timestamps: List[Dict[str, str]]


class Summarizer:
    """基于阿里云百炼的内容总结器"""

    SYSTEM_PROMPT = """你是一个专业的视频内容分析师。请根据提供的视频字幕内容，生成结构化的视频总结。

请以JSON格式输出，包含以下字段：
- title: 视频标题总结
- key_points: 核心要点列表（3-5条）
- highlights: 关键信息字典（如{"核心概念": "xxx", "重要结论": "yyy"}）
- timestamps: 重要时间节点列表（[{"time": "00:00", "content": "开场"}]）

要求：
1. 准确概括视频主要内容
2. 关键要点要有逻辑性
3. 如果有具体数据或结论要重点提取
4. 输出必须是有效的JSON格式"""

    def __init__(self, config: Config):
        self.config = config
        self.api_key = config.aliyun.api_key
        self.model = config.aliyun.llm.model
        self.max_tokens = config.aliyun.llm.max_tokens
        self.temperature = config.aliyun.llm.temperature
        self.endpoint = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

    async def summarize(
        self,
        subtitle_text: str,
        video_info: Optional[Dict[str, Any]] = None,
    ) -> SummaryResult:
        """
        对字幕内容进行总结

        Args:
            subtitle_text: 字幕文本
            video_info: 视频信息（可选）

        Returns:
            SummaryResult对象
        """
        # 构建提示词
        context = ""
        if video_info:
            context = f"视频标题: {video_info.get('title', '')}\nUP主: {video_info.get('owner_name', '')}\n\n"

        user_prompt = f"{context}字幕内容:\n\n{subtitle_text}\n\n请生成结构化总结："

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "response_format": {"type": "json_object"}
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                self.endpoint, headers=headers, json=payload
            )
            result = response.json()

        if response.status_code != 200:
            raise Exception(f"总结请求失败: {result}")

        # 解析结果
        choices = result.get("choices", [])

        if not choices:
            raise Exception("总结结果为空")

        content = choices[0].get("message", {}).get("content", "")

        # 解析JSON
        try:
            data = json.loads(content)
            return SummaryResult(
                title=data.get("title", "未知标题"),
                key_points=data.get("key_points", []),
                highlights=data.get("highlights", {}),
                timestamps=data.get("timestamps", []),
            )
        except json.JSONDecodeError:
            # 如果JSON解析失败，返回原始内容作为标题
            return SummaryResult(
                title=content[:100],
                key_points=[],
                highlights={},
                timestamps=[],
            )
