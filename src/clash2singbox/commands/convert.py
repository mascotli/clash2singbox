"""
commands/convert.py — 一次性转换命令
"""

from pathlib import Path
from typing import Optional

import typer

from clash2singbox.utils import console, do_convert, parse_ports

app = typer.Typer()


# @app.callback(invoke_without_command=True)
# @app.command()
def convert(
    source: str = typer.Argument(..., help="Clash 订阅 URL 或本地 YAML 文件路径"),
    output: Optional[Path] = typer.Option(None, "-o", "--output", help="输出文件路径（默认 config.json）"),
    print_config: bool = typer.Option(False, "--print", help="直接打印到终端而不写文件"),
    force: bool = typer.Option(False, "-f", "--force", help="覆盖已存在的输出文件"),
    proxy: Optional[str] = typer.Option(None, "-p", "--proxy", help="下载订阅时使用的代理，如 http://127.0.0.1:7890"),
    direct_ports: str = typer.Option("22", "--direct-ports", help="逗号分隔的直连端口，如 22,2222"),
):
    """一次性将 Clash 订阅转换为 sing-box 配置（不保存订阅信息）"""
    ports = parse_ports(direct_ports)
    if output is None:
        output = Path("config.json")
    try:
        do_convert(source, proxy, ports, output, force=force, print_config=print_config)
    except Exception as e:
        console.print(f"[red]✗ 转换失败: {e}[/red]")
        raise typer.Exit(1)
    