#!/usr/bin/env bash
# ============================================================
# 抽卡师的魔法 - macOS 打包脚本
# 运行环境：macOS（本地 Mac 或 GitHub Actions 的 macOS runner）
# 产物：dist/抽卡师的魔法-<版本>.pkg（含防拷贝 postinstall）
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

APP_NAME="抽卡师的魔法"
BUNDLE_ID="com.gacha.magic"
VERSION="${VERSION:-1.0.0}"

# ---- 便携版 Python（python-build-standalone）----
# 版本固定，地址已确认可用（2026-08-14 发布，Python 3.12.14）
PY_RELEASE="20260814"
PY_VERSION="3.12.14"
ARCH=$(uname -m)
if [ "$ARCH" = "x86_64" ]; then
  PY_ARCH="x86_64"
else
  PY_ARCH="aarch64"
fi
PY_TAR="cpython-${PY_VERSION}+${PY_RELEASE}-${PY_ARCH}-apple-darwin-install_only.tar.gz"
PY_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PY_RELEASE}/${PY_TAR}"

BUILD_DIR="build"
PY_DIR="$BUILD_DIR/python"
APP_DIR="$BUILD_DIR/${APP_NAME}.app"

log() { echo -e "\n\033[1;32m[build]\033[0m $*"; }
die() { echo -e "\033[1;31m[build] 错误：$*\033[0m" >&2; exit 1; }

# 1. 前置检查
command -v pkgbuild >/dev/null || die "缺少 pkgbuild（需在 macOS 上运行）"

# 2. 前端产物（由工作流/本地预先 npm run build 生成）
log "检查前端产物"
[ -f ../../frontend/dist/index.html ] || die "前端未构建：请先 cd ../../frontend && npm install && npm run build"

# 3. 下载并解压便携版 Python
log "准备便携版 Python (${PY_ARCH})"
mkdir -p "$BUILD_DIR"
if [ ! -x "$PY_DIR/bin/python3" ]; then
  curl -fL --retry 3 "$PY_URL" -o "$BUILD_DIR/$PY_TAR" || die "Python 下载失败：$PY_URL"
  rm -rf "$PY_DIR"
  mkdir -p "$PY_DIR"
  tar -xzf "$BUILD_DIR/$PY_TAR" -C "$PY_DIR" --strip-components=1
fi
PY_BIN="$PY_DIR/bin/python3"
"$PY_BIN" --version || die "Python 运行失败"

# 4. 确保 pip 可用并安装依赖（装进便携版 Python 自带 site-packages）
log "安装依赖到运行时"
"$PY_BIN" -m pip --version >/dev/null 2>&1 || "$PY_BIN" -m ensurepip --upgrade
"$PY_BIN" -m pip install --upgrade pip >/dev/null 2>&1 || true
"$PY_BIN" -m pip install -r ../requirements-win.txt || die "依赖安装失败"

# 5. 装配 .app 包
log "装配 .app"
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources/backend" "$APP_DIR/Contents/Resources/frontend"
cp Info.plist "$APP_DIR/Contents/Info.plist"
cp launcher.sh "$APP_DIR/Contents/MacOS/launcher"
chmod +x "$APP_DIR/Contents/MacOS/launcher"

# 后端（排除开发数据/文档/缓存）
(cd ../../backend && find app -name "__pycache__" -prune -o -name "data" -prune -o -name "source" -prune -o -type f -print) | while read -r f; do
  mkdir -p "$APP_DIR/Contents/Resources/backend/$(dirname "$f")"
  cp "../../backend/$f" "$APP_DIR/Contents/Resources/backend/$f"
done
cp ../../backend/run_app.pyw "$APP_DIR/Contents/Resources/backend/run_app.pyw"

# 前端
cp -r ../../frontend/dist "$APP_DIR/Contents/Resources/frontend/dist"

# 便携版 Python 运行时
cp -r "$PY_DIR" "$APP_DIR/Contents/Resources/runtime"

# 6. 生成 .pkg（postinstall 写入防拷贝标记 + plist）
log "生成 .pkg"
mkdir -p dist build/pkg_root
rm -rf build/pkg_root && mkdir -p build/pkg_root
cp -r "$APP_DIR" "build/pkg_root/${APP_NAME}.app"
chmod +x postinstall.sh
pkgbuild \
  --root "build/pkg_root" \
  --scripts "$(pwd)" \
  --identifier "$BUNDLE_ID" \
  --version "$VERSION" \
  --install-location /Applications \
  "dist/${APP_NAME}-${VERSION}-${PY_ARCH}.pkg" \
  || die "pkgbuild 失败"

log "构建完成：dist/${APP_NAME}-${VERSION}-${PY_ARCH}.pkg"
ls -lh "dist/"*.pkg
