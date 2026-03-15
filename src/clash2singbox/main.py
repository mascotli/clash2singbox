#!/usr/bin/env python3
"""
main.py — CLI 入口，只负责注册子命令
对应 pyproject.toml: clash2singbox = "clash2singbox.main:app"
"""

import typer

from clash2singbox.commands import convert, deps, sub, version

app = typer.Typer(
    name="clash2singbox",
    help="将 Clash 订阅转换为 sing-box 1.13+ 配置",
    add_completion=False,
)

app.add_typer(convert.app, name="convert")
app.add_typer(sub.app,     name="sub")
app.add_typer(deps.app,    name="check-deps")
app.add_typer(version.app, name="version")

if __name__ == "__main__":
    app()
