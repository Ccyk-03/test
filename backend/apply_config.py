#!/usr/bin/env python3
"""一键导入配置脚本：读取 key=value 文件，更新 API Key 与 s/g 系列指令。

用法：
    python apply_config.py <配置文件路径>
    python apply_config.py                 # 不带参数时，默认读取同目录下的 config_import.txt

文件格式（每行一个 key=value，# 开头为注释，空行忽略；只写需要更新的项即可，未写的不动）：
    apikey=sk-xxxxx
    s1=……（单元 1、2 指令）
    s2=……（单元 3-6 指令）
    s3=……（修改提示词指令）
    g1=……（竖屏版单元 1、2）
    g2=……（竖屏版单元 3-6）
    g3=……（竖屏版修改）

多行内容：值里用 \\n 表示换行，例如 s1=第一行\\n第二行\\n第三行。

生效说明：
    - 指令（s/g）每次调用都会从数据库现读，更新后【立即生效】；
    - API Key 存在模型单例缓存里，需【重启应用】后生效（或在应用启动前运行本脚本）。
"""
import sys
from datetime import datetime
from pathlib import Path

# 关键：内嵌 Python 的 ._pth 不会自动把脚本目录加入 sys.path，
# 先手动加入，保证 import app 可用（与 run_app.pyw 同理）。
_BACKEND_DIR = str(Path(__file__).resolve().parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app import model_config  # noqa: E402  触发 runtime_env 路径推导
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import GlobalConfig  # noqa: E402

# 文件字段 → 数据库 global_config 的 key
FIELD_KEYS = {
    "s1": "global_instruction_s1",
    "s2": "global_instruction_s2",
    "s3": "global_instruction_s3",
    "g1": "global_instruction_g1",
    "g2": "global_instruction_g2",
    "g3": "global_instruction_g3",
}


def parse_file(path: str) -> dict:
    """解析 key=value 文件，返回非空字段字典（值里的 \\n 还原为真实换行）。"""
    data = {}
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n").strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if key and value:  # 空值视为「不更新」
                data[key] = value.replace("\\n", "\n")
    return data


def _mask(key: str) -> str:
    if len(key) <= 10:
        return "*" * len(key)
    return f"{key[:6]}***{key[-4:]}"


def apply(data: dict) -> None:
    """把文件内容写入 config.json（api_key）与 global_config 表（s/g 指令）。"""
    # 1. API Key → config.json（复用 model_config，路径/合并逻辑都自动正确）
    if "apikey" in data:
        model_config.save_model_config({"api_key": data["apikey"]})
        print(f"[config.json] api_key 已更新 → {_mask(data['apikey'])}")

    # 2. 指令 → SQLite global_config 表
    if any(k in data for k in FIELD_KEYS):
        Base.metadata.create_all(bind=engine)  # 确保表存在（首次/全新数据库也安全）
        db = SessionLocal()
        try:
            for field, db_key in FIELD_KEYS.items():
                if field not in data:
                    continue
                row = db.query(GlobalConfig).filter(GlobalConfig.key == db_key).first()
                if row is None:
                    row = GlobalConfig(key=db_key, value=data[field])
                    db.add(row)
                else:
                    row.value = data[field]
                row.updated_at = datetime.now()
                print(f"[global_config] {field} 已更新（{len(data[field])} 字）")
            db.commit()
        finally:
            db.close()


def main() -> int:
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        path = str(Path(__file__).resolve().parent / "config_import.txt")

    if not Path(path).exists():
        print(f"❌ 配置文件不存在：{path}")
        return 1

    data = parse_file(path)
    if not data:
        print("❌ 配置文件里没有可用的 key=value 项")
        return 1

    print(f"读取到 {len(data)} 项：{', '.join(sorted(data))}")
    apply(data)
    print("✅ 更新完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
