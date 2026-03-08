# Bilibili 视频字幕爬取与总结工具 - 设计文档

## 1. 项目概述

一个命令行工具，输入 Bilibili 视频 URL 或 BV 号，自动获取字幕（官方字幕优先，无字幕时用阿里云百炼ASR），并使用阿里云百炼大模型生成结构化视频总结。

## 2. 核心功能

| 功能模块 | 实现方式 |
|---------|---------|
| 视频信息解析 | 从URL/BV提取BV号，调用B站API获取视频信息 |
| 字幕获取 | 1. 调用B站字幕API获取官方字幕<br>2. 无字幕时，提取音频上传阿里云百炼ASR |
| 内容总结 | 调用阿里云百炼大模型API（如qwen-plus） |
| 输出展示 | 结构化Markdown格式（标题、要点、关键信息、时间戳） |

## 3. 技术架构

```
bili-summary/
├── bili_summary/
│   ├── __init__.py
│   ├── cli.py           # Click命令行入口
│   ├── config.py        # 配置管理
│   ├── bilibili.py      # B站API封装
│   ├── asr.py           # 阿里云百炼ASR
│   ├── summarizer.py    # 阿里云百炼总结
│   ├── output.py        # 输出格式化
│   └── utils.py         # 工具函数
├── config.yaml          # 用户配置文件
├── requirements.txt
└── README.md
```

## 4. 数据流

```
输入: URL/BV号
  ↓
提取BV号 → 获取视频信息 → 获取cid
  ↓
尝试获取官方字幕 ──有字幕──→ 字幕文本
      └──无字幕──→ 下载音频 → 阿里云ASR → 字幕文本
                              ↓
                        阿里云百炼大模型
                              ↓
                    结构化总结输出
```

## 5. 配置设计

`~/.bili-summary/config.yaml`:
```yaml
# 阿里云百炼配置（必需）
aliyun:
  access_key_id: "your-access-key"
  access_key_secret: "your-secret"
  region: "cn-beijing"  # 默认

  # ASR配置
  asr:
    model: "paraformer-realtime-v1"  # 语音识别模型

  # 总结模型配置
  llm:
    model: "qwen-plus"  # 或其他百炼模型
    max_tokens: 2000
    temperature: 0.7

# 输出配置
output:
  format: "markdown"  # markdown/json/text
  language: "zh"      # 输出语言
  include_timestamps: true
```

## 6. CLI 设计

```bash
# 基本使用
bili-summary https://www.bilibili.com/video/BV1xx411c7mD
bili-summary BV1xx411c7mD

# 指定输出文件
bili-summary BV1xx411c7mD -o summary.md

# 指定输出格式
bili-summary BV1xx411c7mD --format json

# 交互式配置
bili-summary --configure
```

## 7. 输出格式示例

```markdown
# 【视频标题】

## 视频信息
- **UP主**: xxx
- **时长**: 15:30
- **发布时间**: 2024-01-15
- **字幕来源**: 官方字幕 / ASR识别

## 内容总结

### 核心要点
1. [00:00-02:30] 视频开场，介绍了xxx...
2. [02:30-05:00] 详细讲解了yyy...
3. ...

### 关键信息
- **重点1**: xxx
- **重点2**: yyy

### 时间戳导航
| 时间 | 内容 |
|------|------|
| 00:00 | 开场 |
| 02:30 | 核心概念介绍 |
| ... | ... |
```

## 8. 错误处理

| 错误场景 | 处理方式 |
|---------|---------|
| 视频不存在 | 清晰错误提示 |
| 无权限访问 | 提示可能需要登录（后续版本支持） |
| 阿里云API失败 | 重试3次，失败给出详细错误信息 |
| 音频提取失败 | 降级为无字幕模式，总结视频标题/描述 |

## 9. 后续扩展（可选）

- 批量处理多个视频
- 支持收藏夹/UP主全部视频
- 支持其他模型提供商（OpenAI、Claude等）
- 本地缓存避免重复处理

## 10. 技术选型确认

- **语言**: Python 3.9+
- **CLI框架**: Click
- **输出美化**: Rich
- **HTTP请求**: httpx
- **音频处理**: yt-dlp（下载）+ 阿里云百炼ASR
- **配置**: PyYAML
