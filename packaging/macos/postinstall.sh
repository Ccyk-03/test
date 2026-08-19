#!/bin/bash
# macOS .pkg 安装器 postinstall 脚本：安装时写入防拷贝标记。
# 只有通过安装包安装，才会执行本脚本 → 生成 install_id 并写入两处：
#   1) ~/Library/Application Support/抽卡师的魔法/installed（标记文件）
#   2) ~/Library/Preferences/com.gacha.magic.plist（defaults，存 InstallId）
# 直接拷贝 .app 到别的 Mac 时，这两处都不存在 → 程序拒绝运行。

APP_NAME="抽卡师的魔法"
BUNDLE_ID="com.gacha.magic"
APP_SUPPORT="$HOME/Library/Application Support/$APP_NAME"

# 生成随机 install_id（uuid 去掉横线）
INSTALL_ID=$(uuidgen | tr -d '-' | cut -c1-24)

# 写入标记文件
mkdir -p "$APP_SUPPORT"
cat > "$APP_SUPPORT/installed" <<EOF
{"install_id":"$INSTALL_ID","installed_at":"$(date '+%Y-%m-%d %H:%M:%S')"}
EOF

# 写入用户偏好 plist
defaults write "$BUNDLE_ID" InstallId "$INSTALL_ID"

# 在桌面创建快捷方式（符号链接指向 /Applications 里的 .app，双击即可打开，与 Windows 桌面图标体验一致）
APP_PATH="/Applications/$APP_NAME.app"
DESKTOP_LINK="$HOME/Desktop/$APP_NAME.app"
if [ -e "$APP_PATH" ]; then
  ln -sf "$APP_PATH" "$DESKTOP_LINK" 2>/dev/null || true
fi

echo "[postinstall] 安装标记已写入：$APP_SUPPORT/installed"
exit 0
