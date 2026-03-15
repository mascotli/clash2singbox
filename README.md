# clash2singbox

将 Clash 订阅转换为 sing-box 1.13+ 配置的命令行工具。

## 安装

```bash
pip install clash2singbox
```

或通过 uv：

```bash
uv pip install clash2singbox
```

## 用法

```bash
# 从订阅 URL 转换
clash2singbox convert "https://your-sub-url" -o config.json

# 通过代理下载订阅
clash2singbox convert "https://your-sub-url" -o config.json -p http://127.0.0.1:7890

# 从本地文件转换
clash2singbox convert sub.yaml -o config.json

# 自定义直连端口（默认 22）
clash2singbox convert "https://your-sub-url" --direct-ports 22,2222

# 直接打印到终端
clash2singbox convert "https://your-sub-url" --print

# 强制覆盖
clash2singbox convert "https://your-sub-url" -o config.json -f

# 检查依赖
clash2singbox check-deps

# 查看版本
clash2singbox version
```

## 支持的协议

- Shadowsocks
- VMess
- Trojan
- VLESS（含 Reality）
- Hysteria2

## 特性

- 自动识别 20+ 地区，按地区生成节点分组
- 自动过滤信息类条目（剩余流量、到期时间等）
- SSH（22端口）默认直连，避免 TUN 模式干扰
- GitHub 相关域名强制走代理
- 生成配置完全兼容 sing-box 1.13+，无 deprecated 警告
