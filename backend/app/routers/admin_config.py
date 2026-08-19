"""管理端路由：6 个优化单元配置、全局统一调用指令 s2、LLM 模型配置的读写，需管理员权限。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import llm_service
from app import model_config as mc
from app.database import get_db
from app.models import GlobalConfig, UnitConfig, User
from app.schemas import (
    GlobalConfigOut,
    GlobalConfigUpdate,
    ModelConfigOut,
    ModelConfigUpdate,
    PlatformPreset,
    UnitConfigOut,
    UnitConfigUpdate,
)
from app.security import require_admin

router = APIRouter(prefix="/api/admin", tags=["管理端-优化配置"])

S1_KEY = "global_instruction_s1"  # 首次对话（单元 1）指令（通用版）
S2_KEY = "global_instruction_s2"  # 后续对话（单元 2-6）统一调用指令（通用版）
S3_KEY = "global_instruction_s3"  # 修改提示词指令（通用版）
G1_KEY = "global_instruction_g1"  # 首次对话（单元 1）指令（竖屏 9:16 优化版，OpenRouter 专用）
G2_KEY = "global_instruction_g2"  # 后续对话（单元 2-6）统一调用指令（竖屏 9:16 优化版）
G3_KEY = "global_instruction_g3"  # 修改提示词指令（竖屏 9:16 优化版）


@router.get("/units", response_model=list[UnitConfigOut])
def get_unit_configs(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """6 个优化单元的完整配置（名称 / 默认模板 / 单元指令）。"""
    return db.query(UnitConfig).order_by(UnitConfig.unit_no).all()


@router.put("/units/{unit_no}", response_model=UnitConfigOut)
def update_unit_config(
    unit_no: int,
    body: UnitConfigUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """更新指定单元配置。用户端后续执行该单元时立即生效。"""
    config = db.query(UnitConfig).filter(UnitConfig.unit_no == unit_no).first()
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"优化单元 {unit_no} 不存在")
    config.name = body.name.strip() or config.name
    config.default_template = body.default_template
    config.unit_instruction = body.unit_instruction
    config.updated_at = datetime.now()
    db.commit()
    db.refresh(config)
    return config


@router.get("/global", response_model=GlobalConfigOut)
def get_global_config(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """读取六份调用指令 s1/s2/s3（通用版）与 g1/g2/g3（竖屏优化版）。"""
    rows = {row.key: row.value for row in db.query(GlobalConfig).all()}
    return GlobalConfigOut(
        global_instruction_s1=rows.get(S1_KEY, ""),
        global_instruction_s2=rows.get(S2_KEY, ""),
        global_instruction_s3=rows.get(S3_KEY, ""),
        global_instruction_g1=rows.get(G1_KEY, ""),
        global_instruction_g2=rows.get(G2_KEY, ""),
        global_instruction_g3=rows.get(G3_KEY, ""),
    )


@router.put("/global", response_model=GlobalConfigOut)
def update_global_config(body: GlobalConfigUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """更新调用指令（s/g 系列任一字段，None 表示不修改；对之后每一轮生效）。"""
    updates = {
        S1_KEY: body.global_instruction_s1,
        S2_KEY: body.global_instruction_s2,
        S3_KEY: body.global_instruction_s3,
        G1_KEY: body.global_instruction_g1,
        G2_KEY: body.global_instruction_g2,
        G3_KEY: body.global_instruction_g3,
    }
    rows = {row.key: row for row in db.query(GlobalConfig).all()}
    for key, value in updates.items():
        if value is None:
            continue
        row = rows.get(key)
        if row is None:
            row = GlobalConfig(key=key, value=value)
            db.add(row)
        else:
            row.value = value
        row.updated_at = datetime.now()
    db.commit()
    db.flush()
    rows = {row.key: row.value for row in db.query(GlobalConfig).all()}
    return GlobalConfigOut(
        global_instruction_s1=rows.get(S1_KEY, ""),
        global_instruction_s2=rows.get(S2_KEY, ""),
        global_instruction_s3=rows.get(S3_KEY, ""),
        global_instruction_g1=rows.get(G1_KEY, ""),
        global_instruction_g2=rows.get(G2_KEY, ""),
        global_instruction_g3=rows.get(G3_KEY, ""),
    )


# ---------- LLM 模型配置（GPT 接口预留：provider / 模型名 / base_url / API Key） ----------

def _mask_key(key: str) -> str:
    """API Key 掩码展示：前 6 位 + *** + 后 4 位。"""
    if not key:
        return ""
    if len(key) <= 10:
        return "*" * len(key)
    return f"{key[:6]}***{key[-4:]}"


def _model_config_out() -> ModelConfigOut:
    cfg = mc.get_model_config()
    return ModelConfigOut(
        platform=cfg["platform"],
        model=cfg["model"],
        base_url=cfg["base_url"],
        reasoning_enabled=cfg["reasoning_enabled"],
        api_key_masked=_mask_key(cfg["api_key"]),
        has_api_key=bool(cfg["api_key"]),
        platforms=[PlatformPreset(**p) for p in mc.list_platforms()],
    )


@router.get("/model", response_model=ModelConfigOut)
def get_model_config(admin: User = Depends(require_admin)):
    """读取当前 LLM 模型配置（API Key 掩码返回）。"""
    return _model_config_out()


@router.put("/model", response_model=ModelConfigOut)
def update_model_config(body: ModelConfigUpdate, admin: User = Depends(require_admin)):
    """更新模型配置并立即生效（清空模型单例缓存，下一次调用按新配置重建）。

    支持多个 OpenAI 兼容平台（OpenAI 官方 / OpenRouter / Kimi / 智谱 / 通义 / 自定义）。
    """
    mc.save_model_config(body.model_dump())
    llm_service.invalidate_llm_cache()
    return _model_config_out()
