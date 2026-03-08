# bili_summary/config.py
"""配置管理模块"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import yaml


@dataclass
class ASRConfig:
    model: str = "paraformer-v1"


@dataclass
class LLMConfig:
    model: str = "qwen-plus"
    max_tokens: int = 2000
    temperature: float = 0.7


@dataclass
class BilibiliConfig:
    sessdata: str = ""  # B站 SESSDATA Cookie


@dataclass
class AliyunConfig:
    api_key: str = ""  # 阿里云百炼 API Key
    region: str = "cn-beijing"
    asr: ASRConfig = field(default_factory=ASRConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)


@dataclass
class OutputConfig:
    format: str = "markdown"  # markdown, json, text
    language: str = "zh"
    include_timestamps: bool = True


@dataclass
class Config:
    bilibili: BilibiliConfig = field(default_factory=BilibiliConfig)
    aliyun: AliyunConfig = field(default_factory=AliyunConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """从字典创建配置"""
        bilibili_data = data.get("bilibili", {})
        aliyun_data = data.get("aliyun", {})
        asr_data = aliyun_data.get("asr", {})
        llm_data = aliyun_data.get("llm", {})
        output_data = data.get("output", {})

        return cls(
            bilibili=BilibiliConfig(
                sessdata=bilibili_data.get("sessdata", "")
            ),
            aliyun=AliyunConfig(
                api_key=aliyun_data.get("api_key", aliyun_data.get("access_key_id", "")),
                region=aliyun_data.get("region", "cn-beijing"),
                asr=ASRConfig(model=asr_data.get("model", "paraformer-v1")),
                llm=LLMConfig(
                    model=llm_data.get("model", "qwen-plus"),
                    max_tokens=llm_data.get("max_tokens", 2000),
                    temperature=llm_data.get("temperature", 0.7),
                ),
            ),
            output=OutputConfig(
                format=output_data.get("format", "markdown"),
                language=output_data.get("language", "zh"),
                include_timestamps=output_data.get("include_timestamps", True),
            ),
        )


class ConfigManager:
    """配置管理器"""

    def __init__(self):
        self.config_dir = Path.home() / ".bili-summary"
        self.config_file = self.config_dir / "config.yaml"

    def exists(self) -> bool:
        """检查配置文件是否存在"""
        return self.config_file.exists()

    def load(self) -> Config:
        """加载配置"""
        if not self.exists():
            return Config()

        with open(self.config_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return Config.from_dict(data)

    def save(self, config: Config):
        """保存配置"""
        self.config_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "bilibili": {
                "sessdata": config.bilibili.sessdata,
            },
            "aliyun": {
                "api_key": config.aliyun.api_key,
                "region": config.aliyun.region,
                "asr": {"model": config.aliyun.asr.model},
                "llm": {
                    "model": config.aliyun.llm.model,
                    "max_tokens": config.aliyun.llm.max_tokens,
                    "temperature": config.aliyun.llm.temperature,
                },
            },
            "output": {
                "format": config.output.format,
                "language": config.output.language,
                "include_timestamps": config.output.include_timestamps,
            },
        }

        with open(self.config_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

    def get_template(self) -> str:
        """获取配置模板"""
        return """# Bilibili Summary 配置文件

# Bilibili 配置
bilibili:
  # Bilibili SESSDATA Cookie (用于获取需要登录才能访问的原生字幕)
  # 可以留空。遇到需要登录的原生字幕时，程序会在终端提示扫码登录并自动保存
  # 也可以手动填写浏览器 Cookies 中的 SESSDATA 值
  sessdata: ""

# 阿里云配置
# 请填写你的阿里云百炼 API Key
# 获取方式: https://bailian.console.aliyun.com/#/api-key
aliyun:
  # 阿里云百炼 API Key (Bearer Token)
  api_key: "your-api-key"
  region: "cn-beijing"

  # ASR 语音识别配置
  asr:
    model: "paraformer-v1"

  # LLM 总结模型配置
  llm:
    model: "qwen-plus"
    max_tokens: 2000
    temperature: 0.7

# 输出配置
output:
  format: "markdown"  # 可选: markdown, json, text
  language: "zh"
  include_timestamps: true
"""
