# Bilibili Summary

Bilibili 视频字幕爬取与AI总结工具

## 功能特性

- 支持URL或BV号输入
- 优先获取官方字幕，无字幕自动使用阿里云ASR
- 使用阿里云百炼大模型生成结构化总结
- 支持 Markdown / JSON / 纯文本 输出
- 异步处理，带进度指示

## 安装

```bash
pip install -e .
```

## 配置

首次使用需要配置阿里云百炼 API Key：

```bash
bili-summary --configure
```

或手动创建 `~/.bili-summary/config.yaml`：

```yaml
aliyun:
  # 从 https://bailian.console.aliyun.com/#/api-key 获取 API Key
  api_key: "your-api-key"
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
