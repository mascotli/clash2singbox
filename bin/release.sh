#!/bin/bash
# release.sh — 版本发布脚本
# 用法: ./release.sh <version>
# 示例: ./release.sh 0.2.0
 
set -e
 
# ── 颜色 ──────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'
 
info()    { echo -e "${CYAN}▶ $*${NC}"; }
success() { echo -e "${GREEN}✓ $*${NC}"; }
warn()    { echo -e "${YELLOW}⚠ $*${NC}"; }
error()   { echo -e "${RED}✗ $*${NC}"; exit 1; }
 
# ── 参数检查 ──────────────────────────────────────────────────────────────────
VERSION=$1
 
if [ -z "$VERSION" ]; then
    echo -e "${BOLD}用法:${NC} ./release.sh <version>"
    echo -e "${BOLD}示例:${NC} ./release.sh 0.2.0"
    exit 1
fi
 
# 去掉开头的 v（允许用户输入 v0.2.0 或 0.2.0）
VERSION="${VERSION#v}"
TAG="v${VERSION}"
 
# ── 环境检查 ──────────────────────────────────────────────────────────────────
info "检查环境..."
 
command -v git  >/dev/null 2>&1 || error "未找到 git"
command -v uv   >/dev/null 2>&1 || error "未找到 uv，请先安装: curl -LsSf https://astral.sh/uv/install.sh | sh"
 
# 必须在 git 仓库根目录
git rev-parse --git-dir >/dev/null 2>&1 || error "当前目录不是 git 仓库"
 
# 检查是否有未提交的改动
if ! git diff --quiet || ! git diff --cached --quiet; then
    error "存在未提交的改动，请先 git add & commit"
fi
 
# 检查 tag 是否已存在
if git tag | grep -q "^${TAG}$"; then
    error "Tag ${TAG} 已存在"
fi
 
success "环境检查通过"
 
# ── 更新版本号 ────────────────────────────────────────────────────────────────
info "更新版本号到 ${BOLD}${VERSION}${NC}..."
 
# pyproject.toml
sed -i.bak "s/^version = \".*\"/version = \"${VERSION}\"/" pyproject.toml && rm pyproject.toml.bak
 
# src/clash2singbox/__init__.py
sed -i.bak "s/^__version__ = \".*\"/__version__ = \"${VERSION}\"/" src/clash2singbox/__init__.py && rm src/clash2singbox/__init__.py.bak
 
success "版本号已更新"
 
# ── 构建确认 ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}即将发布:${NC}"
echo -e "  版本:  ${CYAN}${TAG}${NC}"
echo -e "  提交:  $(git log --oneline -1)"
echo ""
read -r -p "确认发布? [y/N] " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    # 回滚版本号改动
    git checkout -- pyproject.toml src/clash2singbox/__init__.py
    warn "已取消，版本号改动已回滚"
    exit 0
fi
 
# ── 提交 & 打 Tag ─────────────────────────────────────────────────────────────
info "提交版本号改动..."
git add pyproject.toml src/clash2singbox/__init__.py
git commit -m "chore: bump version to ${VERSION}"
 
info "创建 tag ${TAG}..."
git tag "${TAG}"
 
info "推送到远程..."
git push
git push origin "${TAG}"
 
# ── 完成 ──────────────────────────────────────────────────────────────────────
echo ""
success "发布完成！"
echo -e "  GitHub Actions 正在构建 Release，稍后可在以下地址查看："
REMOTE=$(git remote get-url origin 2>/dev/null | sed 's/git@github.com:/https:\/\/github.com\//' | sed 's/\.git$//')
echo -e "  ${CYAN}${REMOTE}/releases/tag/${TAG}${NC}"