"""抽卡师的魔法 - 安装版启动入口（快捷方式以 pythonw.exe 无控制台窗口启动）。

启动流程：
1. 导入 runtime_env 触发防拷贝校验（未通过安装包安装 → 弹窗报错退出）
2. 首次启动引导：确保 config.json 存在，生成随机 JWT 密钥（不使用开发默认密钥）
3. 日志全部写文件（pythonw 下无控制台输出，标准输出为 None）
4. 端口预检：服务已运行 → 直接打开浏览器退出（防重复启动）
5. 后台线程轮询健康检查，就绪后自动打开浏览器
6. uvicorn 启动（use_colors=False：pythonw 下 stdout 为 None，默认着色会静默崩溃）
"""
import logging
import secrets
import socket
import sys
import threading
import webbrowser
from pathlib import Path

# 关键：内嵌 Python 的 python312._pth 会接管 sys.path，不会自动加入脚本所在目录，
# 必须先手动把 backend 目录加入 sys.path，否则 import app 会报 ModuleNotFoundError
# （pythonw 无控制台，该报错会静默吞掉，表现为「双击没反应」）。
_BACKEND_DIR = str(Path(__file__).resolve().parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# 必须最先导入：触发防拷贝安装校验（未通过则弹窗退出）
import app.runtime_env as runtime_env  # noqa: F401

APP_HOST = "127.0.0.1"
APP_PORT = 8000
APP_URL = f"http://{APP_HOST}:{APP_PORT}"


def _bootstrap_config() -> None:
    """首次启动引导：确保 config.json 存在，生成随机 JWT 密钥，并写入默认模型配置。"""
    if not runtime_env.IS_INSTALLED:
        return
    cfg = runtime_env.read_json(runtime_env.CONFIG_PATH)
    changed = False
    if not cfg.get("jwt_secret"):
        cfg["jwt_secret"] = secrets.token_hex(32)
        changed = True
    if not cfg.get("platform"):
        cfg["platform"] = "openrouter"
        changed = True
    if not cfg.get("model"):
        cfg["model"] = "google/gemini-3.7-flash"
        changed = True
    # api_key 为密钥，不写入源码；由「一键导入配置」工具或管理端「模型配置」填写
    if "reasoning_enabled" not in cfg:
        cfg["reasoning_enabled"] = False
        changed = True
    if changed:
        runtime_env.write_json(runtime_env.CONFIG_PATH, cfg)
        logging.info("已生成默认配置")


def _setup_logging() -> None:
    """日志写文件（pythonw 无控制台，必须落盘才可见）。"""
    runtime_env.LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(runtime_env.LOG_DIR / "app.log", encoding="utf-8")],
    )


def _port_in_use() -> bool:
    """探测 8000 端口是否已有服务（防重复启动）。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((APP_HOST, APP_PORT)) == 0


def _open_browser_when_ready() -> None:
    """后台线程：轮询健康检查，服务就绪后自动打开浏览器。"""
    import time
    import urllib.request

    for _ in range(30):  # 最多等待 30 秒
        try:
            with urllib.request.urlopen(f"{APP_URL}/api/health", timeout=1) as resp:
                if resp.status == 200:
                    webbrowser.open(APP_URL)
                    return
        except Exception:
            time.sleep(1)
    logging.warning("等待服务就绪超时，请手动访问 %s", APP_URL)


def main() -> None:
    _setup_logging()
    _bootstrap_config()
    logging.info("应用启动：%s", runtime_env.INSTALL_DIR)

    # 端口预检：已在运行 → 直接打开浏览器退出
    if _port_in_use():
        logging.info("检测到服务已在运行，直接打开浏览器")
        webbrowser.open(APP_URL)
        return

    import uvicorn

    from app.main import app

    threading.Thread(target=_open_browser_when_ready, daemon=True).start()
    # pythonw 下 stdout/stderr 为 None：use_colors=False + 日志走文件
    uvicorn.run(app, host=APP_HOST, port=APP_PORT, log_config=None, use_colors=False)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        try:
            _setup_logging()
        except Exception:
            pass
        logging.exception("应用启动失败")
        # pythonw 下异常是静默的：弹窗提示用户查看日志
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                None,
                f"应用启动失败，请查看日志：{runtime_env.LOG_DIR / 'app.log'}",
                "抽卡师的魔法",
                0x10,
            )
        except Exception:
            sys.exit(1)
