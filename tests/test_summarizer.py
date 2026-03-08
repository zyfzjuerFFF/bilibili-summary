import json
import pytest
from unittest.mock import Mock, patch
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

        assert isinstance(result, SummaryResult)
        assert result.title == "测试标题"
