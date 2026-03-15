"""
store.py — 订阅持久化存储管理
数据存储在 ~/.config/clash2singbox/subscriptions.json
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# 常量
# ─────────────────────────────────────────────────────────────────────────────

CONFIG_DIR = Path.home() / ".config" / "clash2singbox"
STORE_FILE = CONFIG_DIR / "subscriptions.json"


# ─────────────────────────────────────────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Subscription:
    name: str
    url: str
    proxy: Optional[str] = None
    output: Optional[str] = None
    direct_ports: list[int] = field(default_factory=lambda: [22])
    created_at: str = field(default_factory=lambda: _now())
    updated_at: Optional[str] = None
    node_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Subscription":
        return cls(
            name=d["name"],
            url=d["url"],
            proxy=d.get("proxy"),
            output=d.get("output"),
            direct_ports=d.get("direct_ports", [22]),
            created_at=d.get("created_at", _now()),
            updated_at=d.get("updated_at"),
            node_count=d.get("node_count", 0),
        )


# ─────────────────────────────────────────────────────────────────────────────
# 存储类
# ─────────────────────────────────────────────────────────────────────────────

class SubscriptionStore:
    """
    订阅信息持久化存储

    用法::

        store = SubscriptionStore()
        store.add(Subscription(name="my-sub", url="https://..."))
        subs = store.list()
        store.remove("my-sub")
    """

    def __init__(self, store_file: Path = STORE_FILE):
        self.store_file = store_file
        self._ensure_dir()

    def list(self) -> list[Subscription]:
        return list(self._load().values())

    def get(self, name: str) -> Optional[Subscription]:
        return self._load().get(name)

    def add(self, sub: Subscription) -> None:
        data = self._load()
        if sub.name in data:
            raise ValueError(f"订阅 '{sub.name}' 已存在，请先删除或使用不同名称")
        data[sub.name] = sub
        self._save(data)

    def update(self, sub: Subscription) -> None:
        data = self._load()
        if sub.name not in data:
            raise KeyError(f"订阅 '{sub.name}' 不存在")
        data[sub.name] = sub
        self._save(data)

    def remove(self, name: str) -> None:
        data = self._load()
        if name not in data:
            raise KeyError(f"订阅 '{name}' 不存在")
        del data[name]
        self._save(data)

    def exists(self, name: str) -> bool:
        return name in self._load()

    def _ensure_dir(self) -> None:
        self.store_file.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, Subscription]:
        if not self.store_file.exists():
            return {}
        try:
            raw = json.loads(self.store_file.read_text(encoding="utf-8"))
            return {name: Subscription.from_dict(d) for name, d in raw.items()}
        except (json.JSONDecodeError, KeyError):
            return {}

    def _save(self, data: dict[str, Subscription]) -> None:
        payload = {name: sub.to_dict() for name, sub in data.items()}
        self.store_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
