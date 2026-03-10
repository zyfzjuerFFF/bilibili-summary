"""命令行入口"""
import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel

from bili_summary.config import ConfigManager, Config
from bili_summary.bilibili import BilibiliAPI
from bili_summary.asr import AliyunASR
from bili_summary.downloader import AudioDownloader
from bili_summary.summarizer import Summarizer
from bili_summary.output import OutputFormatter
from bili_summary.utils import extract_bv

import qrcode

console = Console()
SEARCH_ORDER_LABELS = {
    "totalrank": "综合排序",
    "pubdate": "最新发布",
}


def print_error(message: str):
    """打印错误信息"""
    console.print(f"[bold red]错误:[/bold red] {message}")


def print_success(message: str):
    """打印成功信息"""
    console.print(f"[bold green]✓[/bold green] {message}")


def print_info(message: str):
    """打印信息"""
    console.print(f"[blue]ℹ[/blue] {message}")


def render_qr_code(qr_url: str):
    """在终端中渲染二维码"""
    qr = qrcode.QRCode(version=1, box_size=1, border=2)
    qr.add_data(qr_url)
    qr.make(fit=True)

    console.print("\n请使用 Bilibili App 扫描下方二维码：\n")
    qr.print_ascii(tty=sys.stdout.isatty())


async def login_bilibili_via_qr() -> str:
    """通过二维码登录 Bilibili 并返回 SESSDATA"""
    api = BilibiliAPI()

    try:
        qr_url, qr_key = await api.generate_qr_code()
        render_qr_code(qr_url)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("等待扫码确认中...", total=None)

            while True:
                success, msg, sessdata = await api.poll_qr_code(qr_key)
                if success:
                    if sessdata:
                        progress.update(task, description="登录成功，SESSDATA 已获取")
                        return sessdata

                    progress.update(task, description="[red]登录成功，但未获取到 SESSDATA[/red]")
                    print_error("登录成功，但未能提取 SESSDATA")
                    return ""

                if msg == "二维码已失效" or msg.startswith("轮询失败"):
                    progress.update(task, description=f"[red]{msg}[/red]")
                    print_error(msg)
                    return ""

                progress.update(task, description=f"等待扫码确认中... 当前状态: {msg}")
                await asyncio.sleep(2)
    finally:
        await api.close()


def subtitle_login_required(message: str) -> bool:
    """判断当前字幕获取是否要求登录"""
    return message == "获取原生字幕需登录，当前未登录无法获取"


async def refresh_bilibili_login(api: BilibiliAPI, config: Config) -> BilibiliAPI:
    """在需要时引导用户扫码登录，并返回可复用的新 API 客户端"""
    if not sys.stdin.isatty():
        print_info("该视频原生字幕需要 Bilibili 登录，当前为非交互环境，跳过扫码登录。")
        return api

    print_info("该视频原生字幕需要 Bilibili 登录，当前登录态不可用或已过期。")
    if not click.confirm("是否现在扫码登录以获取原生字幕？", default=True):
        return api

    sessdata = await login_bilibili_via_qr()
    if not sessdata:
        return api

    config.bilibili.sessdata = sessdata
    ConfigManager().save(config)
    print_success("Bilibili 登录已更新并保存到 ~/.bili-summary/config.yaml")

    await api.close()
    return BilibiliAPI(sessdata=sessdata)


async def summarize_video(
    api: BilibiliAPI,
    bvid: str,
    config: Config,
    summarizer: Summarizer,
) -> tuple[dict, BilibiliAPI]:
    """提取单个视频的字幕并生成总结。"""
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

    subtitle_text = ""
    subtitle_source = ""

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("获取官方字幕...", total=None)
        subtitles, msg = await api.get_subtitle_list(bvid, video_info.cid)

        if not subtitles and subtitle_login_required(msg):
            progress.stop()
            api = await refresh_bilibili_login(api, config)
            progress.start()
            progress.update(task, description="重新获取官方字幕...")
            subtitles, msg = await api.get_subtitle_list(bvid, video_info.cid)

        if subtitles:
            zh_subs = [s for s in subtitles if "zh" in s.language.lower()]
            selected = zh_subs[0] if zh_subs else subtitles[0]

            subtitle_items = await api.download_subtitle(selected.subtitle_url)
            subtitle_text = api.format_subtitle_text(subtitle_items)
            subtitle_source = "官方字幕" + (
                "(AI生成)" if selected.is_ai_generated else ""
            )
            progress.update(task, description=f"获取到官方字幕 ({len(subtitle_items)} 句)")
        else:
            progress.stop()
            print_info(f"官方字幕获取情况: {msg}")
            progress.start()
            progress.update(task, description="无有效官方字幕，准备使用ASR...")

            if not config.aliyun.api_key:
                raise Exception("未配置阿里云API密钥，无法使用ASR")

            downloader = AudioDownloader()
            asr = AliyunASR(config)

            try:
                progress.update(task, description="下载音频...")
                audio_path = await asyncio.to_thread(downloader.extract_audio, bvid)

                progress.update(task, description="识别音频...")
                asr_result = await asr.transcribe(audio_path)
                subtitle_text = asr.format_as_subtitle(asr_result)
                subtitle_source = "ASR识别"

                downloader.cleanup(audio_path)
            except Exception as e:
                raise Exception(f"ASR识别失败: {e}") from e

    if not subtitle_text.strip():
        raise Exception("未能获取到任何字幕内容")

    print_success(f"字幕来源: {subtitle_source}")
    print_info(f"字幕长度: {len(subtitle_text)} 字符")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("生成总结...", total=None)
        summary = await summarizer.summarize(
            subtitle_text,
            {
                "bvid": video_info.bvid,
                "title": video_info.title,
                "owner_name": video_info.owner_name,
                "duration": video_info.duration,
                "desc": video_info.description,
            },
        )
        progress.update(task, completed=True)

    return {
        "summary": summary,
        "video_info": {
            "bvid": video_info.bvid,
            "title": video_info.title,
            "owner_name": video_info.owner_name,
            "duration": video_info.duration,
        },
        "subtitle_source": subtitle_source,
    }, api


async def process_video(
    url_or_bv: str,
    config: Config,
    output_file: Optional[str],
    output_format: str,
) -> bool:
    """处理单个视频"""
    api = BilibiliAPI(sessdata=config.bilibili.sessdata)

    try:
        try:
            bvid = extract_bv(url_or_bv)
            print_info(f"提取到BV号: {bvid}")
        except ValueError as e:
            print_error(f"无法识别BV号: {e}")
            return False

        summary_bundle, api = await summarize_video(api, bvid, config, Summarizer(config))

        formatter = OutputFormatter(output_format)
        output = formatter.format(
            summary_bundle["summary"],
            summary_bundle["video_info"],
            summary_bundle["subtitle_source"],
        )

        if output_file:
            Path(output_file).write_text(output, encoding="utf-8")
            print_success(f"总结已保存到: {output_file}")
        else:
            console.print()
            console.print(Panel(output, title="视频总结", border_style="green"))
        return True

    except Exception as e:
        print_error(f"处理失败: {e}")
        return False
    finally:
        await api.close()


async def process_search_query(
    keyword: str,
    limit: int,
    order: str,
    config: Config,
    output_file: Optional[str],
) -> bool:
    """根据搜索词批量总结视频并输出单个 Markdown。"""
    api = BilibiliAPI(sessdata=config.bilibili.sessdata)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"搜索视频: {keyword} ({SEARCH_ORDER_LABELS.get(order, order)})",
                total=None,
            )
            search_results = await api.search_videos(keyword, limit=limit, order=order)
            progress.update(task, completed=True)

        if not search_results:
            print_error(f"未搜索到与“{keyword}”相关的视频")
            return False

        print_success(f"已找到 {len(search_results)} 个视频，开始逐个总结")
        summarizer = Summarizer(config)
        formatter = OutputFormatter("markdown")
        aggregated_results = []

        for index, item in enumerate(search_results, 1):
            console.print()
            console.rule(f"[bold blue]{index}/{len(search_results)} {item.title}")
            try:
                summary_bundle, api = await summarize_video(api, item.bvid, config, summarizer)
                aggregated_results.append(
                    {
                        "rank": index,
                        **summary_bundle,
                    }
                )
            except Exception as e:
                print_error(f"{item.title} 处理失败: {e}")
                aggregated_results.append(
                    {
                        "rank": index,
                        "summary": None,
                        "subtitle_source": "失败",
                        "video_info": {
                            "bvid": item.bvid,
                            "title": item.title,
                            "owner_name": item.owner_name,
                            "duration": 0,
                        },
                        "error": str(e),
                    }
                )

        output = formatter.format_search_results(
            keyword,
            SEARCH_ORDER_LABELS.get(order, order),
            aggregated_results,
        )
        target_path = output_file or "search-summary.md"
        Path(target_path).write_text(output, encoding="utf-8")
        print_success(f"批量总结已保存到: {target_path}")
        return True
    except Exception as e:
        print_error(f"批量处理失败: {e}")
        return False
    finally:
        await api.close()


@click.command()
@click.argument("url_or_bv", required=False)
@click.option(
    "--search",
    "search_keyword",
    help="按关键词搜索视频并批量生成总结",
)
@click.option(
    "--limit",
    default=20,
    show_default=True,
    type=click.IntRange(1, 100),
    help="搜索模式下汇总的视频数量",
)
@click.option(
    "--search-order",
    "search_order",
    default="totalrank",
    show_default=True,
    type=click.Choice(["totalrank", "pubdate"]),
    help="搜索模式排序：totalrank=综合排序，pubdate=最新发布",
)
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
def main(
    url_or_bv: Optional[str],
    search_keyword: Optional[str],
    limit: int,
    search_order: str,
    output: Optional[str],
    output_format: str,
    configure: bool,
):
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
        config = config_manager.load() if config_manager.exists() else Config()

        console.print(Panel("配置阿里云百炼", border_style="blue"))
        console.print("获取 API Key: https://bailian.console.aliyun.com/#/api-key")
        if config.aliyun.api_key:
            console.print("已检测到现有 API Key，直接回车可保留当前值。")
        console.print()

        api_key = click.prompt(
            "API Key",
            default=config.aliyun.api_key,
            hide_input=True,
            show_default=False,
        )
        region = click.prompt("Region", default=config.aliyun.region)

        config.aliyun.api_key = api_key
        config.aliyun.region = region

        config_manager.save(config)
        print_success("配置已保存到 ~/.bili-summary/config.yaml")
        return

    # 检查配置
    if not config_manager.exists():
        print_error("未找到配置文件，请先运行: bili-summary --configure")
        sys.exit(1)

    config = config_manager.load()

    if not config.aliyun.api_key:
        print_error("阿里云 API Key 未配置")
        sys.exit(1)

    if search_keyword and url_or_bv:
        print_error("`--search` 模式下不需要再提供视频 URL 或 BV 号")
        sys.exit(1)

    if search_keyword:
        if output_format != "markdown":
            print_error("搜索批量模式当前仅支持 markdown 输出")
            sys.exit(1)
        success = asyncio.run(
            process_search_query(search_keyword, limit, search_order, config, output)
        )
        if not success:
            sys.exit(1)
        return

    if not url_or_bv:
        print_error("请提供视频 URL / BV 号，或使用 `--search`")
        sys.exit(1)

    success = asyncio.run(process_video(url_or_bv, config, output, output_format))
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
