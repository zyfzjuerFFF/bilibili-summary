"""集成测试"""
import os
import tempfile
import pytest
from unittest.mock import AsyncMock, Mock, patch

from bili_summary.cli import process_search_query, process_video
from bili_summary.config import Config, AliyunConfig, ASRConfig, LLMConfig
from bili_summary.summarizer import SummaryResult


class TestIntegration:
    @pytest.fixture
    def config(self):
        config = Config(
            aliyun=AliyunConfig(
                api_key="test-key",
                asr=ASRConfig(model="test-asr"),
                llm=LLMConfig(model="test-llm"),
            )
        )
        config.bilibili.sessdata = "test-sessdata"
        return config

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
        mock_api.get_subtitle_list = AsyncMock(return_value=([Mock(
            language="zh-CN",
            subtitle_url="http://test.com/sub.json",
            is_ai_generated=False,
        )], "成功获取字幕列表"))
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
            mock_api_class.assert_called_once_with(sessdata="test-sessdata")

            # 验证文件被写入
            assert os.path.exists(output_file)
            content = open(output_file, 'r').read()
            assert "总结标题" in content
        finally:
            if os.path.exists(output_file):
                os.remove(output_file)

    @pytest.mark.asyncio
    @patch("bili_summary.cli.summarize_video", new_callable=AsyncMock)
    @patch("bili_summary.cli.BilibiliAPI")
    async def test_search_flow_outputs_combined_markdown(
        self,
        mock_api_class,
        mock_summarize_video,
        config,
    ):
        """测试搜索模式会将多视频总结写入同一个 Markdown 文件"""
        mock_api = Mock()
        mock_api_class.return_value = mock_api
        mock_api.search_videos = AsyncMock(return_value=[
            Mock(bvid="BV1xx", title="理想 i6 试驾", owner_name="UP1"),
            Mock(bvid="BV2yy", title="理想 i6 对比", owner_name="UP2"),
        ])
        mock_api.close = AsyncMock()

        mock_summarize_video.side_effect = [
            ({
                "summary": SummaryResult(
                    title="视频一总结",
                    key_points=["要点1"],
                    highlights={"主旨": "内容1"},
                    timestamps=[],
                ),
                "video_info": {
                    "bvid": "BV1xx",
                    "title": "理想 i6 试驾",
                    "owner_name": "UP1",
                    "duration": 300,
                },
                "subtitle_source": "官方字幕",
            }, mock_api),
            ({
                "summary": SummaryResult(
                    title="视频二总结",
                    key_points=["要点2"],
                    highlights={"主旨": "内容2"},
                    timestamps=[],
                ),
                "video_info": {
                    "bvid": "BV2yy",
                    "title": "理想 i6 对比",
                    "owner_name": "UP2",
                    "duration": 420,
                },
                "subtitle_source": "ASR识别",
            }, mock_api),
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            output_file = f.name

        try:
            success = await process_search_query("理想 i6", 2, "pubdate", config, output_file)
            assert success is True

            content = open(output_file, "r", encoding="utf-8").read()
            assert "搜索结果总结：理想 i6" in content
            assert "排序方式" in content
            assert "最新发布" in content
            assert "## 1. 理想 i6 试驾" in content
            assert "## 2. 理想 i6 对比" in content
        finally:
            if os.path.exists(output_file):
                os.remove(output_file)

    @pytest.mark.asyncio
    @patch("bili_summary.cli.ConfigManager")
    @patch("bili_summary.cli.click.confirm", return_value=True)
    @patch("bili_summary.cli.login_bilibili_via_qr", new_callable=AsyncMock, return_value="fresh-sessdata")
    @patch("bili_summary.cli.BilibiliAPI")
    @patch("bili_summary.cli.Summarizer")
    async def test_login_on_demand_for_official_subtitle(
        self,
        mock_summarizer_class,
        mock_api_class,
        mock_login,
        mock_confirm,
        mock_config_manager_class,
        config,
        monkeypatch,
    ):
        """测试原生字幕需要登录时触发扫码并保存新登录态"""
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        initial_api = Mock()
        refreshed_api = Mock()
        mock_api_class.side_effect = [initial_api, refreshed_api]

        video_info = Mock(
            bvid="BV1xx",
            cid=123,
            title="测试",
            owner_name="UP",
            duration=300,
        )
        initial_api.get_video_info = AsyncMock(return_value=video_info)
        initial_api.get_subtitle_list = AsyncMock(
            return_value=([], "获取原生字幕需登录，当前未登录无法获取")
        )
        initial_api.close = AsyncMock()

        refreshed_api.get_video_info = AsyncMock(return_value=video_info)
        refreshed_api.get_subtitle_list = AsyncMock(return_value=([Mock(
            language="zh-CN",
            subtitle_url="http://test.com/sub.json",
            is_ai_generated=False,
        )], "成功获取字幕列表"))
        refreshed_api.download_subtitle = AsyncMock(return_value=[Mock(content="字幕内容")])
        refreshed_api.format_subtitle_text = Mock(return_value="字幕内容")
        refreshed_api.close = AsyncMock()

        mock_summarizer = Mock()
        mock_summarizer_class.return_value = mock_summarizer
        mock_summarizer.summarize = AsyncMock(return_value=Mock(
            title="总结标题",
            key_points=["要点1"],
            highlights={},
            timestamps=[],
        ))

        mock_config_manager = Mock()
        mock_config_manager_class.return_value = mock_config_manager

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            output_file = f.name

        try:
            config.bilibili.sessdata = ""
            await process_video("BV1xx", config, output_file, "markdown")

            mock_confirm.assert_called_once()
            mock_login.assert_awaited_once()
            mock_config_manager.save.assert_called_once_with(config)
            assert config.bilibili.sessdata == "fresh-sessdata"
            assert mock_api_class.call_args_list[0].kwargs == {"sessdata": ""}
            assert mock_api_class.call_args_list[1].kwargs == {"sessdata": "fresh-sessdata"}
            refreshed_api.get_subtitle_list.assert_awaited_once_with("BV1xx", 123)
        finally:
            if os.path.exists(output_file):
                os.remove(output_file)
