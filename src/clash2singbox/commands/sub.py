"""
commands/sub.py — 订阅管理子命令组
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import typer
from rich.panel import Panel
from rich.table import Table

from clash2singbox.store import STORE_FILE, Subscription, SubscriptionStore
from clash2singbox.utils import console, do_convert, parse_ports

app = typer.Typer(help="管理订阅")
store = SubscriptionStore()


def _update_sub(sub: Subscription) -> None:
    """拉取并重新生成单个订阅配置"""
    output = Path(sub.output) if sub.output else Path(f"{sub.name}.json")
    node_count = do_convert(
        source=sub.url,
        proxy=sub.proxy,
        ports=sub.direct_ports,
        output=output,
        force=True,
    )
    sub.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sub.node_count = node_count
    store.update(sub)


@app.command("add")
def sub_add(
    url: str = typer.Argument(..., help="订阅 URL"),
    name: Optional[str] = typer.Option(None, "-n", "--name", help="订阅名称（默认用 URL 域名）"),
    output: Optional[Path] = typer.Option(None, "-o", "--output", help="生成配置的输出路径"),
    proxy: Optional[str] = typer.Option(None, "-p", "--proxy", help="下载时使用的代理"),
    direct_ports: str = typer.Option("22", "--direct-ports", help="直连端口，逗号分隔"),
    update: bool = typer.Option(True, "--update/--no-update", help="添加后立即拉取并生成配置"),
):
    """添加一个新订阅"""
    if name is None:
        parsed = urlparse(url)
        name = parsed.hostname or "sub"

    if store.exists(name):
        console.print(f"[red]✗ 订阅 '{name}' 已存在，请用 -n 指定其他名称[/red]")
        raise typer.Exit(1)

    ports = parse_ports(direct_ports)
    output_path = str(output) if output else f"{name}.json"

    sub = Subscription(
        name=name,
        url=url,
        proxy=proxy,
        output=output_path,
        direct_ports=ports,
    )
    store.add(sub)
    console.print(f"[green]✓ 订阅 '{name}' 已添加[/green]")
    console.print(f"  [dim]配置将输出到: {output_path}[/dim]")

    if update:
        try:
            _update_sub(sub)
        except Exception as e:
            console.print(f"[red]✗ 初次更新失败: {e}[/red]")


@app.command("list")
def sub_list():
    """列出所有已保存的订阅"""
    subs = store.list()
    if not subs:
        console.print("[yellow]暂无订阅，使用 'clash2singbox sub add <url>' 添加[/yellow]")
        return

    table = Table(title="订阅列表", show_header=True, header_style="bold cyan")
    table.add_column("名称", style="bold")
    table.add_column("节点数", justify="right")
    table.add_column("最后更新")
    table.add_column("输出文件")
    table.add_column("代理")

    for sub in subs:
        updated = sub.updated_at or "[dim]从未[/dim]"
        proxy_str = sub.proxy or "[dim]无[/dim]"
        node_str = str(sub.node_count) if sub.node_count else "[dim]-[/dim]"
        table.add_row(sub.name, node_str, updated, sub.output or "-", proxy_str)

    console.print(table)
    console.print(f"\n[dim]数据存储于: {STORE_FILE}[/dim]")


@app.command("update")
def sub_update(
    name: Optional[str] = typer.Argument(None, help="订阅名称，不填则更新全部"),
):
    """更新订阅并重新生成配置"""
    if name:
        sub = store.get(name)
        if not sub:
            console.print(f"[red]✗ 订阅 '{name}' 不存在[/red]")
            raise typer.Exit(1)
        try:
            _update_sub(sub)
        except Exception as e:
            console.print(f"[red]✗ 更新失败: {e}[/red]")
            raise typer.Exit(1)
    else:
        subs = store.list()
        if not subs:
            console.print("[yellow]暂无订阅[/yellow]")
            return
        console.print(f"[cyan]正在更新全部 {len(subs)} 个订阅...[/cyan]\n")
        ok, fail = 0, 0
        for sub in subs:
            console.rule(f"[bold]{sub.name}[/bold]")
            try:
                _update_sub(sub)
                ok += 1
            except Exception as e:
                console.print(f"[red]✗ 更新失败: {e}[/red]")
                fail += 1
        console.rule()
        if fail:
            console.print(f"[yellow]完成：{ok} 成功，{fail} 失败[/yellow]")
        else:
            console.print(f"[green]✓ 全部 {ok} 个订阅更新成功[/green]")


@app.command("remove")
def sub_remove(
    name: str = typer.Argument(..., help="要删除的订阅名称"),
    yes: bool = typer.Option(False, "-y", "--yes", help="跳过确认"),
):
    """删除一个订阅（不会删除已生成的配置文件）"""
    if not store.exists(name):
        console.print(f"[red]✗ 订阅 '{name}' 不存在[/red]")
        raise typer.Exit(1)

    if not yes:
        confirm = typer.confirm(f"确认删除订阅 '{name}'?")
        if not confirm:
            console.print("[yellow]已取消[/yellow]")
            return

    store.remove(name)
    console.print(f"[green]✓ 订阅 '{name}' 已删除[/green]")


@app.command("show")
def sub_show(
    name: str = typer.Argument(..., help="订阅名称"),
):
    """查看订阅详情"""
    sub = store.get(name)
    if not sub:
        console.print(f"[red]✗ 订阅 '{name}' 不存在[/red]")
        raise typer.Exit(1)

    console.print(Panel(
        f"[bold]名称:[/bold]      {sub.name}\n"
        f"[bold]URL:[/bold]       {sub.url}\n"
        f"[bold]输出文件:[/bold]  {sub.output}\n"
        f"[bold]代理:[/bold]      {sub.proxy or '无'}\n"
        f"[bold]直连端口:[/bold]  {sub.direct_ports}\n"
        f"[bold]节点数:[/bold]    {sub.node_count or '-'}\n"
        f"[bold]创建时间:[/bold]  {sub.created_at}\n"
        f"[bold]最后更新:[/bold]  {sub.updated_at or '从未'}",
        title=f"订阅详情 · {name}",
        border_style="cyan",
    ))
    