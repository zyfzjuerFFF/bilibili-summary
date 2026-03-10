# Bilibili Summary

Bilibili 视频字幕爬取与AI总结工具

## 功能特性

- 支持URL或BV号输入
- 支持按关键词搜索视频并批量汇总前 N 个结果
- 优先获取官方字幕，无字幕自动使用阿里云ASR
- 使用阿里云百炼大模型生成结构化总结
- 支持 Markdown / JSON / 纯文本 输出
- 异步处理，带进度指示

## 安装

```bash
pip install -e .
```

## 配置

首次使用建议运行交互式配置，填写阿里云百炼 API Key：

```bash
bili-summary --configure
```

如果某个视频的官方字幕需要登录，而当前 `SESSDATA` 不存在或已过期，程序会在处理该视频时弹出终端二维码引导登录，并自动保存新的 `SESSDATA`。

或手动创建 `~/.bili-summary/config.yaml`：

```yaml
bilibili:
  # 可留空；需要登录态字幕时，程序会按需触发二维码登录并自动回写
  sessdata: ""

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

# 搜索“理想 i6”，汇总综合排序前20个且标题包含全部关键词的视频
bili-summary --search "理想 i6"

# 搜索“理想 i6”，按最新发布汇总
bili-summary --search "理想 i6" --search-order pubdate

# 指定搜索数量和输出文件
bili-summary --search "理想 i6" --limit 10 -o ideal-i6-summary.md
```

搜索模式说明：

- 搜索结果按综合排序抓取视频。
- 可选排序有两种：`totalrank`（综合排序）和 `pubdate`（最新发布）。
- 只有标题中同时包含全部关键词的视频才会被纳入总结；例如 `--search "理想 i6"` 会跳过只包含“理想”或只包含“i6”的视频。
- 搜索模式当前输出为单个 Markdown 文件；未指定 `-o` 时默认写入当前目录下的 `search-summary.md`。

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
