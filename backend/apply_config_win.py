#!/usr/bin/env python3
"""Windows 版配置导入脚本（可放在任意目录运行，仅用 Python 标准库）。

用法（在任意目录）：
    python apply_config_win.py <配置文件>       # 指定文件
    python apply_config_win.py                  # 默认读同目录 config_import.txt

会自动定位：
    - 配置  ：脚本同目录的 config.json（脚本应放在安装目录内，如 D:\\test1）
    - 数据库：%APPDATA%\\PromptOpt\\app.db（数据目录，不在安装目录内）

文件格式（每行 key=value，# 注释，空行忽略；多行用 \\n 表示换行）：
    apikey=sk-xxxx
    s1=第一行\\n第二行
    s2=...
    s3=...
    g1=...
    g2=...
    g3=...
只写要更新的项，未写的不动。指令立即生效；API Key 需重启应用后生效。
"""
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

FIELD_KEYS = {
    "s1": "global_instruction_s1",
    "s2": "global_instruction_s2",
    "s3": "global_instruction_s3",
    "g1": "global_instruction_g1",
    "g2": "global_instruction_g2",
    "g3": "global_instruction_g3",
}


def _config_path() -> Path:
    """优先脚本同目录的 config.json（脚本放在安装目录内，如 D:\\test1）；
    否则回落 PROMPT_OPT_HOME 环境变量，再回落默认安装目录。"""
    here = Path(__file__).resolve().parent
    if (here / "config.json").exists() or (here / ".installed").exists():
        return here / "config.json"
    home = os.environ.get("PROMPT_OPT_HOME")
    if home:
        return Path(home) / "config.json"
    local = os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
    return Path(local) / "Programs" / "PromptOpt" / "config.json"


def _db_path() -> Path:
    appdata = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
    return Path(appdata) / "PromptOpt" / "app.db"


def parse_file(path: str) -> dict:
    data = {}
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n").strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if key and value:
                data[key] = value.replace("\\n", "\n")
    return data


def _mask(key: str) -> str:
    return key if len(key) <= 10 else f"{key[:6]}***{key[-4:]}"


def apply(data: dict) -> None:
    # 1. API Key → config.json
    if "apikey" in data:
        cfg_path = _config_path()
        cfg = {}
        if cfg_path.exists():
            try:
                cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                cfg = {}
        cfg["api_key"] = data["apikey"]
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = cfg_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, cfg_path)
        print(f"[config.json] api_key 已更新 → {_mask(data['apikey'])}")
        print(f"            路径：{cfg_path}")

    # 2. 指令 → SQLite global_config 表
    if any(k in data for k in FIELD_KEYS):
        db_path = _db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS global_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key VARCHAR(64) UNIQUE NOT NULL,
                    value TEXT NOT NULL,
                    updated_at DATETIME
                )
            """)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            for field, dbkey in FIELD_KEYS.items():
                if field not in data:
                    continue
                cur = conn.execute("SELECT id FROM global_config WHERE key=?", (dbkey,))
                if cur.fetchone() is None:
                    conn.execute(
                        "INSERT INTO global_config (key, value, updated_at) VALUES (?,?,?)",
                        (dbkey, data[field], now),
                    )
                else:
                    conn.execute(
                        "UPDATE global_config SET value=?, updated_at=? WHERE key=?",
                        (data[field], now, dbkey),
                    )
                print(f"[global_config] {field} 已更新（{len(data[field])} 字）")
            conn.commit()
            print(f"            路径：{db_path}")
        finally:
            conn.close()


def main() -> int:
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        path = str(Path(__file__).resolve().parent / "config_import.txt")
    if not Path(path).exists():
        print(f"配置文件不存在：{path}")
        return 1
    data = parse_file(path)
    if not data:
        print("配置文件里没有可用的 key=value 项")
        return 1
    print(f"读取到 {len(data)} 项：{', '.join(sorted(data))}")
    apply(data)
    print("更新完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
