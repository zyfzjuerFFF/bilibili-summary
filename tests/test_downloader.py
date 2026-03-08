# tests/test_downloader.py
import pytest
from unittest.mock import Mock, patch
from bili_summary.downloader import AudioDownloader


class TestAudioDownloader:
    @pytest.fixture
    def downloader(self):
        return AudioDownloader()

    def test_init(self, downloader):
        assert downloader is not None

    @patch("yt_dlp.YoutubeDL")
    def test_extract_audio(self, mock_ydl_class, downloader):
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__ = Mock(return_value=mock_ydl)
        mock_ydl_class.return_value.__exit__ = Mock(return_value=False)
        mock_ydl.extract_info.return_value = {"title": "测试视频"}
        mock_ydl.prepare_filename.return_value = "/tmp/test.m4a"

        result = downloader.extract_audio("BV1xx411c7mD")

        mock_ydl.extract_info.assert_called_once()
        assert result == "/tmp/test.mp3"
