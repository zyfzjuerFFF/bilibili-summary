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

    def test_format_search_results_markdown(self, sample_result, sample_video_info):
        formatter = OutputFormatter(format_type="markdown")
        output = formatter.format_search_results(
            "理想 i6",
            "最新发布",
            [
                {
                    "rank": 1,
                    "summary": sample_result,
                    "video_info": sample_video_info,
                    "subtitle_source": "官方字幕",
                }
            ],
        )

        assert "# 搜索结果总结：理想 i6" in output
        assert "- **排序方式**: 最新发布" in output
        assert "## 1. 测试视频" in output
        assert "### 核心要点" in output
        assert "https://www.bilibili.com/video/BV1xx" in output
