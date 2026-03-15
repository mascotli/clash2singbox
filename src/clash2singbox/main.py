#!/usr/bin/env python3
"""
main.py — CLI 入口，只负责注册子命令
对应 pyproject.toml: clash2singbox = "clash2singbox.main:app"
"""

import typer

from clash2singbox.commands import convert, deps, sub
from clash2singbox.commands.help import print_help

app = typer.Typer(
    name="clash2singbox",
    help="将 Clash 订阅转换为 sing-box 1.13+ 配置",
    add_completion=False,
    invoke_without_command=True,
)


@app.callback(invoke_without_command=True)
def default(
    ctx: typer.Context,
    help: bool = typer.Option(False, "--help", "-h", help="显示帮助信息", is_eager=True),
    version: bool = typer.Option(False, "--version", "-v", help="显示版本号", is_eager=True),
):
    if version:
        from clash2singbox import __version__
        from clash2singbox.utils import console
        console.print(f"clash2singbox [bold cyan]{__version__}[/bold cyan]")
        raise typer.Exit()

    if help or ctx.invoked_subcommand is None:
        print_help()
        raise typer.Exit()


app.add_typer(convert.app, name="convert")
app.add_typer(sub.app,     name="sub")
app.add_typer(deps.app,    name="check-deps")

if __name__ == "__main__":
    app()
