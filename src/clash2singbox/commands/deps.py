"""
commands/deps.py — check-deps 命令
"""

import typer

from clash2singbox.utils import console

app = typer.Typer()


@app.callback(invoke_without_command=True)
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
        