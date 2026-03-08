# tests/test_bilibili.py
import pytest
from unittest.mock import Mock, patch, AsyncMock
import httpx
from bili_summary.bilibili import BilibiliAPI, VideoInfo, SubtitleItem


class TestVideoInfo:
    def test_video_info_creation(self):
        info = VideoInfo(
            bvid="BV1xx411c7mD",
            cid=123456,
            title="测试视频",
            description="测试描述",
            duration=300,
            owner_name="测试UP",
        )
        assert info.bvid == "BV1xx411c7mD"
        assert info.title == "测试视频"


class TestBilibiliAPI:
    @pytest.fixture
    def api(self):
        return BilibiliAPI()

    @pytest.mark.asyncio
    async def test_get_video_info_success(self, api):
        mock_response = {
            "code": 0,
            "data": {
                "bvid": "BV1xx411c7mD",
                "cid": 123456,
                "title": "测试视频",
                "desc": "测试描述",
                "duration": 300,
                "owner": {"name": "测试UP"},
            },
        }

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value = Mock(
                json=lambda: mock_response, status_code=200
            )
            info = await api.get_video_info("BV1xx411c7mD")

        assert info.bvid == "BV1xx411c7mD"
        assert info.title == "测试视频"

    @pytest.mark.asyncio
    async def test_get_video_info_not_found(self, api):
        mock_response = {"code": -404, "message": "视频不存在"}

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value = Mock(
                json=lambda: mock_response, status_code=200
            )
            with pytest.raises(Exception, match="视频不存在"):
                await api.get_video_info("BVinvalid")

    @pytest.mark.asyncio
    async def test_get_subtitles_success(self, api):
        mock_response = {
            "code": 0,
            "data": {
                "subtitle": {
                    "subtitles": [
                        {
                            "id": 1,
                            "lan": "zh-CN",
                            "lan_doc": "中文（中国）",
                            "subtitle_url": "//example.com/subtitle.json",
                        }
                    ]
                }
            },
        }

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value = Mock(
                json=lambda: mock_response, status_code=200
            )
            subtitles = await api.get_subtitle_list("BV1xx411c7mD", 123456)

        assert len(subtitles) == 1
        assert subtitles[0].language == "zh-CN"
