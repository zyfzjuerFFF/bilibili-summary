# tests/test_asr.py
import pytest
from unittest.mock import AsyncMock, Mock, patch
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

    @patch("dashscope.utils.oss_utils.upload_file", return_value="oss://test-audio")
    @patch("bili_summary.asr.Transcription.fetch")
    @patch("bili_summary.asr.Transcription.async_call")
    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("httpx.AsyncClient.get")
    async def test_transcribe(
        self,
        mock_get,
        mock_sleep,
        mock_async_call,
        mock_fetch,
        mock_upload_file,
        asr,
    ):
        mock_async_call.return_value = Mock(
            status_code=200,
            output=Mock(task_id="task-123"),
        )
        mock_fetch.return_value = Mock(
            status_code=200,
            output=Mock(
                task_status="SUCCEEDED",
                results=[{"transcription_url": "https://example.com/transcript.json"}],
            ),
        )
        mock_get.return_value = Mock(
            status_code=200,
            json=Mock(return_value={
                "transcripts": [
                    {
                        "sentences": [
                            {"begin_time": 0, "end_time": 5000, "text": "你好世界"}
                        ]
                    }
                ]
            }),
        )

        result = await asr.transcribe("/tmp/test.m4a")

        mock_upload_file.assert_called_once()
        mock_async_call.assert_called_once()
        mock_fetch.assert_called_once_with("task-123")
        assert len(result) == 1
        assert result[0]["text"] == "你好世界"
