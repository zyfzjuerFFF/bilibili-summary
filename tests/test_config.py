# tests/test_config.py
import os
import tempfile
import pytest
from bili_summary.config import Config, ConfigManager


class TestConfig:
    def test_default_config_structure(self):
        config = Config()
        assert config.aliyun.api_key == ""
        assert config.aliyun.region == "cn-beijing"
        assert config.output.format == "markdown"

    def test_config_from_dict(self):
        data = {
            "aliyun": {
                "api_key": "test-key",
                "asr": {"model": "test-model"},
                "llm": {"model": "qwen-test"},
            }
        }
        config = Config.from_dict(data)
        assert config.aliyun.api_key == "test-key"
        assert config.aliyun.llm.model == "qwen-test"

    def test_config_from_dict_legacy(self):
        """测试从旧的 access_key_id 格式迁移"""
        data = {
            "aliyun": {
                "access_key_id": "legacy-key",
                "asr": {"model": "test-model"},
            }
        }
        config = Config.from_dict(data)
        assert config.aliyun.api_key == "legacy-key"
