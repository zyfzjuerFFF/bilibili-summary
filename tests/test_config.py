# tests/test_config.py
from bili_summary.config import Config, ConfigManager


class TestConfig:
    def test_default_config_structure(self):
        config = Config()
        assert config.bilibili.sessdata == ""
        assert config.aliyun.api_key == ""
        assert config.aliyun.region == "cn-beijing"
        assert config.output.format == "markdown"

    def test_config_from_dict(self):
        data = {
            "bilibili": {"sessdata": "test-sessdata"},
            "aliyun": {
                "api_key": "test-key",
                "asr": {"model": "test-model"},
                "llm": {"model": "qwen-test"},
            }
        }
        config = Config.from_dict(data)
        assert config.bilibili.sessdata == "test-sessdata"
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

    def test_config_manager_save_and_load_with_bilibili(self, tmp_path):
        manager = ConfigManager()
        manager.config_dir = tmp_path / ".bili-summary"
        manager.config_file = manager.config_dir / "config.yaml"

        config = Config()
        config.bilibili.sessdata = "saved-sessdata"
        config.aliyun.api_key = "saved-api-key"

        manager.save(config)
        loaded = manager.load()

        assert loaded.bilibili.sessdata == "saved-sessdata"
        assert loaded.aliyun.api_key == "saved-api-key"
