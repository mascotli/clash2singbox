#!/usr/bin/env python3
"""
clash2singbox CLI 入口
对应 pyproject.toml 中: clash2singbox = "clash2singbox.main:app"
"""

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

app = typer.Typer(
    name="clash2singbox",
    help="将 Clash 订阅转换为 sing-box 1.13+ 配置",
    add_completion=False,
)
console = Console()


# ─────────────────────────────────────────────────────────────────────────────
# 内部工具
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_raw(source: str, proxy: Optional[str]) -> str:
    """统一读取原始订阅内容（URL 或本地文件）"""
    parsed = urlparse(source)
    if parsed.scheme in ("http", "https"):
        proxies_map = {"http://": proxy, "https://": proxy} if proxy else None
        resp = httpx.get(
            source,
            follow_redirects=True,
            timeout=30,
            headers={"User-Agent": "clash"},
            proxies=proxies_map,
        )
        resp.raise_for_status()
        return resp.text
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {source}")
    return path.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# CLI 命令
# ─────────────────────────────────────────────────────────────────────────────

@app.command()
def convert(
    source: str = typer.Argument(
        ..., help="Clash 订阅 URL 或本地 YAML 文件路径"
    ),
    output: Optional[Path] = typer.Option(
        None, "-o", "--output", help="输出文件路径（默认 config.json）"
    ),
    print_config: bool = typer.Option(
        False, "--print", help="直接打印到终端而不写文件"
    ),
    force: bool = typer.Option(
        False, "-f", "--force", help="覆盖已存在的输出文件"
    ),
    proxy: Optional[str] = typer.Option(
        None, "-p", "--proxy", help="下载订阅时使用的代理，如 http://127.0.0.1:7890"
    ),
    direct_ports: str = typer.Option(
        "22", "--direct-ports", help="逗号分隔的直连端口，如 22,2222（默认 22）"
    ),
):
    """将 Clash 订阅转换为 sing-box 1.13+ 配置文件"""

    # 解析直连端口
    try:
        ports = [int(p.strip()) for p in direct_ports.split(",") if p.strip()]
    except ValueError:
        console.print("[red]✗ --direct-ports 格式错误，请用逗号分隔的数字，如 22,2222[/red]")
        raise typer.Exit(1)

    # 读取订阅
    if proxy:
        console.print(f"[cyan]⬇ 正在下载订阅[/cyan] {source} [dim](via {proxy})[/dim]")
    else:
        console.print(f"[cyan]⬇ 正在读取[/cyan] {source}")

    try:
        raw = _fetch_raw(source, proxy)
        clash_cfg = yaml.safe_load(raw)
    except Exception as e:
        console.print(f"[red]✗ 读取失败: {e}[/red]")
        raise typer.Exit(1)

    proxies_list = clash_cfg.get("proxies", [])
    if not proxies_list:
        console.print("[red]✗ 未找到任何节点 (proxies 字段为空)[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓ 共读取到 {len(proxies_list)} 个节点[/green]")

    # 初始化转换器并转换
    converter = ClashToSingboxConverter(proxy=proxy, direct_ports=ports)

    try:
        result = converter.parse_proxies(proxies_list)
        config = converter.build_singbox_config(result)
    except Exception as e:
        console.print(f"[red]✗ 转换失败: {e}[/red]")
        raise typer.Exit(1)

    # 打印节点分布表
    table = Table(title="节点分布", show_header=True, header_style="bold cyan")
    table.add_column("地区", style="bold")
    table.add_column("节点数", justify="right")
    table.add_column("节点列表（前3）", overflow="fold")

    for region in PRIORITY_REGIONS:
        tags = result.region_map.get(region, [])
        if tags:
            preview = ", ".join(tags[:3]) + ("..." if len(tags) > 3 else "")
            table.add_row(region, str(len(tags)), preview)

    for region in [*SOUTHEAST_ASIA, *OTHER_REGIONS]:
        tags = result.region_map.get(region, [])
        if tags:
            preview = ", ".join(tags[:3]) + ("..." if len(tags) > 3 else "")
            table.add_row(region, str(len(tags)), preview)

    other = result.region_map.get("🌐 其他", [])
    if other:
        preview = ", ".join(other[:3]) + ("..." if len(other) > 3 else "")
        table.add_row("🌐 未识别", str(len(other)), preview)

    console.print(table)

    # 跳过条目
    if result.skipped:
        console.print(f"\n[yellow]⚠ 跳过 {len(result.skipped)} 个条目:[/yellow]")
        for name, reason in result.skipped[:10]:
            console.print(f"  [dim]• {name}[/dim] — {reason}")
        if len(result.skipped) > 10:
            console.print(f"  [dim]... 及其他 {len(result.skipped) - 10} 个[/dim]")

    console.print(f"\n[green]✓ 成功转换 {result.total} 个节点[/green]")
    console.print(f"[dim]直连端口: {ports}  |  GitHub 域名强制走代理[/dim]")

    # 序列化
    config_json = json.dumps(config, ensure_ascii=False, indent=2)

    if print_config:
        console.print(config_json)
        return

    if output is None:
        output = Path("config.json")

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


@app.command()
def check_deps():
    """检查依赖是否已安装"""
    deps = {"httpx": "httpx", "yaml": "pyyaml", "typer": "typer", "rich": "rich"}
    all_ok = True
    for module, pkg in deps.items():
        try:
            __import__(module)
            console.print(f"[green]✓[/green] {pkg}")
        except ImportError:
            console.print(f"[red]✗[/red] {pkg}  →  pip install {pkg}")
            all_ok = False
    if all_ok:
        console.print("\n[bold green]所有依赖已就绪[/bold green]")
    else:
        console.print("\n[bold]安装全部依赖:[/bold]\n  pip install httpx pyyaml typer rich")


@app.command()
def version():
    """显示当前版本"""
    from clash2singbox import __version__
    console.print(f"clash2singbox [bold cyan]{__version__}[/bold cyan]")


if __name__ == "__main__":
    app()
