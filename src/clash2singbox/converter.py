"""
converter.py — Clash → sing-box 核心转换逻辑
可单独 import 使用，不依赖 CLI 框架
"""
 
from __future__ import annotations
 
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
 
import httpx
import yaml
 
 
# ─────────────────────────────────────────────────────────────────────────────
# 常量
# ─────────────────────────────────────────────────────────────────────────────
 
JUNK_KEYWORDS = [
    "剩余流量", "距离", "重置", "套餐", "到期", "官网", "备用",
    "进不去", "先关闭", "expire", "traffic", "remaining",
]
 
REGION_MAP: dict[str, list[str]] = {
    "🇸🇬 新加坡":   ["新加坡", "狮城", "sg", "singapore"],
    "🇭🇰 香港":     ["香港", "hk", "hong kong", "hongkong"],
    "🇺🇸 美国":     ["美国", "us", "united states", "america"],
    "🇯🇵 日本":     ["日本", "jp", "japan"],
    "🇹🇼 台湾":     ["台湾", "台灣", "tw", "taiwan"],
    "🇰🇷 韩国":     ["韩国", "韓國", "kr", "korea"],
    "🇲🇾 马来西亚":  ["马来", "馬來", "my", "malaysia"],
    "🇮🇩 印尼":     ["印尼", "印度尼西亚", "id", "indonesia"],
    "🇮🇳 印度":     ["印度", "in", "india"],
    "🇹🇭 泰国":     ["泰国", "泰國", "th", "thailand"],
    "🇻🇳 越南":     ["越南", "vn", "vietnam"],
    "🇵🇭 菲律宾":   ["菲律宾", "菲律賓", "ph", "philippines"],
    "🇩🇪 德国":     ["德国", "德國", "de", "germany"],
    "🇬🇧 英国":     ["英国", "英國", "uk", "united kingdom"],
    "🇫🇷 法国":     ["法国", "法國", "fr", "france"],
    "🇨🇦 加拿大":   ["加拿大", "ca", "canada"],
    "🇧🇷 巴西":     ["巴西", "br", "brazil"],
    "🇹🇷 土耳其":   ["土耳其", "tr", "turkey", "turkiye"],
    "🇦🇺 澳大利亚":  ["澳大利亚", "澳洲", "au", "australia"],
    "🇷🇺 俄罗斯":   ["俄罗斯", "俄羅斯", "ru", "russia"],
    "🇳🇱 荷兰":     ["荷兰", "荷蘭", "nl", "netherlands"],
    "🇦🇷 阿根廷":   ["阿根廷", "ar", "argentina"],
}
 
PRIORITY_REGIONS = [
    "🇸🇬 新加坡", "🇭🇰 香港", "🇺🇸 美国", "🇯🇵 日本", "🇹🇼 台湾", "🇰🇷 韩国",
]
 
SOUTHEAST_ASIA = frozenset([
    "🇲🇾 马来西亚", "🇮🇩 印尼", "🇮🇳 印度", "🇹🇭 泰国", "🇻🇳 越南", "🇵🇭 菲律宾",
])
 
OTHER_REGIONS = frozenset([
    "🇩🇪 德国", "🇬🇧 英国", "🇫🇷 法国", "🇨🇦 加拿大", "🇧🇷 巴西",
    "🇹🇷 土耳其", "🇦🇺 澳大利亚", "🇷🇺 俄罗斯", "🇳🇱 荷兰", "🇦🇷 阿根廷",
])
 
# 默认直连端口（SSH 等不适合走代理的端口）
DEFAULT_DIRECT_PORTS: list[int] = [22]
 
# GitHub 相关域名（强制走代理，防止被墙）
DEFAULT_GITHUB_DOMAINS: list[str] = [
    "github.com",
    "githubusercontent.com",
    "githubassets.com",
    "ghcr.io",
]
 
 
# ─────────────────────────────────────────────────────────────────────────────
# 数据类
# ─────────────────────────────────────────────────────────────────────────────
 
@dataclass
class ConvertResult:
    """转换结果"""
    outbounds: list[dict]
    skipped: list[tuple[str, str]]       # (tag, reason)
    region_map: dict[str, list[str]]     # region → [tag, ...]
 
    @property
    def total(self) -> int:
        return len(self.outbounds)
 
    @property
    def regions(self) -> list[str]:
        return [r for r in self.region_map if r != "🌐 其他"]
 
 
# ─────────────────────────────────────────────────────────────────────────────
# 协议转换函数（模块私有）
# ─────────────────────────────────────────────────────────────────────────────
 
def _convert_shadowsocks(p: dict) -> dict:
    return {
        "type": "shadowsocks",
        "tag": p["name"],
        "server": p["server"],
        "server_port": int(p["port"]),
        "method": p["cipher"],
        "password": str(p["password"]),
        "udp_fragment": True,
    }
 
 
def _convert_vmess(p: dict) -> dict:
    ob: dict = {
        "type": "vmess",
        "tag": p["name"],
        "server": p["server"],
        "server_port": int(p["port"]),
        "uuid": p["uuid"],
        "alter_id": int(p.get("alterId", 0)),
        "security": p.get("cipher", "auto"),
    }
    network = p.get("network", "tcp")
    if str(p.get("tls", "false")).lower() == "true":
        ob["tls"] = {
            "enabled": True,
            "server_name": p.get("servername") or p.get("sni") or p["server"],
        }
    if network == "ws":
        ws = p.get("ws-opts", {})
        ob["transport"] = {
            "type": "ws",
            "path": ws.get("path", "/"),
            "headers": ws.get("headers", {}),
        }
    elif network == "grpc":
        ob["transport"] = {
            "type": "grpc",
            "service_name": p.get("grpc-opts", {}).get("grpc-service-name", ""),
        }
    return ob
 
 
def _convert_trojan(p: dict) -> dict:
    ob: dict = {
        "type": "trojan",
        "tag": p["name"],
        "server": p["server"],
        "server_port": int(p["port"]),
        "password": str(p["password"]),
        "tls": {
            "enabled": True,
            "server_name": p.get("sni") or p["server"],
            "insecure": bool(p.get("skip-cert-verify", False)),
        },
    }
    network = p.get("network", "tcp")
    if network == "ws":
        ob["transport"] = {
            "type": "ws",
            "path": p.get("ws-opts", {}).get("path", "/"),
        }
    elif network == "grpc":
        ob["transport"] = {
            "type": "grpc",
            "service_name": p.get("grpc-opts", {}).get("grpc-service-name", ""),
        }
    return ob
 
 
def _convert_vless(p: dict) -> dict:
    ob: dict = {
        "type": "vless",
        "tag": p["name"],
        "server": p["server"],
        "server_port": int(p["port"]),
        "uuid": p["uuid"],
        "flow": p.get("flow", ""),
    }
    reality = p.get("reality-opts", {})
    tls_enabled = str(p.get("tls", "false")).lower() == "true"
 
    if reality:
        ob["tls"] = {
            "enabled": True,
            "server_name": p.get("servername") or p.get("sni") or p["server"],
            "utls": {
                "enabled": True,
                "fingerprint": p.get("client-fingerprint", "chrome"),
            },
            "reality": {
                "enabled": True,
                "public_key": reality.get("public-key", ""),
                "short_id": reality.get("short-id", ""),
            },
        }
    elif tls_enabled:
        ob["tls"] = {
            "enabled": True,
            "server_name": p.get("servername") or p.get("sni") or p["server"],
            "insecure": bool(p.get("skip-cert-verify", False)),
        }
 
    network = p.get("network", "tcp")
    if network == "ws":
        ob["transport"] = {
            "type": "ws",
            "path": p.get("ws-opts", {}).get("path", "/"),
        }
    elif network == "grpc":
        ob["transport"] = {
            "type": "grpc",
            "service_name": p.get("grpc-opts", {}).get("grpc-service-name", ""),
        }
    elif network == "http":
        ob["transport"] = {"type": "http"}
    return ob
 
 
def _convert_hysteria2(p: dict) -> dict:
    return {
        "type": "hysteria2",
        "tag": p["name"],
        "server": p["server"],
        "server_port": int(p["port"]),
        "password": str(p.get("password", p.get("auth", ""))),
        "tls": {
            "enabled": True,
            "server_name": p.get("sni") or p["server"],
            "insecure": bool(p.get("skip-cert-verify", False)),
        },
    }
 
 
_CONVERTERS: dict = {
    "ss":        _convert_shadowsocks,
    "vmess":     _convert_vmess,
    "trojan":    _convert_trojan,
    "vless":     _convert_vless,
    "hysteria2": _convert_hysteria2,
    "hy2":       _convert_hysteria2,
}
 
 
# ─────────────────────────────────────────────────────────────────────────────
# 核心转换类
# ─────────────────────────────────────────────────────────────────────────────
 
class ClashToSingboxConverter:
    """
    Clash 订阅 → sing-box 配置转换器
 
    基本用法::
 
        from clash2singbox.converter import ClashToSingboxConverter
 
        converter = ClashToSingboxConverter()
        config = converter.convert_url("https://your-sub-url")
 
        # 或从文件
        config = converter.convert_file(Path("sub.yaml"))
 
        # 带代理
        converter = ClashToSingboxConverter(proxy="http://127.0.0.1:7890")
        config = converter.convert_url("https://your-sub-url")
    """
 
    def __init__(
        self,
        proxy: Optional[str] = None,
        direct_ports: Optional[list[int]] = None,
        github_domains: Optional[list[str]] = None,
    ):
        """
        Args:
            proxy: 下载订阅时使用的 HTTP 代理，如 "http://127.0.0.1:7890"
            direct_ports: 需要直连的端口列表，默认 [22]（SSH）
            github_domains: 强制走代理的域名列表，默认为 GitHub 相关域名
        """
        self.proxy = proxy
        self.direct_ports: list[int] = (
            direct_ports if direct_ports is not None else DEFAULT_DIRECT_PORTS
        )
        self.github_domains: list[str] = (
            github_domains if github_domains is not None else DEFAULT_GITHUB_DOMAINS
        )
 
    # ── 公开方法 ──────────────────────────────────────────────────────────────
 
    def convert_url(self, url: str) -> dict:
        """从订阅 URL 下载并转换为 sing-box 配置"""
        raw = self._fetch(url)
        clash_cfg = self._parse_yaml(raw)
        return self._build(clash_cfg)
 
    def convert_file(self, path: Path) -> dict:
        """从本地 YAML 文件转换为 sing-box 配置"""
        raw = path.read_text(encoding="utf-8")
        clash_cfg = self._parse_yaml(raw)
        return self._build(clash_cfg)
 
    def convert_source(self, source: str) -> dict:
        """自动判断 source 是 URL 还是文件路径"""
        parsed = urlparse(source)
        if parsed.scheme in ("http", "https"):
            return self.convert_url(source)
        return self.convert_file(Path(source))
 
    def parse_proxies(self, proxies: list[dict]) -> ConvertResult:
        """
        仅转换节点列表，不构建完整配置。
        可用于需要自定义配置结构时复用节点转换逻辑。
        """
        outbounds: list[dict] = []
        skipped: list[tuple[str, str]] = []
        region_map: dict[str, list[str]] = {}
 
        for p in proxies:
            name = p.get("name", "")
            ptype = p.get("type", "").lower()
 
            if self._is_junk(name):
                skipped.append((name, "信息类条目"))
                continue
 
            converter_fn = _CONVERTERS.get(ptype)
            if not converter_fn:
                skipped.append((name, f"不支持的类型: {ptype}"))
                continue
 
            try:
                ob = converter_fn(p)
                # 清理空值字段
                ob = {k: v for k, v in ob.items() if v != "" and v is not None}
                outbounds.append(ob)
                region = self._detect_region(name)
                region_map.setdefault(region or "🌐 其他", []).append(name)
            except Exception as e:
                skipped.append((name, f"转换错误: {e}"))
 
        return ConvertResult(
            outbounds=outbounds,
            skipped=skipped,
            region_map=region_map,
        )
 
    def build_singbox_config(self, result: ConvertResult) -> dict:
        """根据 ConvertResult 构建完整 sing-box 配置"""
        outbounds = result.outbounds
        region_map = result.region_map
        all_tags = [ob["tag"] for ob in outbounds]
 
        # 自动选择：优先地区节点参与测速
        auto_tags: list[str] = []
        for region in PRIORITY_REGIONS:
            auto_tags.extend(region_map.get(region, []))
        if not auto_tags:
            auto_tags = all_tags[:20]
 
        # 构建地区 selector
        region_selectors: list[dict] = []
        selector_tags: list[str] = []
 
        for region in PRIORITY_REGIONS:
            tags = region_map.get(region, [])
            if not tags:
                continue
            region_selectors.append({
                "type": "selector",
                "tag": region,
                "outbounds": tags,
                "default": tags[0],
            })
            selector_tags.append(region)
 
        sea_tags: list[str] = []
        for r in SOUTHEAST_ASIA:
            sea_tags.extend(region_map.get(r, []))
        if sea_tags:
            region_selectors.append({
                "type": "selector",
                "tag": "🌏 东南亚",
                "outbounds": sea_tags,
                "default": sea_tags[0],
            })
            selector_tags.append("🌏 东南亚")
 
        other_tags: list[str] = []
        for r in OTHER_REGIONS:
            other_tags.extend(region_map.get(r, []))
        other_tags.extend(region_map.get("🌐 其他", []))
        if other_tags:
            region_selectors.append({
                "type": "selector",
                "tag": "🌍 其他地区",
                "outbounds": other_tags,
                "default": other_tags[0],
            })
            selector_tags.append("🌍 其他地区")
 
        top_outbounds = [
            {
                "type": "selector",
                "tag": "✈️ 节点选择",
                "outbounds": ["⚡ 自动选择"] + selector_tags + ["direct"],
                "default": "⚡ 自动选择",
            },
            {
                "type": "urltest",
                "tag": "⚡ 自动选择",
                "outbounds": auto_tags,
                "url": "https://www.gstatic.com/generate_204",
                "interval": "3m",
                "tolerance": 50,
            },
            *region_selectors,
            *outbounds,
            {"type": "direct", "tag": "direct"},
            {"type": "block",  "tag": "block"},
        ]
 
        # 构建路由规则
        route_rules: list[dict] = [
            {"network": "icmp", "outbound": "direct"},
        ]
 
        if self.direct_ports:
            route_rules.append({"port": self.direct_ports, "outbound": "direct"})
 
        route_rules += [
            {
                "type": "logical",
                "mode": "or",
                "rules": [{"protocol": "dns"}, {"port": 53}],
                "action": "hijack-dns",
            },
            {"ip_is_private": True, "outbound": "direct"},
            {"rule_set": ["geosite-category-ads-all"], "outbound": "block"},
            # GitHub 强制走代理（置于 geosite-cn 之前）
            {"domain_suffix": self.github_domains, "outbound": "✈️ 节点选择"},
            {"rule_set": ["geosite-cn", "geoip-cn"], "outbound": "direct"},
            {"rule_set": ["geosite-geolocation-!cn"], "outbound": "✈️ 节点选择"},
        ]
 
        return {
            "log": {"level": "info", "timestamp": True, "output": "/var/log/sing-box.log"},
 
            "dns": {
                "servers": [
                    {
                        "type": "https",
                        "tag": "dns-remote",
                        "server": "1.1.1.1",
                        "path": "/dns-query",
                        "domain_resolver": "dns-bootstrap",
                        "detour": "✈️ 节点选择",
                    },
                    {
                        "type": "https",
                        "tag": "dns-local",
                        "server": "223.5.5.5",
                        "path": "/dns-query",
                        "domain_resolver": "dns-bootstrap",
                        "detour": "direct",
                    },
                    {
                        "type": "udp",
                        "tag": "dns-bootstrap",
                        "server": "223.5.5.5",
                        "server_port": 53,
                    },
                ],
                "rules": [
                    {
                        "rule_set": ["geosite-cn"],
                        "action": "route",
                        "server": "dns-local",
                    },
                    {
                        "rule_set": ["geosite-geolocation-!cn"],
                        "action": "route",
                        "server": "dns-remote",
                    },
                ],
                "final": "dns-remote",
                "independent_cache": True,
            },
 
            "inbounds": [
                {
                    "type": "tun",
                    "tag": "tun-in",
                    "address": ["172.18.0.1/30", "fdfe:dcba:9876::1/126"],
                    "auto_route": True,
                    "strict_route": True,
                    "sniff": True,
                    "sniff_override_destination": False,
                },
                {
                    "type": "mixed",
                    "tag": "mixed-in",
                    "listen": "127.0.0.1",
                    "listen_port": 7890,
                    "sniff": True,
                },
            ],
 
            "outbounds": top_outbounds,
 
            "route": {
                "default_domain_resolver": "dns-local",
                "rules": route_rules,
                "rule_set": [
                    {
                        "tag": "geoip-cn",
                        "type": "remote",
                        "format": "binary",
                        "url": "https://raw.githubusercontent.com/SagerNet/sing-geoip/rule-set/geoip-cn.srs",
                        "download_detour": "✈️ 节点选择",
                        "update_interval": "7d",
                    },
                    {
                        "tag": "geosite-cn",
                        "type": "remote",
                        "format": "binary",
                        "url": "https://raw.githubusercontent.com/SagerNet/sing-geosite/rule-set/geosite-cn.srs",
                        "download_detour": "✈️ 节点选择",
                        "update_interval": "7d",
                    },
                    {
                        "tag": "geosite-geolocation-!cn",
                        "type": "remote",
                        "format": "binary",
                        "url": "https://raw.githubusercontent.com/SagerNet/sing-geosite/rule-set/geosite-geolocation-!cn.srs",
                        "download_detour": "✈️ 节点选择",
                        "update_interval": "7d",
                    },
                    {
                        "tag": "geosite-category-ads-all",
                        "type": "remote",
                        "format": "binary",
                        "url": "https://raw.githubusercontent.com/SagerNet/sing-geosite/rule-set/geosite-category-ads-all.srs",
                        "download_detour": "✈️ 节点选择",
                        "update_interval": "7d",
                    },
                ],
                "final": "✈️ 节点选择",
                "auto_detect_interface": True,
            },
 
            "experimental": {
                "cache_file": {
                    "enabled": True,
                    "path": "cache.db",
                    "store_fakeip": False,
                },
                "clash_api": {
                    "external_controller": "127.0.0.1:9090",
                    "external_ui": "ui",
                    "external_ui_download_url": "https://github.com/MetaCubeX/metacubexd/archive/gh-pages.tar.gz",
                    "external_ui_download_detour": "✈️ 节点选择",
                    "secret": "",
                },
            },
        }
 
    # ── 内部方法 ──────────────────────────────────────────────────────────────
 
    def _fetch(self, url: str) -> str:
        resp = httpx.get(
            url,
            follow_redirects=True,
            timeout=30,
            headers={"User-Agent": "clash"},
            proxy=self.proxy,
        )
        resp.raise_for_status()
        return resp.text
 
    def _build(self, clash_cfg: dict) -> dict:
        proxies = clash_cfg.get("proxies", [])
        if not proxies:
            raise ValueError("未找到任何节点 (proxies 字段为空)")
        result = self.parse_proxies(proxies)
        return self.build_singbox_config(result)
 
    @staticmethod
    def _parse_yaml(content: str) -> dict:
        result = yaml.safe_load(content)
        if not isinstance(result, dict):
            raise ValueError("YAML 内容不是有效的 Clash 配置")
        return result
 
    @staticmethod
    def _is_junk(tag: str) -> bool:
        tag_lower = tag.lower()
        return any(kw in tag_lower for kw in JUNK_KEYWORDS)
 
    @staticmethod
    def _detect_region(tag: str) -> Optional[str]:
        tag_lower = tag.lower()
        for region, keywords in REGION_MAP.items():
            if any(kw in tag_lower for kw in keywords):
                return region
        return None
    