"""
commands/version.py — version 命令
"""

import typer

from clash2singbox.utils import console

app = typer.Typer()


@app.callback(invoke_without_command=True)
def version():
    """显示当前版本"""
    from clash2singbox import __version__
    console.print(f"clash2singbox [bold cyan]{__version__}[/bold cyan]")
