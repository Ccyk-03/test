"""LLM 模型配置：支持多个 OpenAI 兼容平台（OpenAI 官方 / OpenRouter / Kimi / 智谱 / 通义 / 自定义）。

API Key 仅由管理员在「管理端 → 模型配置」填写，接口只返回掩码、不明文展示。
所有平台底层均为 OpenAI 兼容端点（/chat/completions），统一走
init_chat_model(model_provider="openai", api_key=..., base_url=...)。
"""
from app.runtime_env import CONFIG_PATH, read_json, write_json

# 平台预设：key → {label, base_url, default_model, reasoning}
# reasoning=True 表示该平台默认模型为推理模型（如 gpt-oss），调用时附带 reasoning 参数
PLATFORMS = {
    "openai": {"label": "OpenAI 官方", "base_url": "https://api.openai.com/v1", "default_model": "gpt-4o-mini", "reasoning": False},
    "openrouter": {"label": "OpenRouter", "base_url": "https://openrouter.ai/api/v1", "default_model": "openai/gpt-oss-20b:free", "reasoning": True},
    "moonshot": {"label": "Moonshot Kimi", "base_url": "https://api.moonshot.cn/v1", "default_model": "moonshot-v1-8k", "reasoning": False},
    "zhipu": {"label": "智谱 GLM", "base_url": "https://open.bigmodel.cn/api/paas/v4", "default_model": "glm-4-flash", "reasoning": False},
    "dashscope": {"label": "通义千问", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "default_model": "qwen-plus", "reasoning": False},
    "custom": {"label": "自定义（OpenAI 兼容）", "base_url": "", "default_model": "", "reasoning": False},
}

DEFAULT_PLATFORM = "openai"


def _platform_defaults(platform: str) -> dict:
    return PLATFORMS.get(platform) or PLATFORMS[DEFAULT_PLATFORM]


def _normalize_model(name: str) -> str:
    """规范化模型名：全角冒号转半角、去除首尾空白。

    防止用户从网页复制模型名时带入全角「：」导致 OpenRouter 报「not a valid model ID」。
    """
    return (name or "").replace("：", ":").strip()


def get_model_config() -> dict:
    """当前生效的模型配置：{platform, model, base_url, api_key, reasoning_enabled}。

    模型名不设默认：由用户在管理端自行填写（空则调用时提示填写）。
    """
    cfg = read_json(CONFIG_PATH)
    platform = cfg.get("platform") or DEFAULT_PLATFORM
    defaults = _platform_defaults(platform)
    model = _normalize_model(cfg.get("model") or "")
    # reasoning：显式配置优先，否则用平台默认值
    if "reasoning_enabled" in cfg:
        reasoning = bool(cfg["reasoning_enabled"])
    else:
        reasoning = bool(defaults["reasoning"])
    return {
        "platform": platform,
        "model": model,
        "base_url": (cfg.get("base_url") or "").strip() or defaults["base_url"],
        "api_key": cfg.get("api_key") or "",
        "reasoning_enabled": reasoning,
    }


def save_model_config(patch: dict) -> dict:
    """合并保存模型配置；api_key 为空串表示保持不变。返回保存后的完整配置。"""
    current = get_model_config()
    platform_changed = False
    if patch.get("platform") and patch["platform"] in PLATFORMS:
        current["platform"] = patch["platform"]
        platform_changed = True
    if patch.get("model"):
        current["model"] = _normalize_model(patch["model"])
    if patch.get("base_url"):
        current["base_url"] = patch["base_url"].strip()
    if patch.get("api_key"):
        current["api_key"] = patch["api_key"].strip()
    if "reasoning_enabled" in patch:
        current["reasoning_enabled"] = bool(patch["reasoning_enabled"])
    elif platform_changed:
        # 平台切换后，推理开关跟随新平台默认（除非显式指定）
        current["reasoning_enabled"] = bool(_platform_defaults(current["platform"])["reasoning"])
    # 合并回原文件：保留 jwt_secret 等附加键，避免覆盖丢失
    raw = read_json(CONFIG_PATH)
    raw.update(current)
    write_json(CONFIG_PATH, raw)
    return current


def list_platforms() -> list[dict]:
    """平台预设列表（前端下拉用）。"""
    return [
        {
            "key": k,
            "label": v["label"],
            "base_url": v["base_url"],
            "default_model": v["default_model"],
            "reasoning": bool(v["reasoning"]),
        }
        for k, v in PLATFORMS.items()
    ]
