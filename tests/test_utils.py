# tests/test_utils.py
import pytest
from bili_summary.utils import extract_bv, format_duration, validate_url


class TestExtractBV:
    def test_extract_from_full_url(self):
        url = "https://www.bilibili.com/video/BV1xx411c7mD"
        assert extract_bv(url) == "BV1xx411c7mD"

    def test_extract_from_url_with_params(self):
        url = "https://www.bilibili.com/video/BV1xx411c7mD?spm_id_from=333.1007"
        assert extract_bv(url) == "BV1xx411c7mD"

    def test_extract_from_bv_only(self):
        assert extract_bv("BV1xx411c7mD") == "BV1xx411c7mD"

    def test_extract_invalid(self):
        with pytest.raises(ValueError):
            extract_bv("invalid-url")


class TestFormatDuration:
    def test_format_seconds(self):
        assert format_duration(65) == "01:05"

    def test_format_hours(self):
        assert format_duration(3665) == "01:01:05"

    def test_format_zero(self):
        assert format_duration(0) == "00:00"


class TestValidateURL:
    def test_valid_bilibili_url(self):
        assert validate_url("https://www.bilibili.com/video/BV1xx411c7mD") is True

    def test_valid_b23_url(self):
        assert validate_url("https://b23.tv/xxxxx") is True

    def test_invalid_url(self):
        assert validate_url("https://youtube.com/watch") is False
