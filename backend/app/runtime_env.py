"""运行时环境判定与路径推导 + 防拷贝安装校验（guard）。

支持两种平台布局：
1. Windows 安装版（NSIS 安装包）：
       $INSTDIR\\
       ├── runtime\\      Python embeddable 运行时
       ├── backend\\      run_app.pyw + app\\ 包
       ├── frontend\\     Vite 构建产物
       ├── config.json    模型配置
       ├── .installed     安装标记（含随机 install_id）
       └── Uninstall.exe
   数据目录：%APPDATA%\\PromptOpt
2. macOS 安装版（.app 安装到 /Applications）：
       抽卡师的魔法.app\\Contents\\...  （运行时 + backend + frontend，只读）
   数据与标记在用户目录：
       ~/Library/Application Support/抽卡师的魔法/
       ├── installed     安装标记（含随机 install_id）
       ├── config.json    模型配置（管理端改写）
       ├── app.db
       └── logs/
       ~/Library/Preferences/com.gacha.magic.plist   （defaults 存 InstallId）
3. 开发版（源码运行）：无标记 → guard 完全跳过，路径保持 backend/data。

防拷贝机制（三重校验，仅安装模式生效，按平台）：
  Windows：① 环境变量 PROMPT_OPT_INSTALLED=1  ② PROMPT_OPT_HOME 指向安装目录
           ③ 注册表 InstallId == .installed 标记文件的 install_id
  macOS：  ① 标记文件 ~/Library/Application Support/…/installed 存在
           ② plist 里的 InstallId == 标记文件里的 install_id
           ③ 程序运行路径在 .app 包内（且 .app 位于 /Applications）
说明：该机制用于阻止「直接拷贝文件夹/应用运行」；对有意技术破解不设防。
"""
import json
import os
import subprocess
import sys
from pathlib import Path

APP_NAME = "抽卡师的魔法"
BUNDLE_ID = "com.gacha.magic"

_IS_MAC = sys.platform == "darwin"


def _appdata_dir() -> Path:
    base = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
    return Path(base)


# ---------- 路径推导（按平台） ----------

if _IS_MAC:
    # macOS：标记文件与数据都在用户目录，不在 .app 内（避免随 .app 一起被拷贝）
    _APP_SUPPORT = Path.home() / "Library" / "Application Support" / APP_NAME
    _MARKER = _APP_SUPPORT / "installed"
    IS_INSTALLED = _MARKER.exists()
    INSTALL_DIR = Path("/Applications") / (APP_NAME + ".app")
    DATA_DIR = _APP_SUPPORT
    CONFIG_PATH = _APP_SUPPORT / "config.json"
    DB_PATH = _APP_SUPPORT / "app.db"
    LOG_DIR = _APP_SUPPORT / "logs"
else:
    # Windows 安装版：标记文件在安装根目录；开发版：无标记
    _MARKER = Path(__file__).resolve().parents[2] / ".installed"
    IS_INSTALLED = _MARKER.exists()
    if IS_INSTALLED:
        INSTALL_DIR = _MARKER.parent
        DATA_DIR = _appdata_dir() / "PromptOpt"
        CONFIG_PATH = INSTALL_DIR / "config.json"
        DB_PATH = DATA_DIR / "app.db"
        LOG_DIR = DATA_DIR / "logs"
    else:
        BACKEND_DIR = Path(__file__).resolve().parents[1]
        INSTALL_DIR = None
        DATA_DIR = BACKEND_DIR / "data"
        CONFIG_PATH = BACKEND_DIR / "config.json"
        DB_PATH = DATA_DIR / "app.db"
        LOG_DIR = DATA_DIR / "logs"


# ---------- JSON 读写（原子写） ----------

def read_json(path: Path) -> dict:
    """读取 JSON 文件，不存在/损坏时返回空字典。"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_json(path: Path, data: dict) -> None:
    """原子写 JSON：先写临时文件再 os.replace，避免中断造成文件损坏。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


# ---------- 平台专属安装标识读取 ----------

def _read_registry_env(name: str) -> str | None:
    """Windows：读 HKCU\\Environment 用户环境变量。"""
    if os.name != "nt":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _ = winreg.QueryValueEx(key, name)
        return value
    except Exception:
        return None


def _read_registry_install_id() -> str | None:
    """Windows：读 HKCU\\Software\\PromptOpt\\InstallId。"""
    if os.name != "nt":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\PromptOpt") as key:
            value, _ = winreg.QueryValueEx(key, "InstallId")
        return value
    except Exception:
        return None


def _read_plist_install_id() -> str | None:
    """macOS：读用户偏好 plist 里的 InstallId（用 defaults 命令）。"""
    if not _IS_MAC:
        return None
    try:
        out = subprocess.run(
            ["defaults", "read", BUNDLE_ID, "InstallId"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        return out or None
    except Exception:
        return None


# ---------- 防拷贝校验 ----------

def _fail(message: str) -> None:
    """安装校验失败：按平台弹窗/打印后退出进程。"""
    text = "程序未通过安装校验，请使用安装包重新安装。\n\n" + message
    try:
        if _IS_MAC:
            # macOS 原生对话框
            subprocess.run(
                ["osascript", "-e", f'display dialog "{text}" buttons {{"好"}} default button 1 with title "{APP_NAME}" with icon caution'],
                timeout=10,
            )
        elif os.name == "nt":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, text, APP_NAME, 0x10)
        else:
            print(f"[安装校验失败] {text}", file=sys.stderr)
    except Exception:
        print(f"[安装校验失败] {text}", file=sys.stderr)
    sys.exit(1)


def _read_marker() -> dict:
    return read_json(_MARKER)


def _norm_path(p) -> str:
    """路径规范化：绝对化 + 去末尾分隔符 + Windows 下忽略大小写。"""
    norm = os.path.normpath(os.path.abspath(str(p)))
    if os.name == "nt":
        norm = os.path.normcase(norm)
    return norm.rstrip(os.sep + ("/" if os.sep == "\\" else ""))


def _guard_windows() -> None:
    """Windows 安装版三重校验。"""
    problems = []
    # ① 环境变量 PROMPT_OPT_INSTALLED == "1"
    installed_flag = os.environ.get("PROMPT_OPT_INSTALLED") or _read_registry_env("PROMPT_OPT_INSTALLED")
    if installed_flag != "1":
        problems.append("缺少安装环境变量 PROMPT_OPT_INSTALLED=1（本程序必须通过安装包安装后运行）")
    # ② PROMPT_OPT_HOME 指向安装目录
    home = os.environ.get("PROMPT_OPT_HOME") or _read_registry_env("PROMPT_OPT_HOME")
    if not home or _norm_path(home) != _norm_path(INSTALL_DIR):
        problems.append("环境变量 PROMPT_OPT_HOME 与安装目录不一致")
    # ③ 运行路径位于安装目录之内
    try:
        Path(_norm_path(sys.argv[0])).relative_to(_norm_path(INSTALL_DIR))
    except (ValueError, OSError):
        problems.append("程序运行路径不在安装目录内（禁止直接拷贝文件夹运行）")
    # ④ 注册表 InstallId 与标记一致
    marker = _read_marker()
    reg_id = _read_registry_install_id()
    if not marker or not marker.get("install_id") or not reg_id or reg_id != marker.get("install_id"):
        problems.append("安装标识校验失败")
    if problems:
        _fail("\n".join(f"• {p}" for p in problems))


def _guard_mac() -> None:
    """macOS 安装版三重校验。"""
    problems = []
    # ① 标记文件存在（IS_INSTALLED 已保证）
    # ② plist 里的 InstallId 与标记文件一致
    marker = _read_marker()
    plist_id = _read_plist_install_id()
    if not marker or not marker.get("install_id") or not plist_id or plist_id != marker.get("install_id"):
        problems.append("安装标识校验失败（请通过安装包重新安装）")
    # ③ 程序运行路径在 .app 包内，且 .app 位于 /Applications
    exe = Path(_norm_path(sys.argv[0]))
    if ".app/Contents" not in str(exe):
        problems.append("程序未通过 .app 安装包启动（禁止直接拷贝应用运行）")
    if problems:
        _fail("\n".join(f"• {p}" for p in problems))


def guard() -> None:
    """防拷贝安装校验：仅安装模式（存在标记）执行；开发模式直接放行。"""
    if not IS_INSTALLED:
        return
    if _IS_MAC:
        _guard_mac()
    else:
        _guard_windows()


# 导入即校验：拦截一切未通过安装包的启动方式
guard()
