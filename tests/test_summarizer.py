import json
import pytest
from unittest.mock import Mock, patch
import httpx
from bili_summary.summarizer import Summarizer, SummaryResult
from bili_summary.config import Config, AliyunConfig, LLMConfig


class TestSummarizer:
    @pytest.fixture
    def config(self):
        return Config(
            aliyun=AliyunConfig(
                api_key="test-key",
                llm=LLMConfig(model="qwen-test", max_tokens=1000),
            )
        )

    @pytest.fixture
    def summarizer(self, config):
        return Summarizer(config)

    def test_init(self, summarizer):
        assert summarizer.model == "qwen-test"

    def test_build_user_prompt_includes_context_and_detail_requirements(self, summarizer):
        prompt = summarizer._build_user_prompt(
            "这是字幕内容",
            {
                "title": "Python 性能优化实战",
                "owner_name": "测试UP主",
                "desc": "讲解性能分析和优化步骤",
            },
        )

        assert "视频标题: Python 性能优化实战" in prompt
        assert "UP主: 测试UP主" in prompt
        assert "视频简介: 讲解性能分析和优化步骤" in prompt
        assert "如果视频属于技术、学习、教程或课程类" in prompt
        assert "逻辑步骤" in prompt

    def test_build_payload_disables_thinking_for_qwen35(self):
        config = Config(
            aliyun=AliyunConfig(
                api_key="test-key",
                llm=LLMConfig(model="qwen3.5-plus", max_tokens=4096),
            )
        )
        summarizer = Summarizer(config)

        payload = summarizer._build_payload("这是字幕内容")

        assert payload["model"] == "qwen3.5-plus"
        assert payload["enable_thinking"] is False
        assert payload["response_format"] == {"type": "json_object"}
        assert "max_tokens" not in payload

    def test_build_payload_keeps_max_tokens_for_non_qwen35(self, summarizer):
        payload = summarizer._build_payload("这是字幕内容")

        assert payload["model"] == "qwen-test"
        assert payload["max_tokens"] == 1000
        assert "enable_thinking" not in payload

    @patch("httpx.AsyncClient.post")
    async def test_summarize(self, mock_post, summarizer):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "output": {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({
                                "title": "测试标题",
                                "key_points": ["要点1", "要点2"],
                                "highlights": {"重点": "内容"},
                            })
                        }
                    }
                ]
            }
        }
        mock_post.return_value = mock_response

        result = await summarizer.summarize("这是字幕内容")

        _, kwargs = mock_post.call_args
        assert kwargs["json"]["max_tokens"] == 1000
        assert isinstance(result, SummaryResult)
        assert result.title == "测试标题"
        assert result.key_points == ["要点1", "要点2"]
        assert result.highlights == {"重点": "内容"}

    @patch("httpx.AsyncClient.post")
    async def test_summarize_qwen35_uses_json_mode_without_thinking(self, mock_post):
        config = Config(
            aliyun=AliyunConfig(
                api_key="test-key",
                llm=LLMConfig(model="qwen3.5-plus", max_tokens=4096),
            )
        )
        summarizer = Summarizer(config)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "output": {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({
                                "title": "测试标题",
                                "key_points": ["要点1"],
                                "highlights": {"主旨": "内容"},
                            })
                        }
                    }
                ]
            }
        }
        mock_post.return_value = mock_response

        await summarizer.summarize("这是字幕内容")

        _, kwargs = mock_post.call_args
        assert kwargs["json"]["enable_thinking"] is False
        assert "max_tokens" not in kwargs["json"]

    @patch("httpx.AsyncClient.post", side_effect=httpx.ReadTimeout("timed out"))
    async def test_summarize_timeout_returns_clear_error(self, mock_post, summarizer):
        with pytest.raises(Exception, match="总结请求超时"):
            await summarizer.summarize("这是字幕内容")

        assert mock_post.call_count == summarizer.REQUEST_RETRIES
