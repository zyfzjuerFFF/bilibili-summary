# tests/test_bilibili.py
import json
import pytest
from unittest.mock import Mock, patch
import httpx

from bili_summary.bilibili import BilibiliAPI, SearchResultItem, VideoInfo


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

    def test_constructor_sets_sessdata_cookie(self):
        api = BilibiliAPI(sessdata="test-sessdata")
        assert api.client.cookies.get("SESSDATA") == "test-sessdata"

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
            subtitles, msg = await api.get_subtitle_list("BV1xx411c7mD", 123456)

        assert len(subtitles) == 1
        assert subtitles[0].language == "zh-CN"
        assert msg == "成功获取字幕列表"

    @pytest.mark.asyncio
    async def test_get_subtitles_requires_login_message(self, api):
        mock_response = {
            "code": 0,
            "data": {
                "need_login_subtitle": True,
                "subtitle": {"subtitles": []},
            },
        }

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value = Mock(
                json=lambda: mock_response, status_code=200
            )
            subtitles, msg = await api.get_subtitle_list("BV1xx411c7mD", 123456)

        assert subtitles == []
        assert msg == "获取原生字幕需登录，当前未登录无法获取"

    @pytest.mark.asyncio
    async def test_generate_qr_code_success(self, api):
        mock_response = {
            "code": 0,
            "data": {
                "url": "https://passport.bilibili.com/h5-app/passport/login/scan",
                "qrcode_key": "test-key",
            },
        }

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value = Mock(
                json=lambda: mock_response, status_code=200
            )
            qr_url, qr_key = await api.generate_qr_code()

        called_url = mock_get.call_args.args[0]
        assert called_url.startswith("https://passport.bilibili.com/")
        assert qr_url == mock_response["data"]["url"]
        assert qr_key == "test-key"

    @pytest.mark.asyncio
    async def test_generate_qr_code_non_json_response(self, api):
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                text="<html>blocked</html>",
                json=Mock(side_effect=json.JSONDecodeError("Expecting value", "", 0)),
            )
            with pytest.raises(Exception, match="非 JSON 响应"):
                await api.generate_qr_code()

    @pytest.mark.asyncio
    async def test_poll_qr_code_success_reads_sessdata(self, api):
        mock_response = {
            "code": 0,
            "data": {"code": 0, "message": "成功"},
        }
        api.client.cookies.set("SESSDATA", "from-client", domain=".bilibili.com", path="/")

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value = Mock(
                json=lambda: mock_response,
                status_code=200,
                cookies=httpx.Cookies(),
            )
            success, msg, sessdata = await api.poll_qr_code("test-key")

        assert success is True
        assert msg == "登录成功"
        assert sessdata == "from-client"

    @pytest.mark.asyncio
    async def test_search_videos_filters_titles_by_all_keywords(self, api):
        homepage_response = Mock(status_code=200, text="", json=Mock(return_value={}))
        search_response = Mock(
            status_code=200,
            json=Mock(return_value={
                "code": 0,
                "data": {
                    "result": [
                        {
                            "bvid": "BV1xx",
                            "title": '<em class="keyword">理想</em>i6 试驾',
                            "author": "测试UP",
                        },
                        {
                            "bvid": "BV2yy",
                            "title": "理想 L6 对比",
                            "author": "另一个UP",
                        },
                        {
                            "bvid": "BV3zz",
                            "title": "i6 城市体验",
                            "author": "第三个UP",
                        },
                    ]
                },
            }),
        )

        with patch("httpx.AsyncClient.get", side_effect=[homepage_response, search_response]) as mock_get:
            results = await api.search_videos("理想 i6", limit=1, order="pubdate")

        assert results == [SearchResultItem(bvid="BV1xx", title="理想i6 试驾", owner_name="测试UP")]
        assert mock_get.call_args_list[1].kwargs["params"]["order"] == "pubdate"
