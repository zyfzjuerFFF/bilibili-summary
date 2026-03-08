"""视频内容总结模块"""
import asyncio
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

    REQUEST_RETRIES = 3

    SYSTEM_PROMPT = """你是一个专业的视频内容分析师和知识整理助手。你的目标不是泛泛概括，而是基于字幕内容产出全面、准确、结构清晰、可执行的高质量总结。

请先根据视频标题、UP主信息和字幕内容判断视频类型，再按类型调整提取重点。常见类型及要求如下：
1. 技术 / 学习 / 教程 / 课程类：
   - 必须尽可能保留关键术语、概念定义、原理解释、依赖前提、实现思路、算法或架构、工具链、配置项、参数、接口、代码逻辑、操作步骤、约束条件、适用边界、常见错误。
   - 必须提取所有出现的具体数据、版本号、性能指标、公式、阈值、案例结果和对比结论。
   - 必须说明“为什么这样做”以及“具体怎么做”。
2. 新闻 / 时事 / 观点类：
   - 重点提炼事件背景、关键事实、时间线、论点、论据、影响、争议和结论。
3. 产品 / 测评 / 消费建议类：
   - 重点提炼评测维度、优缺点、关键参数、价格或成本、适用人群和购买建议。
4. 访谈 / 播客 / 对谈类：
   - 重点提炼主题脉络、嘉宾核心观点、论证依据、分歧点和可落地建议。
5. Vlog / 故事 / 泛娱乐类：
   - 重点提炼主线内容、高光片段、人物或事件节点、情绪转折和值得记住的信息。

你必须只输出一个合法 JSON 对象，不要输出 Markdown 代码块，也不要附加解释文字。JSON 字段要求如下：
- title: 准确、具体、信息充分的总结标题，明确视频主旨或结论。
- key_points: 5-10 条高信息密度要点，按重要性排序。每条尽量包含主语、动作、结论；如果有数据、术语、步骤、因果关系，必须保留。
- highlights: 一个对象，键必须是清晰的中文标题。至少包含以下键：
  - "视频类型"
  - "主旨"
  - "可执行要点"
  再根据视频类型补充 3-6 个最重要的分节，例如：
  - 技术 / 学习类：核心概念、技术细节、逻辑步骤、数据与指标、风险与限制、适用场景
  - 新闻 / 观点类：背景、关键事实、时间线、争议点、影响
  - 产品 / 测评类：核心参数、优点、缺点、适用人群、购买建议
  每个值都应写成完整、具体、信息密度高的中文段落，避免空话和套话。
- timestamps: 3-8 个重要时间节点，格式为 [{"time": "MM:SS", "content": "内容概述"}]。如果字幕中没有可靠时间信息且无法合理提炼，则返回 []。

硬性要求：
1. 忠于字幕，不要编造字幕中没有明确出现的事实；不确定时明确写“字幕未明确说明”。
2. 优先完整性和准确性，不要为了简短而省略关键细节。
3. 对技术 / 学习类内容，必须保留关键术语、数字、逻辑链路和操作步骤。
4. 如果内容包含流程、教程或方法论，必须体现先后顺序、触发条件和预期结果。
5. “可执行要点”必须给出读者可以直接采用的做法、检查项、决策建议或实践提醒；如果确实没有，写明“暂无直接可执行动作”并说明原因。
6. 如果字幕有明显信息缺口，客观指出缺失，不要自行补全。
7. 输出必须是有效 JSON；缺失字段使用空字符串、空数组或空对象。"""

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
        user_prompt = self._build_user_prompt(subtitle_text, video_info)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = self._build_payload(user_prompt)

        result = await self._request_summary(headers, payload)

        choices = result.get("choices") or result.get("output", {}).get("choices", [])
        if not choices and "output" not in result:
            raise Exception(f"总结请求失败: {result}")

        # 解析结果
        if not choices:
            raise Exception("总结结果为空")

        content = choices[0].get("message", {}).get("content", "")

        # 解析JSON
        try:
            data = json.loads(content)
            return SummaryResult(
                title=data.get("title", "未知标题"),
                key_points=self._normalize_key_points(data.get("key_points")),
                highlights=self._normalize_highlights(data.get("highlights")),
                timestamps=self._normalize_timestamps(data.get("timestamps")),
            )
        except json.JSONDecodeError:
            # 如果JSON解析失败，返回原始内容作为标题
            return SummaryResult(
                title=content[:100],
                key_points=[],
                highlights={},
                timestamps=[],
            )

    async def _request_summary(
        self,
        headers: Dict[str, str],
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """请求总结接口，并在网络波动时自动重试。"""
        timeout = httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0)
        last_error: Optional[Exception] = None

        for attempt in range(1, self.REQUEST_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        self.endpoint,
                        headers=headers,
                        json=payload,
                    )

                try:
                    result = response.json()
                except json.JSONDecodeError as exc:
                    snippet = response.text.strip().replace("\n", " ")[:120]
                    raise Exception(
                        f"总结请求失败: 阿里云返回了非 JSON 响应 "
                        f"(HTTP {response.status_code}, 内容片段: {snippet or '<empty>'})"
                    ) from exc

                if response.status_code == 200:
                    return result

                raise Exception(f"总结请求失败: {result}")
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt == self.REQUEST_RETRIES:
                    break
                await asyncio.sleep(attempt)
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt == self.REQUEST_RETRIES:
                    break
                await asyncio.sleep(attempt)

        if isinstance(last_error, httpx.TimeoutException):
            raise Exception("总结请求超时，请稍后重试，或检查网络 / 代理设置。") from last_error
        if last_error is not None:
            raise Exception(f"总结请求失败: {last_error}") from last_error
        raise Exception("总结请求失败: 未知错误")

    def _build_payload(self, user_prompt: str) -> Dict[str, Any]:
        """构建模型请求体，并处理不同模型的兼容参数。"""
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
        }

        # Qwen3.5 系列默认开启思考模式，结构化输出时必须显式关闭。
        if self.model.startswith("qwen3.5-"):
            payload["enable_thinking"] = False
        else:
            payload["max_tokens"] = self.max_tokens

        return payload

    def _build_user_prompt(
        self,
        subtitle_text: str,
        video_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """构建用户提示词。"""
        context_lines = [
            "请基于以下视频信息和字幕内容生成结构化总结。",
            "如果视频属于技术、学习、教程或课程类，请优先覆盖关键概念、技术细节、具体数据、逻辑步骤、限制条件和实践建议。",
            "如果字幕信息不足，请明确指出缺失，不要补造事实。",
            "",
        ]

        if video_info:
            if video_info.get("title"):
                context_lines.append(f"视频标题: {video_info['title']}")
            if video_info.get("owner_name"):
                context_lines.append(f"UP主: {video_info['owner_name']}")
            if video_info.get("desc"):
                context_lines.append(f"视频简介: {video_info['desc']}")
            context_lines.append("")

        context_lines.extend(["字幕内容:", subtitle_text, "", "请输出 JSON："])
        return "\n".join(context_lines)

    def _normalize_key_points(self, key_points: Any) -> List[str]:
        """规范化核心要点字段。"""
        if not isinstance(key_points, list):
            return []
        return [str(point).strip() for point in key_points if str(point).strip()]

    def _normalize_highlights(self, highlights: Any) -> Dict[str, str]:
        """规范化关键信息字段。"""
        if not isinstance(highlights, dict):
            return {}
        return {
            str(key).strip(): str(value).strip()
            for key, value in highlights.items()
            if str(key).strip() and str(value).strip()
        }

    def _normalize_timestamps(self, timestamps: Any) -> List[Dict[str, str]]:
        """规范化时间戳字段。"""
        if not isinstance(timestamps, list):
            return []

        normalized = []
        for item in timestamps:
            if not isinstance(item, dict):
                continue
            time = str(item.get("time", "")).strip()
            content = str(item.get("content", "")).strip()
            if time or content:
                normalized.append({"time": time, "content": content})
        return normalized
