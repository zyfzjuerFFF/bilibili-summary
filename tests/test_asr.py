# tests/test_asr.py
import pytest
from unittest.mock import Mock, patch, AsyncMock
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
    @patch("httpx.AsyncClient.get")
    @patch("builtins.open")
    async def test_transcribe(self, mock_open, mock_get, mock_post, asr):
        # Mock file read
        mock_file = Mock()
        mock_file.read.return_value = b"fake audio data"
        mock_open.return_value.__enter__ = Mock(return_value=mock_file)
        mock_open.return_value.__exit__ = Mock(return_value=False)

        # Mock file upload response
        mock_upload_response = Mock()
        mock_upload_response.status_code = 200
        mock_upload_response.json.return_value = {
            "id": "file-123",
            "url": "https://dashscope.aliyuncs.com/api/v1/files/file-123/content",
        }

        # Mock ASR submit response
        mock_asr_response = Mock()
        mock_asr_response.status_code = 200
        mock_asr_response.json.return_value = {
            "output": {
                "task_id": "task-123",
                "task_status": "SUCCEEDED",
                "results": [
                    {"begin_time": 0, "end_time": 5000, "text": "你好世界"}
                ],
            }
        }

        # Mock task query response
        mock_task_response = Mock()
        mock_task_response.status_code = 200
        mock_task_response.json.return_value = {
            "output": {
                "task_status": "SUCCEEDED",
                "results": [
                    {"begin_time": 0, "end_time": 5000, "text": "你好世界"}
                ],
            }
        }

        mock_post.side_effect = [mock_upload_response, mock_asr_response]
        mock_get.return_value = mock_task_response

        result = await asr.transcribe("/tmp/test.m4a")

        assert len(result) == 1
        assert result[0]["text"] == "你好世界"
