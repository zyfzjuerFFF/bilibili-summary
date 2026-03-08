# tests/test_asr.py
import pytest
from unittest.mock import Mock, patch
from bili_summary.asr import AliyunASR
from bili_summary.config import Config, AliyunConfig, ASRConfig


class TestAliyunASR:
    @pytest.fixture
    def config(self):
        return Config(
            aliyun=AliyunConfig(
                api_key="test-key",
                asr=ASRConfig(model="test-model"),
            )
        )

    @pytest.fixture
    def asr(self, config):
        return AliyunASR(config)

    def test_init(self, asr):
        assert asr.api_key == "test-key"

    @patch("httpx.AsyncClient.post")
    @patch("builtins.open")
    async def test_transcribe(self, mock_open, mock_post, asr):
        # Mock file read
        mock_file = Mock()
        mock_file.read.return_value = b"fake audio data"
        mock_open.return_value.__enter__ = Mock(return_value=mock_file)
        mock_open.return_value.__exit__ = Mock(return_value=False)

        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "output": {
                "sentences": [
                    {"begin_time": 0, "end_time": 5000, "text": "你好世界"}
                ]
            }
        }
        mock_post.return_value = mock_response

        result = await asr.transcribe("/tmp/test.m4a")

        assert len(result) == 1
        assert result[0]["text"] == "你好世界"
