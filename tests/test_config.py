# tests/test_config.py
import os
import tempfile
import pytest
from bili_summary.config import Config, ConfigManager


class TestConfig:
    def test_default_config_structure(self):
        config = Config()
        assert config.aliyun.access_key_id == ""
        assert config.aliyun.region == "cn-beijing"
        assert config.output.format == "markdown"

    def test_config_from_dict(self):
        data = {
            "aliyun": {
                "access_key_id": "test-key",
                "access_key_secret": "test-secret",
                "asr": {"model": "test-model"},
                "llm": {"model": "qwen-test"},
            }
        }
        config = Config.from_dict(data)
        assert config.aliyun.access_key_id == "test-key"
        assert config.aliyun.llm.model == "qwen-test"
