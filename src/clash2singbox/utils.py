"""
utils.py — 各命令共用的工具函数
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from clash2singbox.converter import (
    OTHER_REGIONS,
    PRIORITY_REGIONS,
    SOUTHEAST_ASIA,
    ClashToSingboxConverter,
)

console = Console()


def fetch_raw(source: str, proxy: Optional[str]) -> str:
    """统一读取原始订阅内容（URL 或本地文件）"""
    parsed = urlparse(source)
    if parsed.scheme in ("http", "https"):
        resp = httpx.get(
            source,
            follow_redirects=True,
            timeout=30,
            headers={"User-Agent": "clash"},
            proxy=proxy,
        )
        resp.raise_for_status()
        return resp.text
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {source}")
    return path.read_text(encoding="utf-8")


def parse_ports(direct_ports: str) -> list[int]:
    """解析逗号分隔的端口字符串"""
    try:
        return [int(p.strip()) for p in direct_ports.split(",") if p.strip()]
    except ValueError:
        console.print("[red]✗ --direct-ports 格式错误，请用逗号分隔的数字，如 22,2222[/red]")
        raise typer.Exit(1)


def do_convert(
    source: str,
    proxy: Optional[str],
    ports: list[int],
    output: Path,
    force: bool = True,
    print_config: bool = False,
) -> int:
    """执行转换并写入文件，返回节点数。供 convert 命令和 sub update 共用。"""
    if proxy:
        console.print(f"[cyan]⬇ 正在下载订阅[/cyan] {source} [dim](via {proxy})[/dim]")
    else:
        console.print(f"[cyan]⬇ 正在下载订阅[/cyan] {source}")

    raw = fetch_raw(source, proxy)
    clash_cfg = yaml.safe_load(raw)

    proxies_list = clash_cfg.get("proxies", [])
    if not proxies_list:
        raise ValueError("未找到任何节点 (proxies 字段为空)")

    console.print(f"[green]✓ 共读取到 {len(proxies_list)} 个节点[/green]")

    converter = ClashToSingboxConverter(proxy=proxy, direct_ports=ports)
    result = converter.parse_proxies(proxies_list)
    config = converter.build_singbox_config(result)

    table = Table(title="节点分布", show_header=True, header_style="bold cyan")
    table.add_column("地区", style="bold")
    table.add_column("节点数", justify="right")
    table.add_column("节点列表（前3）", overflow="fold")

    for region in PRIORITY_REGIONS:
        tags = result.region_map.get(region, [])
        if tags:
            table.add_row(region, str(len(tags)), ", ".join(tags[:3]) + ("..." if len(tags) > 3 else ""))

    for region in [*SOUTHEAST_ASIA, *OTHER_REGIONS]:
        tags = result.region_map.get(region, [])
        if tags:
            table.add_row(region, str(len(tags)), ", ".join(tags[:3]) + ("..." if len(tags) > 3 else ""))

    other = result.region_map.get("🌐 其他", [])
    if other:
        table.add_row("🌐 未识别", str(len(other)), ", ".join(other[:3]) + ("..." if len(other) > 3 else ""))

    console.print(table)

    if result.skipped:
        console.print(f"\n[yellow]⚠ 跳过 {len(result.skipped)} 个条目:[/yellow]")
        for name, reason in result.skipped[:10]:
            console.print(f"  [dim]• {name}[/dim] — {reason}")
        if len(result.skipped) > 10:
            console.print(f"  [dim]... 及其他 {len(result.skipped) - 10} 个[/dim]")

    console.print(f"\n[green]✓ 成功转换 {result.total} 个节点[/green]")
    console.print(f"[dim]直连端口: {ports}  |  GitHub 域名强制走代理[/dim]")

    config_json = json.dumps(config, ensure_ascii=False, indent=2)

    if print_config:
        console.print(config_json)
        return result.total

    if output.exists() and not force:
        overwrite = typer.confirm(f"文件 {output} 已存在，是否覆盖?")
        if not overwrite:
            console.print("[yellow]已取消[/yellow]")
            raise typer.Exit(0)

    output.write_text(config_json, encoding="utf-8")
    console.print(Panel(
        f"[bold green]✓ 配置已写入[/bold green] [cyan]{output.resolve()}[/cyan]\n\n"
        f"节点总数: [bold]{result.total}[/bold]  |  "
        f"地区分组: [bold]{len(result.regions)}[/bold]  |  "
        f"直连端口: [bold]{ports}[/bold]\n\n"
        f"运行方式: [dim]sing-box run -c {output}[/dim]",
        title="转换完成",
        border_style="green",
    ))

    return result.total
