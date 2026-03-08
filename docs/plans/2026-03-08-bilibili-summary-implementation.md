# Bilibili 视频总结工具 - 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建一个CLI工具，通过URL/BV号获取B站视频字幕（官方优先，ASR兜底），并用阿里云百炼生成结构化总结。

**Architecture:** 采用分层架构：CLI层(Click) → 业务逻辑层 → 服务层(B站API/阿里云ASR/百炼LLM)。每个服务封装为独立模块，配置统一管理，错误分级处理。

**Tech Stack:** Python 3.9+, Click, Rich, httpx, yt-dlp, PyYAML

---

## 前置准备

### Task 0: 初始化项目结构

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `bili_summary/__init__.py`
- Create: `tests/__init__.py`

**Step 1: 创建项目基础文件**

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "bili-summary"
version = "0.1.0"
description = "Bilibili video subtitle extraction and summarization tool"
requires-python = ">=3.9"
dependencies = [
    "click>=8.0",
    "rich>=13.0",
    "httpx>=0.25.0",
    "pyyaml>=6.0",
    "yt-dlp>=2023.0",
]

[project.scripts]
bili-summary = "bili_summary.cli:main"
```

**Step 2: 创建.gitignore**

```
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
.pytest_cache/
.coverage
htmlcov/
.tox/
.venv
venv/
ENV/
*.log
config.yaml
.DS_Store
```

**Step 3: 安装依赖并验证**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -c "import bili_summary; print('OK')"
```

Expected: 输出 "OK"

**Step 4: Commit**

```bash
git init
git add pyproject.toml .gitignore bili_summary/__init__.py tests/__init__.py
git commit -m "chore: initialize project structure"
```

---

## 第一阶段：配置管理

### Task 1: 配置模块

**Files:**
- Create: `bili_summary/config.py`
- Create: `tests/test_config.py`

**Step 1: 编写配置测试**

```python
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
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_config.py -v
```

Expected: 2个测试都FAIL，Config类不存在

**Step 3: 实现配置模块**

```python
# bili_summary/config.py
"""配置管理模块"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import yaml


@dataclass
class ASRConfig:
    model: str = "paraformer-realtime-v1"


@dataclass
class LLMConfig:
    model: str = "qwen-plus"
    max_tokens: int = 2000
    temperature: float = 0.7


@dataclass
class AliyunConfig:
    access_key_id: str = ""
    access_key_secret: str = ""
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
    aliyun: AliyunConfig = field(default_factory=AliyunConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """从字典创建配置"""
        aliyun_data = data.get("aliyun", {})
        asr_data = aliyun_data.get("asr", {})
        llm_data = aliyun_data.get("llm", {})
        output_data = data.get("output", {})

        return cls(
            aliyun=AliyunConfig(
                access_key_id=aliyun_data.get("access_key_id", ""),
                access_key_secret=aliyun_data.get("access_key_secret", ""),
                region=aliyun_data.get("region", "cn-beijing"),
                asr=ASRConfig(model=asr_data.get("model", "paraformer-realtime-v1")),
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
            "aliyun": {
                "access_key_id": config.aliyun.access_key_id,
                "access_key_secret": config.aliyun.access_key_secret,
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
# 请填写你的阿里云百炼配置

aliyun:
  access_key_id: "your-access-key-id"
  access_key_secret: "your-access-key-secret"
  region: "cn-beijing"

  # ASR 语音识别配置
  asr:
    model: "paraformer-realtime-v1"

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
```

**Step 4: 运行测试确认通过**

```bash
pytest tests/test_config.py -v
```

Expected: 2个测试都PASS

**Step 5: Commit**

```bash
git add bili_summary/config.py tests/test_config.py
git commit -m "feat: add configuration management module"
```

---

## 第二阶段：工具函数

### Task 2: 工具函数模块

**Files:**
- Create: `bili_summary/utils.py`
- Create: `tests/test_utils.py`

**Step 1: 编写工具函数测试**

```python
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
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_utils.py -v
```

Expected: 测试FAIL，函数不存在

**Step 3: 实现工具函数**

```python
# bili_summary/utils.py
"""工具函数模块"""
import re
from urllib.parse import urlparse


def extract_bv(url_or_bv: str) -> str:
    """
    从URL或BV号中提取BV号

    Args:
        url_or_bv: 视频URL或BV号

    Returns:
        BV号字符串

    Raises:
        ValueError: 无法提取BV号时
    """
    # 如果本身就是BV号格式
    if re.match(r"^BV[a-zA-Z0-9]+", url_or_bv):
        return url_or_bv

    # 从URL中提取
    pattern = r"BV[a-zA-Z0-9]+"
    match = re.search(pattern, url_or_bv)

    if match:
        return match.group(0)

    raise ValueError(f"无法从输入中提取BV号: {url_or_bv}")


def format_duration(seconds: int) -> str:
    """
    将秒数格式化为时长字符串

    Args:
        seconds: 秒数

    Returns:
        格式化的时长字符串 (MM:SS 或 HH:MM:SS)
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def validate_url(url: str) -> bool:
    """
    验证是否为支持的B站URL

    Args:
        url: 待验证的URL

    Returns:
        是否有效
    """
    try:
        parsed = urlparse(url)
        valid_hosts = ["www.bilibili.com", "bilibili.com", "b23.tv"]
        return parsed.netloc in valid_hosts or any(
            parsed.netloc.endswith(h) for h in valid_hosts
        )
    except Exception:
        return False


def parse_timestamp(ms: int) -> str:
    """
    将毫秒时间戳转换为可读格式

    Args:
        ms: 毫秒数

    Returns:
        格式化的时长字符串
    """
    return format_duration(ms // 1000)
```

**Step 4: 运行测试确认通过**

```bash
pytest tests/test_utils.py -v
```

Expected: 所有测试PASS

**Step 5: Commit**

```bash
git add bili_summary/utils.py tests/test_utils.py
git commit -m "feat: add utility functions for URL parsing and formatting"
```

---

## 第三阶段：B站API封装

### Task 3: Bilibili API模块

**Files:**
- Create: `bili_summary/bilibili.py`
- Create: `tests/test_bilibili.py`

**Step 1: 编写API测试（Mock）**

```python
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
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_bilibili.py -v
```

Expected: 测试FAIL，BilibiliAPI类不存在

**Step 3: 实现Bilibili API模块**

```python
# bili_summary/bilibili.py
"""Bilibili API封装模块"""
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import httpx
import json


@dataclass
class VideoInfo:
    """视频信息"""
    bvid: str
    cid: int
    title: str
    description: str
    duration: int
    owner_name: str
    pic: str = ""
    pubdate: int = 0


@dataclass
class SubtitleItem:
    """字幕项"""
    from_time: float
    to_time: float
    content: str


@dataclass
class SubtitleInfo:
    """字幕信息"""
    id: int
    language: str
    language_doc: str
    subtitle_url: str
    is_ai_generated: bool = False


class BilibiliAPI:
    """Bilibili API客户端"""

    BASE_URL = "https://api.bilibili.com"

    def __init__(self):
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0"
            },
            timeout=30.0,
        )

    async def get_video_info(self, bvid: str) -> VideoInfo:
        """
        获取视频基本信息

        Args:
            bvid: BV号

        Returns:
            VideoInfo对象
        """
        url = f"{self.BASE_URL}/x/web-interface/view"
        params = {"bvid": bvid}

        response = await self.client.get(url, params=params)
        data = response.json()

        if data.get("code") != 0:
            raise Exception(f"获取视频信息失败: {data.get('message', '未知错误')}")

        video_data = data["data"]
        return VideoInfo(
            bvid=video_data["bvid"],
            cid=video_data["cid"],
            title=video_data["title"],
            description=video_data["desc"],
            duration=video_data["duration"],
            owner_name=video_data["owner"]["name"],
            pic=video_data.get("pic", ""),
            pubdate=video_data.get("pubdate", 0),
        )

    async def get_subtitle_list(self, bvid: str, cid: int) -> List[SubtitleInfo]:
        """
        获取视频字幕列表

        Args:
            bvid: BV号
            cid: 视频cid

        Returns:
            字幕信息列表
        """
        url = f"{self.BASE_URL}/x/player/wbi/v2"
        params = {"bvid": bvid, "cid": cid}

        response = await self.client.get(url, params=params)
        data = response.json()

        if data.get("code") != 0:
            return []

        subtitle_data = data.get("data", {}).get("subtitle", {})
        subtitles = subtitle_data.get("subtitles", [])

        return [
            SubtitleInfo(
                id=s.get("id", 0),
                language=s.get("lan", ""),
                language_doc=s.get("lan_doc", ""),
                subtitle_url="https:" + s["subtitle_url"]
                if s["subtitle_url"].startswith("//")
                else s["subtitle_url"],
                is_ai_generated=s.get("type", "") == "AI",
            )
            for s in subtitles
        ]

    async def download_subtitle(self, subtitle_url: str) -> List[SubtitleItem]:
        """
        下载字幕内容

        Args:
            subtitle_url: 字幕URL

        Returns:
            字幕项列表
        """
        response = await self.client.get(subtitle_url)
        data = response.json()

        body = data.get("body", [])
        return [
            SubtitleItem(
                from_time=item.get("from", 0),
                to_time=item.get("to", 0),
                content=item.get("content", ""),
            )
            for item in body
        ]

    async def has_official_subtitle(self, bvid: str, cid: int) -> bool:
        """
        检查是否有官方字幕

        Args:
            bvid: BV号
            cid: 视频cid

        Returns:
            是否有官方字幕
        """
        subtitles = await self.get_subtitle_list(bvid, cid)
        return len(subtitles) > 0

    def format_subtitle_text(self, subtitles: List[SubtitleItem]) -> str:
        """
        将字幕项格式化为文本

        Args:
            subtitles: 字幕项列表

        Returns:
            格式化后的字幕文本
        """
        return "\n".join([item.content for item in subtitles])

    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()
```

**Step 4: 运行测试确认通过**

```bash
pytest tests/test_bilibili.py -v
```

Expected: 所有测试PASS

**Step 5: Commit**

```bash
git add bili_summary/bilibili.py tests/test_bilibili.py
git commit -m "feat: add Bilibili API wrapper with video info and subtitle support"
```

---

## 第四阶段：阿里云ASR模块

### Task 4: 音频下载模块

**Files:**
- Create: `bili_summary/downloader.py`
- Create: `tests/test_downloader.py`

**Step 1: 编写下载器测试**

```python
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
        assert result == "/tmp/test.m4a"
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_downloader.py -v
```

Expected: 测试FAIL

**Step 3: 实现音频下载模块**

```python
# bili_summary/downloader.py
"""音频下载模块"""
import tempfile
import os
from pathlib import Path
from typing import Optional
import yt_dlp


class AudioDownloader:
    """音频下载器"""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or tempfile.gettempdir()

    def _get_ydl_opts(self) -> dict:
        """获取yt-dlp配置"""
        return {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                    "preferredquality": "192",
                }
            ],
            "outtmpl": os.path.join(self.output_dir, "%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
        }

    def extract_audio(self, bvid: str) -> str:
        """
        从B站视频提取音频

        Args:
            bvid: BV号

        Returns:
            音频文件路径
        """
        url = f"https://www.bilibili.com/video/{bvid}"
        opts = self._get_ydl_opts()

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info.get("id", bvid)

            # 构造输出文件路径
            audio_path = os.path.join(self.output_dir, f"{video_id}.m4a")
            return audio_path

    def cleanup(self, file_path: str):
        """
        清理临时文件

        Args:
            file_path: 文件路径
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass
```

**Step 4: 运行测试确认通过**

```bash
pytest tests/test_downloader.py -v
```

Expected: 测试PASS

**Step 5: Commit**

```bash
git add bili_summary/downloader.py tests/test_downloader.py
git commit -m "feat: add audio downloader using yt-dlp"
```

### Task 5: 阿里云ASR模块

**Files:**
- Create: `bili_summary/asr.py`
- Create: `tests/test_asr.py`

**Step 1: 编写ASR测试**

```python
# tests/test_asr.py
import pytest
from unittest.mock import Mock, patch
from bili_summary.asr import AliyunASR
from bili_summary.config import Config, AliyunConfig, ASRConfig


class TestAliyunASR:
    @pytest.fixture
    def config(self):
        return Config(
            aliyun=AliyunConfig(
                access_key_id="test-key",
                access_key_secret="test-secret",
                asr=ASRConfig(model="test-model"),
            )
        )

    @pytest.fixture
    def asr(self, config):
        return AliyunASR(config)

    def test_init(self, asr):
        assert asr.config.aliyun.access_key_id == "test-key"

    @patch("bili_summary.asr.AliyunASR._upload_file")
    @patch("bili_summary.asr.AliyunASR._submit_task")
    @patch("bili_summary.asr.AliyunASR._get_result")
    async def test_transcribe(
        self, mock_get_result, mock_submit, mock_upload, asr
    ):
        mock_upload.return_value = "https://oss.example.com/audio.m4a"
        mock_submit.return_value = "task-123"
        mock_get_result.return_value = [
            {"begin_time": 0, "end_time": 5000, "text": "你好世界"}
        ]

        result = await asr.transcribe("/tmp/test.m4a")

        assert len(result) == 1
        assert result[0]["text"] == "你好世界"
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_asr.py -v
```

**Step 3: 实现阿里云ASR模块**

```python
# bili_summary/asr.py
"""阿里云百炼ASR模块"""
import json
import time
import base64
import hmac
import hashlib
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode
import httpx

from bili_summary.config import Config


class AliyunASR:
    """阿里云百炼语音识别客户端"""

    def __init__(self, config: Config):
        self.config = config
        self.access_key_id = config.aliyun.access_key_id
        self.access_key_secret = config.aliyun.access_key_secret
        self.region = config.aliyun.region
        self.model = config.aliyun.asr.model

        # 阿里云百炼API端点
        self.endpoint = f"https://dashscope.aliyuncs.com"

    def _sign_request(self, method: str, uri: str, params: Dict) -> Dict:
        """
        签名请求

        Args:
            method: HTTP方法
            uri: 请求URI
            params: 请求参数

        Returns:
            包含签名的headers
        """
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_key_secret}",
            "Date": timestamp,
        }

        return headers

    async def transcribe(self, audio_file_path: str) -> List[Dict[str, Any]]:
        """
        识别音频文件

        Args:
            audio_file_path: 音频文件路径

        Returns:
            识别结果列表，每项包含 text, begin_time, end_time
        """
        # 读取音频文件并转为base64
        with open(audio_file_path, "rb") as f:
            audio_data = base64.b64encode(f.read()).decode("utf-8")

        url = f"{self.endpoint}/api/v1/services/audio/asr/transcription"

        headers = {
            "Authorization": f"Bearer {self.access_key_id}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "input": {"audio": audio_data, "audio_format": "m4a"},
            "parameters": {"disfluency_removal": True},
        }

        async with httpx.AsyncClient(timeout=300.0) as client:
            # 提交任务
            response = await client.post(url, headers=headers, json=payload)
            result = response.json()

            if response.status_code != 200:
                raise Exception(f"ASR请求失败: {result}")

            # 获取结果
            output = result.get("output", {})
            sentences = output.get("sentences", [])

            return [
                {
                    "begin_time": s.get("begin_time", 0),
                    "end_time": s.get("end_time", 0),
                    "text": s.get("text", ""),
                }
                for s in sentences
            ]

    def format_as_subtitle(self, results: List[Dict[str, Any]]) -> str:
        """
        将ASR结果格式化为字幕文本

        Args:
            results: ASR结果列表

        Returns:
            格式化的字幕文本
        """
        return "\n".join([r["text"] for r in results])
```

**Step 4: 运行测试确认通过**

```bash
pytest tests/test_asr.py -v
```

**Step 5: Commit**

```bash
git add bili_summary/asr.py tests/test_asr.py
git commit -m "feat: add Alibaba Cloud DashScope ASR support"
```

---

## 第五阶段：总结模块

### Task 6: 阿里云百炼LLM总结模块

**Files:**
- Create: `bili_summary/summarizer.py`
- Create: `tests/test_summarizer.py`

**Step 1: 编写总结器测试**

```python
# tests/test_summarizer.py
import pytest
from unittest.mock import Mock, patch
from bili_summary.summarizer import Summarizer, SummaryResult
from bili_summary.config import Config, AliyunConfig, LLMConfig


class TestSummarizer:
    @pytest.fixture
    def config(self):
        return Config(
            aliyun=AliyunConfig(
                access_key_id="test-key",
                access_key_secret="test-secret",
                llm=LLMConfig(model="qwen-test", max_tokens=1000),
            )
        )

    @pytest.fixture
    def summarizer(self, config):
        return Summarizer(config)

    def test_init(self, summarizer):
        assert summarizer.model == "qwen-test"

    @patch("httpx.AsyncClient.post")
    async def test_summarize(self, mock_post, summarizer):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "output": {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({
                                "title": "测试标题",
                                "key_points": ["要点1", "要点2"],
                                "highlights": {"重点": "内容"},
                            })
                        }
                    }
                ]
            }
        }
        mock_post.return_value = mock_response

        result = await summarizer.summarize("这是字幕内容")

        assert isinstance(result, SummaryResult)
        assert result.title == "测试标题"
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_summarizer.py -v
```

**Step 3: 实现总结模块**

```python
# bili_summary/summarizer.py
"""视频内容总结模块"""
import json
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import httpx

from bili_summary.config import Config


@dataclass
class SummaryResult:
    """总结结果"""
    title: str
    key_points: List[str]
    highlights: Dict[str, str]
    timestamps: List[Dict[str, str]]


class Summarizer:
    """基于阿里云百炼的内容总结器"""

    SYSTEM_PROMPT = """你是一个专业的视频内容分析师。请根据提供的视频字幕内容，生成结构化的视频总结。

请以JSON格式输出，包含以下字段：
- title: 视频标题总结
- key_points: 核心要点列表（3-5条）
- highlights: 关键信息字典（如{"核心概念": "xxx", "重要结论": "yyy"}）
- timestamps: 重要时间节点列表（[{"time": "00:00", "content": "开场"}]）

要求：
1. 准确概括视频主要内容
2. 关键要点要有逻辑性
3. 如果有具体数据或结论要重点提取
4. 输出必须是有效的JSON格式"""

    def __init__(self, config: Config):
        self.config = config
        self.api_key = config.aliyun.access_key_id
        self.model = config.aliyun.llm.model
        self.max_tokens = config.aliyun.llm.max_tokens
        self.temperature = config.aliyun.llm.temperature
        self.endpoint = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

    async def summarize(
        self,
        subtitle_text: str,
        video_info: Optional[Dict[str, Any]] = None,
    ) -> SummaryResult:
        """
        对字幕内容进行总结

        Args:
            subtitle_text: 字幕文本
            video_info: 视频信息（可选）

        Returns:
            SummaryResult对象
        """
        # 构建提示词
        context = ""
        if video_info:
            context = f"视频标题: {video_info.get('title', '')}\nUP主: {video_info.get('owner_name', '')}\n\n"

        user_prompt = f"{context}字幕内容:\n\n{subtitle_text}\n\n请生成结构化总结："

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "input": {
                "messages": [
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ]
            },
            "parameters": {
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "result_format": "message",
            },
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                self.endpoint, headers=headers, json=payload
            )
            result = response.json()

        if response.status_code != 200:
            raise Exception(f"总结请求失败: {result}")

        # 解析结果
        output = result.get("output", {})
        choices = output.get("choices", [])

        if not choices:
            raise Exception("总结结果为空")

        content = choices[0].get("message", {}).get("content", "")

        # 解析JSON
        try:
            data = json.loads(content)
            return SummaryResult(
                title=data.get("title", "未知标题"),
                key_points=data.get("key_points", []),
                highlights=data.get("highlights", {}),
                timestamps=data.get("timestamps", []),
            )
        except json.JSONDecodeError:
            # 如果JSON解析失败，返回原始内容作为标题
            return SummaryResult(
                title=content[:100],
                key_points=[],
                highlights={},
                timestamps=[],
            )
```

**Step 4: 运行测试确认通过**

```bash
pytest tests/test_summarizer.py -v
```

**Step 5: Commit**

```bash
git add bili_summary/summarizer.py tests/test_summarizer.py
git commit -m "feat: add Alibaba Cloud DashScope LLM summarization"
```

---

## 第六阶段：输出格式化

### Task 7: 输出模块

**Files:**
- Create: `bili_summary/output.py`
- Create: `tests/test_output.py`

**Step 1: 编写输出测试**

```python
# tests/test_output.py
import pytest
import json
from bili_summary.output import OutputFormatter
from bili_summary.summarizer import SummaryResult


class TestOutputFormatter:
    @pytest.fixture
    def sample_result(self):
        return SummaryResult(
            title="测试视频总结",
            key_points=["要点1", "要点2"],
            highlights={"重点": "这是重点内容"},
            timestamps=[{"time": "00:00", "content": "开场"}],
        )

    @pytest.fixture
    def sample_video_info(self):
        return {
            "bvid": "BV1xx",
            "title": "测试视频",
            "owner_name": "测试UP",
            "duration": 300,
        }

    def test_format_markdown(self, sample_result, sample_video_info):
        formatter = OutputFormatter(format_type="markdown")
        output = formatter.format(sample_result, sample_video_info)

        assert "# 测试视频总结" in output
        assert "## 视频信息" in output
        assert "要点1" in output

    def test_format_json(self, sample_result, sample_video_info):
        formatter = OutputFormatter(format_type="json")
        output = formatter.format(sample_result, sample_video_info)

        data = json.loads(output)
        assert data["title"] == "测试视频总结"
        assert data["key_points"] == ["要点1", "要点2"]

    def test_format_text(self, sample_result, sample_video_info):
        formatter = OutputFormatter(format_type="text")
        output = formatter.format(sample_result, sample_video_info)

        assert "测试视频总结" in output
        assert "要点1" in output
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_output.py -v
```

**Step 3: 实现输出模块**

```python
# bili_summary/output.py
"""输出格式化模块"""
import json
from typing import Dict, Any, Optional
from datetime import datetime

from bili_summary.summarizer import SummaryResult
from bili_summary.utils import format_duration


class OutputFormatter:
    """输出格式化器"""

    def __init__(self, format_type: str = "markdown"):
        self.format_type = format_type.lower()

    def format(
        self,
        summary: SummaryResult,
        video_info: Optional[Dict[str, Any]] = None,
        subtitle_source: str = "官方字幕",
    ) -> str:
        """
        格式化输出

        Args:
            summary: 总结结果
            video_info: 视频信息
            subtitle_source: 字幕来源

        Returns:
            格式化后的字符串
        """
        if self.format_type == "json":
            return self._format_json(summary, video_info, subtitle_source)
        elif self.format_type == "text":
            return self._format_text(summary, video_info, subtitle_source)
        else:
            return self._format_markdown(summary, video_info, subtitle_source)

    def _format_markdown(
        self,
        summary: SummaryResult,
        video_info: Optional[Dict[str, Any]],
        subtitle_source: str,
    ) -> str:
        """Markdown格式"""
        lines = [f"# {summary.title}", ""]

        # 视频信息
        if video_info:
            lines.extend(["## 视频信息", ""])
            lines.append(f"- **UP主**: {video_info.get('owner_name', '未知')}")
            lines.append(
                f"- **时长**: {format_duration(video_info.get('duration', 0))}"
            )
            lines.append(f"- **字幕来源**: {subtitle_source}")
            lines.append("")

        # 核心要点
        if summary.key_points:
            lines.extend(["## 核心要点", ""])
            for i, point in enumerate(summary.key_points, 1):
                lines.append(f"{i}. {point}")
            lines.append("")

        # 关键信息
        if summary.highlights:
            lines.extend(["## 关键信息", ""])
            for key, value in summary.highlights.items():
                lines.append(f"- **{key}**: {value}")
            lines.append("")

        # 时间戳导航
        if summary.timestamps:
            lines.extend(["## 时间戳导航", ""])
            lines.append("| 时间 | 内容 |")
            lines.append("|------|------|")
            for ts in summary.timestamps:
                lines.append(f"| {ts.get('time', '--')} | {ts.get('content', '')} |")
            lines.append("")

        # 原视频链接
        if video_info:
            bvid = video_info.get('bvid', '')
            if bvid:
                lines.extend(["---", ""])
                lines.append(f"[查看原视频](https://www.bilibili.com/video/{bvid})")

        return "\n".join(lines)

    def _format_json(
        self,
        summary: SummaryResult,
        video_info: Optional[Dict[str, Any]],
        subtitle_source: str,
    ) -> str:
        """JSON格式"""
        data = {
            "title": summary.title,
            "video_info": video_info or {},
            "subtitle_source": subtitle_source,
            "summary": {
                "key_points": summary.key_points,
                "highlights": summary.highlights,
                "timestamps": summary.timestamps,
            },
            "generated_at": datetime.now().isoformat(),
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _format_text(
        self,
        summary: SummaryResult,
        video_info: Optional[Dict[str, Any]],
        subtitle_source: str,
    ) -> str:
        """纯文本格式"""
        lines = [summary.title, ""]

        if video_info:
            lines.append(f"UP主: {video_info.get('owner_name', '未知')}")
            lines.append(f"字幕来源: {subtitle_source}")
            lines.append("")

        if summary.key_points:
            lines.append("核心要点:")
            for i, point in enumerate(summary.key_points, 1):
                lines.append(f"  {i}. {point}")
            lines.append("")

        if summary.highlights:
            lines.append("关键信息:")
            for key, value in summary.highlights.items():
                lines.append(f"  {key}: {value}")

        return "\n".join(lines)
```

**Step 4: 运行测试确认通过**

```bash
pytest tests/test_output.py -v
```

**Step 5: Commit**

```bash
git add bili_summary/output.py tests/test_output.py
git commit -m "feat: add output formatting with markdown/json/text support"
```

---

## 第七阶段：CLI主入口

### Task 8: CLI模块

**Files:**
- Create: `bili_summary/cli.py`
- Modify: `pyproject.toml`（添加rich依赖）

**Step 1: 更新pyproject.toml添加rich**

```toml
# pyproject.toml 添加 dev 依赖
[project.optional-dependencies]
dev = ["pytest>=7.0", "pytest-asyncio>=0.21.0"]
```

**Step 2: 编写CLI代码**

```python
# bili_summary/cli.py
"""命令行入口"""
import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.text import Text

from bili_summary.config import ConfigManager, Config
from bili_summary.bilibili import BilibiliAPI
from bili_summary.asr import AliyunASR
from bili_summary.downloader import AudioDownloader
from bili_summary.summarizer import Summarizer
from bili_summary.output import OutputFormatter
from bili_summary.utils import extract_bv, validate_url

console = Console()


def print_error(message: str):
    """打印错误信息"""
    console.print(f"[bold red]错误:[/bold red] {message}")


def print_success(message: str):
    """打印成功信息"""
    console.print(f"[bold green]✓[/bold green] {message}")


def print_info(message: str):
    """打印信息"""
    console.print(f"[blue]ℹ[/blue] {message}")


async def process_video(
    url_or_bv: str,
    config: Config,
    output_file: Optional[str],
    output_format: str,
):
    """处理单个视频"""
    api = BilibiliAPI()

    try:
        # 提取BV号
        try:
            bvid = extract_bv(url_or_bv)
            print_info(f"提取到BV号: {bvid}")
        except ValueError as e:
            print_error(f"无法识别BV号: {e}")
            return

        # 获取视频信息
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("获取视频信息...", total=None)
            video_info = await api.get_video_info(bvid)
            progress.update(task, completed=True)

        print_success(f"视频标题: {video_info.title}")
        print_info(f"UP主: {video_info.owner_name}")

        # 获取字幕
        subtitle_text = ""
        subtitle_source = ""

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # 尝试官方字幕
            task = progress.add_task("获取官方字幕...", total=None)
            subtitles = await api.get_subtitle_list(bvid, video_info.cid)

            if subtitles:
                # 优先使用中文或第一个字幕
                zh_subs = [s for s in subtitles if "zh" in s.language.lower()]
                selected = zh_subs[0] if zh_subs else subtitles[0]

                subtitle_items = await api.download_subtitle(selected.subtitle_url)
                subtitle_text = api.format_subtitle_text(subtitle_items)
                subtitle_source = "官方字幕" + (
                    "(AI生成)" if selected.is_ai_generated else ""
                )
                progress.update(task, description=f"获取到官方字幕 ({len(subtitle_items)} 句)")
            else:
                progress.update(task, description="无官方字幕，准备使用ASR...")

                # 使用ASR
                if not config.aliyun.access_key_id:
                    print_error("未配置阿里云API密钥，无法使用ASR")
                    return

                downloader = AudioDownloader()
                asr = AliyunASR(config)

                try:
                    progress.update(task, description="下载音频...")
                    audio_path = await asyncio.to_thread(downloader.extract_audio, bvid)

                    progress.update(task, description="识别音频...")
                    asr_result = await asr.transcribe(audio_path)
                    subtitle_text = asr.format_as_subtitle(asr_result)
                    subtitle_source = "ASR识别"

                    # 清理临时文件
                    downloader.cleanup(audio_path)

                except Exception as e:
                    print_error(f"ASR识别失败: {e}")
                    subtitle_source = "无字幕"

        if not subtitle_text.strip():
            print_error("未能获取到任何字幕内容")
            return

        print_success(f"字幕来源: {subtitle_source}")
        print_info(f"字幕长度: {len(subtitle_text)} 字符")

        # 生成总结
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("生成总结...", total=None)
            summarizer = Summarizer(config)
            summary = await summarizer.summarize(
                subtitle_text,
                {
                    "bvid": video_info.bvid,
                    "title": video_info.title,
                    "owner_name": video_info.owner_name,
                    "duration": video_info.duration,
                },
            )
            progress.update(task, completed=True)

        # 格式化输出
        formatter = OutputFormatter(output_format)
        output = formatter.format(
            summary,
            {
                "bvid": video_info.bvid,
                "title": video_info.title,
                "owner_name": video_info.owner_name,
                "duration": video_info.duration,
            },
            subtitle_source,
        )

        # 输出结果
        if output_file:
            Path(output_file).write_text(output, encoding="utf-8")
            print_success(f"总结已保存到: {output_file}")
        else:
            console.print()
            console.print(Panel(output, title="视频总结", border_style="green"))

    except Exception as e:
        print_error(f"处理失败: {e}")
        raise
    finally:
        await api.close()


@click.command()
@click.argument("url_or_bv")
@click.option(
    "-o",
    "--output",
    help="输出文件路径",
    type=click.Path(),
)
@click.option(
    "-f",
    "--format",
    "output_format",
    default="markdown",
    type=click.Choice(["markdown", "json", "text"]),
    help="输出格式",
)
@click.option(
    "--configure",
    is_flag=True,
    help="交互式配置",
)
def main(url_or_bv: str, output: Optional[str], output_format: str, configure: bool):
    """
    Bilibili 视频总结工具

    示例:
        bili-summary BV1xx411c7mD
        bili-summary https://www.bilibili.com/video/BV1xx411c7mD
        bili-summary BV1xx411c7mD -o summary.md
        bili-summary BV1xx411c7mD --format json
    """
    config_manager = ConfigManager()

    # 配置模式
    if configure:
        console.print(Panel("配置阿里云百炼", border_style="blue"))

        access_key = click.prompt("Access Key ID", hide_input=False)
        access_secret = click.prompt("Access Key Secret", hide_input=True)
        region = click.prompt("Region", default="cn-beijing")

        config = Config()
        config.aliyun.access_key_id = access_key
        config.aliyun.access_key_secret = access_secret
        config.aliyun.region = region

        config_manager.save(config)
        print_success("配置已保存到 ~/.bili-summary/config.yaml")
        return

    # 检查配置
    if not config_manager.exists():
        print_error("未找到配置文件，请先运行: bili-summary --configure")
        sys.exit(1)

    config = config_manager.load()

    if not config.aliyun.access_key_id:
        print_error("阿里云 Access Key 未配置")
        sys.exit(1)

    # 处理视频
    asyncio.run(process_video(url_or_bv, config, output, output_format))


if __name__ == "__main__":
    main()
```

**Step 3: 安装并测试CLI**

```bash
pip install -e ".[dev]"
bili-summary --help
```

Expected: 显示帮助信息

**Step 4: Commit**

```bash
git add bili_summary/cli.py pyproject.toml
git commit -m "feat: add CLI interface with rich output and progress indicators"
```

---

## 第八阶段：集成测试

### Task 9: 端到端测试

**Files:**
- Create: `tests/test_integration.py`

**Step 1: 编写集成测试**

```python
# tests/test_integration.py
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
```

**Step 2: 运行集成测试**

```bash
pytest tests/test_integration.py -v
```

Expected: 测试PASS

**Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration tests for full workflow"
```

---

## 第九阶段：完善与文档

### Task 10: README和示例配置

**Files:**
- Create: `README.md`
- Create: `config.example.yaml`

**Step 1: 编写README**

```markdown
# Bilibili Summary

Bilibili 视频字幕爬取与AI总结工具

## 功能特性

- 🔍 支持URL或BV号输入
- 📝 优先获取官方字幕，无字幕自动使用阿里云ASR
- 🤖 使用阿里云百炼大模型生成结构化总结
- 📄 支持 Markdown / JSON / 纯文本 输出
- ⚡ 异步处理，带进度指示

## 安装

```bash
pip install -e .
```

## 配置

首次使用需要配置阿里云百炼API密钥：

```bash
bili-summary --configure
```

或手动创建 `~/.bili-summary/config.yaml`：

```yaml
aliyun:
  access_key_id: "your-access-key"
  access_key_secret: "your-secret"
  region: "cn-beijing"
  asr:
    model: "paraformer-realtime-v1"
  llm:
    model: "qwen-plus"
    max_tokens: 2000
    temperature: 0.7

output:
  format: "markdown"
  include_timestamps: true
```

## 使用方法

```bash
# 基本使用
bili-summary BV1xx411c7mD

# 使用完整URL
bili-summary https://www.bilibili.com/video/BV1xx411c7mD

# 输出到文件
bili-summary BV1xx411c7mD -o summary.md

# JSON格式输出
bili-summary BV1xx411c7mD --format json
```

## 输出示例

```markdown
# 视频标题总结

## 视频信息
- **UP主**: xxx
- **时长**: 15:30
- **字幕来源**: 官方字幕

## 核心要点
1. 要点一...
2. 要点二...

## 时间戳导航
| 时间 | 内容 |
|------|------|
| 00:00 | 开场 |
```

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest
```
```

**Step 2: 创建示例配置**

```yaml
# config.example.yaml
aliyun:
  access_key_id: "your-access-key-id"
  access_key_secret: "your-access-key-secret"
  region: "cn-beijing"

  asr:
    model: "paraformer-realtime-v1"

  llm:
    model: "qwen-plus"
    max_tokens: 2000
    temperature: 0.7

output:
  format: "markdown"
  language: "zh"
  include_timestamps: true
```

**Step 3: Commit**

```bash
git add README.md config.example.yaml
git commit -m "docs: add README and example configuration"
```

---

## 执行计划

**总任务数:** 11个 (Task 0-10)

**预计时间:** 2-3小时

**执行顺序:**
1. Task 0-2: 基础架构 (配置+工具)
2. Task 3: B站API
3. Task 4-5: 音频+ASR
4. Task 6: LLM总结
5. Task 7: 输出格式化
6. Task 8: CLI主入口
7. Task 9-10: 测试和文档

**每个Task包含:**
- 编写测试（预期失败）
- 运行测试确认失败
- 实现功能
- 运行测试确认通过
- Commit
