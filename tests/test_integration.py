"""集成测试"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
import tempfile
import os

from bili_summary.cli import process_video
from bili_summary.config import Config, AliyunConfig, ASRConfig, LLMConfig


class TestIntegration:
    @pytest.fixture
    def config(self):
        return Config(
            aliyun=AliyunConfig(
                access_key_id="test-key",
                access_key_secret="test-secret",
                asr=ASRConfig(model="test-asr"),
                llm=LLMConfig(model="test-llm"),
            )
        )

    @pytest.mark.asyncio
    @patch("bili_summary.cli.BilibiliAPI")
    @patch("bili_summary.cli.Summarizer")
    async def test_full_flow_with_subtitle(self, mock_summarizer_class, mock_api_class, config):
        """测试完整流程 - 有官方字幕"""
        # Mock API
        mock_api = Mock()
        mock_api_class.return_value = mock_api
        mock_api.get_video_info = AsyncMock(return_value=Mock(
            bvid="BV1xx",
            cid=123,
            title="测试",
            owner_name="UP",
            duration=300,
        ))
        mock_api.get_subtitle_list = AsyncMock(return_value=[Mock(
            language="zh-CN",
            subtitle_url="http://test.com/sub.json",
            is_ai_generated=False,
        )])
        mock_api.download_subtitle = AsyncMock(return_value=[Mock(content="字幕内容")])
        mock_api.format_subtitle_text = Mock(return_value="字幕内容")
        mock_api.close = AsyncMock()

        # Mock Summarizer
        mock_summarizer = Mock()
        mock_summarizer_class.return_value = mock_summarizer
        mock_summarizer.summarize = AsyncMock(return_value=Mock(
            title="总结标题",
            key_points=["要点1"],
            highlights={},
            timestamps=[],
        ))

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            output_file = f.name

        try:
            await process_video("BV1xx", config, output_file, "markdown")

            # 验证文件被写入
            assert os.path.exists(output_file)
            content = open(output_file, 'r').read()
            assert "总结标题" in content
        finally:
            if os.path.exists(output_file):
                os.remove(output_file)
