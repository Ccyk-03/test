"""应用配置：加载 .env 环境变量，统一管理模型/数据库/JWT 等配置项。

.env 读取顺序：
1. /home/cyk/python_Project/.env（课程项目级，含 CLOSEAI_API_KEY / CLOSEAI_BASE_URL / LANGSMITH_*）
2. GPT_Chat/.env（本项目级，若存在则覆盖，用于本地覆盖配置）
"""
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

from app import runtime_env  # 触发安装校验 guard + 提供路径推导（DB 位置随安装/开发模式变化）

# 项目级 .env（python_Project 目录）
_PROJECT_ENV = Path(__file__).resolve().parents[3] / ".env"
# 本项目级 .env（GPT_Chat 目录），存在则加载并覆盖
_LOCAL_ENV = Path(__file__).resolve().parents[2] / ".env"

load_dotenv(_PROJECT_ENV, override=True)
load_dotenv(_LOCAL_ENV, override=True)

# 安装版：JWT 密钥取自 config.json（首次启动时由 run_app.pyw 生成随机值，
# 不使用开发默认密钥，避免部署后仍为公开默认值）
if runtime_env.IS_INSTALLED:
    import os

    _installed_cfg = runtime_env.read_json(runtime_env.CONFIG_PATH)
    if _installed_cfg.get("jwt_secret"):
        os.environ["JWT_SECRET_KEY"] = _installed_cfg["jwt_secret"]

# backend 目录绝对路径
BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """全局配置：可从环境变量覆盖，均提供默认值兜底。"""

    # ---- LLM 模型配置（仅 OpenAI GPT，模型名与 Key 由管理端配置）----
    llm_model: str = "gpt-4o-mini"                 # LLM_MODEL（默认模型，可在管理端修改）
    llm_temperature: float = 0.7                   # LLM_TEMPERATURE
    llm_timeout: int = 600                         # LLM_TIMEOUT（秒）；推理模型+长提示词可能需 3-10 分钟

    # ---- JWT 配置 ----
    jwt_secret_key: str = "dev-secret-key-change-me-in-production"  # JWT_SECRET_KEY
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440                 # token 有效期（分钟），默认 24 小时

    # ---- 数据库配置 ----
    # 安装版数据库位于 %APPDATA%\PromptOpt\app.db，开发版位于 backend/data/app.db（由 runtime_env 推导）
    database_url: str = f"sqlite:///{runtime_env.DB_PATH}"

    model_config = {"env_file": _LOCAL_ENV, "extra": "ignore"}


settings = Settings()
