"""
commands/help.py — 帮助信息
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


def print_help():
    """打印帮助信息，供 main.py 直接调用"""
    console.print(Panel(
        Text.from_markup(
            "[bold cyan]clash2singbox[/bold cyan] — Clash 订阅转 sing-box 1.13+ 配置工具\n"
        ),
        border_style="cyan",
        padding=(0, 1),
    ))

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("命令", style="bold cyan", width=28)
    table.add_column("说明")

    table.add_row("convert [i]<url|file>[/i]",  "一次性转换订阅，不保存订阅信息")
    table.add_row("", "")
    table.add_row("[bold]sub add[/bold] [i]<url>[/i]",    "添加并保存订阅")
    table.add_row("sub list",                             "列出所有已保存的订阅")
    table.add_row("sub update [i][name][/i]",             "更新指定订阅（不填则更新全部）")
    table.add_row("sub remove [i]<name>[/i]",             "删除订阅")
    table.add_row("sub show [i]<name>[/i]",               "查看订阅详情")
    table.add_row("", "")
    table.add_row("check-deps",                           "检查依赖是否已安装")
    table.add_row("", "")

    console.print(table)

    console.print("[bold]选项:[/bold]")
    console.print("  [cyan]-h, --help[/cyan]       显示此帮助")
    console.print("  [cyan]-v, --version[/cyan]    显示当前版本\n")

    console.print("[bold]常用示例:[/bold]")
    console.print("  [dim]# 添加订阅（自动拉取并生成配置）[/dim]")
    console.print("  clash2singbox sub add [cyan]\"https://your-sub-url\"[/cyan] -n myisp -o ~/config.json -p http://127.0.0.1:7890\n")
    console.print("  [dim]# 更新全部订阅[/dim]")
    console.print("  clash2singbox sub update\n")
    console.print("  [dim]# 一次性转换[/dim]")
    console.print("  clash2singbox convert [cyan]\"https://your-sub-url\"[/cyan] -o config.json\n")
