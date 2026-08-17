#!/usr/bin/env bash
# ============================================================
# 提示词迭代优化系统 - 一键构建脚本（WSL / Linux 内运行）
# 产物：dist/PromptOpt-Setup-<版本>.exe（Windows NSIS 安装包）
#
# 构建内容：
#   1. 前端：npm run build → frontend/dist
#   2. 运行时：Python 3.12.10 embeddable（win_amd64）+ 全量依赖
#   3. 后端：backend/app + run_app.pyw
#   4. NSIS：安装向导（模型配置录入、用户环境变量、防拷贝标记、快捷方式）
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

PRODUCT_VERSION="${PRODUCT_VERSION:-1.0.0}"
PYTHON_EMBED_ZIP="python-3.12.10-embed-amd64.zip"
PYTHON_EMBED_URL="https://www.python.org/ftp/python/3.12.10/${PYTHON_EMBED_ZIP}"
# 官方源首次下载时固化的 SHA256（python.org HTTPS）
PYTHON_EMBED_SHA256="4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3"
PIP="/home/cyk/miniconda3/envs/langchain/bin/python -m pip"

log() { echo -e "\n\033[1;32m[build]\033[0m $*"; }
die() { echo -e "\033[1;31m[build] 错误：$*\033[0m" >&2; exit 1; }

# ---------- 1. 前置检查 ----------
log "1/8 前置工具检查"
for tool in makensis curl unzip node npm; do
  command -v "$tool" >/dev/null || die "缺少工具：$tool"
done
[ -d ../backend/app ] || die "找不到 ../backend/app"
[ -d ../frontend ] || die "找不到 ../frontend"

# ---------- 2. 前端构建 ----------
log "2/8 构建前端 (npm run build)"
(cd ../frontend && npm run build >/dev/null) || die "前端构建失败"
[ -f ../frontend/dist/index.html ] || die "前端产物缺失 frontend/dist/index.html"

# ---------- 3. 下载并校验 Python embeddable ----------
log "3/8 准备 Python 3.12.10 embeddable 运行时"
mkdir -p build dist
if [ -f "build/${PYTHON_EMBED_ZIP}" ] && echo "${PYTHON_EMBED_SHA256}  build/${PYTHON_EMBED_ZIP}" | sha256sum -c --quiet 2>/dev/null; then
  log "   复用已缓存的 ${PYTHON_EMBED_ZIP}（哈希校验通过）"
else
  log "   下载 ${PYTHON_EMBED_URL}"
  curl -fL --retry 3 -o "build/${PYTHON_EMBED_ZIP}" "$PYTHON_EMBED_URL" || die "下载失败"
  echo "${PYTHON_EMBED_SHA256}  build/${PYTHON_EMBED_ZIP}" | sha256sum -c --quiet || die "SHA256 校验失败，请检查下载源"
fi

# ---------- 4. 解压运行时并修补 python312._pth ----------
log "4/8 解压运行时 + 启用 site-packages"
rm -rf build/runtime
unzip -q "build/${PYTHON_EMBED_ZIP}" -d build/runtime
# embeddable 默认不加载 site-packages：取消注释 import site 并追加依赖目录
python3 - <<'EOF'
from pathlib import Path
pth = Path("build/runtime/python312._pth")
content = pth.read_text(encoding="utf-8")
content = content.replace("#import site", "import site")
if "Lib\\site-packages" not in content:
    content = content.rstrip("\n") + "\nLib\\site-packages\n"
pth.write_text(content, encoding="utf-8")
print(content)
EOF

# ---------- 5. 下载并安装 Windows 依赖（win_amd64 cp312 wheel） ----------
log "5/8 下载 win_amd64 依赖 wheel"
rm -rf build/wheels && mkdir -p build/wheels
$PIP download --only-binary=:all: --platform win_amd64 --implementation cp \
  --python-version 3.12 --abi cp312 -r requirements-win.txt -d build/wheels >/dev/null \
  || die "wheel 下载失败（--only-binary 快速暴露无 Windows wheel 的包）"

log "6/8 安装依赖到运行时（解包 wheel）"
# 说明：pip install --target 只接受与当前解释器（Linux）兼容的 wheel，
# 无法安装 win_amd64 跨平台包；wheel 本质是 zip 归档，直接解包到 site-packages
# （跳过 .data 目录：控制台脚本等运行时不依赖）
SITE="build/runtime/Lib/site-packages"
mkdir -p "$SITE"
python3 - <<'EOF'
import glob, os, zipfile

target = "build/runtime/Lib/site-packages"
count = 0
for whl in sorted(glob.glob("build/wheels/*.whl")):
    pkg = os.path.basename(whl).split("-")[0]
    with zipfile.ZipFile(whl) as z:
        for member in z.namelist():
            # 跳过目录项与 .data 子树（scripts/headers 等运行时不依赖）
            if member.endswith("/") or ".data/" in member:
                continue
            z.extract(member, target)
    count += 1
print(f"    共解包 {count} 个 wheel")
EOF
[ -d "$SITE/langchain" ] || die "运行时缺少 langchain 包"
[ -f "$SITE/langchain/__init__.py" ] || die "langchain 解包不完整"

# ---------- 6. 组装安装布局 ----------
log "7/8 组装安装目录布局"
rm -rf build/staging && mkdir -p build/staging
# 后端代码（排除开发期数据/需求文档/缓存）
mkdir -p build/staging/backend
cp ../backend/run_app.pyw build/staging/backend/
(cd ../backend && find app -name "__pycache__" -prune -o -name "data" -prune -o -name "source" -prune -o -type f -print) | while read -r f; do
  mkdir -p "build/staging/backend/$(dirname "$f")"
  cp "../backend/$f" "build/staging/backend/$f"
done
# 前端构建产物（保持 frontend/dist 层级，与后端 SPA 服务路径一致）
mkdir -p build/staging/frontend
cp -r ../frontend/dist build/staging/frontend/dist
# Python 运行时
cp -r build/runtime build/staging/runtime
rm -rf build/staging/runtime/__pycache__ build/staging/runtime/Lib/site-packages/__pycache__
log "   布局检查："
find build/staging -maxdepth 2 -type d | sort | sed 's/^/     /'

# ---------- 7. 编译 NSIS 安装包 ----------
# 说明：API Key 仅由管理员在管理端填写，不随安装包携带；
# 安装包只安装程序，模型平台/名称/地址/Key 均由管理员安装后在管理界面配置。
log "8/8 编译 NSIS 安装包 → dist/PromptOpt-Setup-${PRODUCT_VERSION}.exe"
mkdir -p dist
makensis -INPUTCHARSET UTF8 \
  -DPRODUCT_VERSION="${PRODUCT_VERSION}" -DINPUT_STAGING=build/staging \
  installer.nsi \
  || die "makensis 编译失败"
EXE="dist/PromptOpt-Setup-${PRODUCT_VERSION}.exe"
[ -f "$EXE" ] || die "未找到产物 $EXE"
log "构建完成："
ls -lh "$EXE"
echo "SHA256: $(sha256sum "$EXE" | awk '{print $1}')"
