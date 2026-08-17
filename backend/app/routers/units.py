"""用户端路由：6 个优化单元概览、执行优化（链式迭代 + 审计留痕）、修改提示词（s3 指令）、单元历史。

对话流程（对应底层链式规则）：
- 单元 1（首次对话）：用户提示词 t1 + s1 指令 → T1（无基础模板）
- 单元 i(≥2)（后续对话）：t_i + s2 指令 + 链式基础模板 T_{i-1} → T_i（无历史回退默认模板）
- 修改流程（revise）：上一次最终提示词（手动输入）+ 需修改提示词 + s3 指令 → 新的 T_i
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import chain_state, llm_service
from app.database import get_db
from app.models import AuditLog, Conversation, UnitConfig, User, UserUnitName
from app.routers.conversations import get_current_conversation
from app.schemas import (
    AuditDetail,
    RecordRenameRequest,
    UnitRenameRequest,
    UnitReviseRequest,
    UnitRunRequest,
    UnitRunResponse,
    UnitSummary,
)
from app.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/units", tags=["优化单元"])

UNIT_MIN, UNIT_MAX = 1, 6


def _get_unit_config(db: Session, unit_no: int) -> UnitConfig:
    config = db.query(UnitConfig).filter(UnitConfig.unit_no == unit_no).first()
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"优化单元 {unit_no} 不存在")
    return config


def _latest_success(db: Session, user_id: int, unit_no: int, conversation_no: int) -> AuditLog | None:
    """当前对话内指定单元的最近一次成功记录（链式状态查询统一入口；跳过已删除记录）。"""
    return (
        db.query(AuditLog)
        .filter(
            AuditLog.user_id == user_id,
            AuditLog.conversation_no == conversation_no,
            AuditLog.unit_no == unit_no,
            AuditLog.status == "success",
            AuditLog.is_deleted == False,  # noqa: E712
        )
        .order_by(AuditLog.id.desc())
        .first()
    )


def _resolve_conversation_no(db: Session, user: User, requested: int | None) -> int:
    """解析所属对话号：请求显式指定则校验后使用，否则为当前对话。"""
    if requested is not None:
        conv = (
            db.query(Conversation)
            .filter(Conversation.user_id == user.id, Conversation.conversation_no == requested)
            .first()
        )
        if conv is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"对话 {requested} 不存在")
        return requested
    return get_current_conversation(db, user).conversation_no


def _merge_instruction(configured: str, custom: str) -> str:
    """生效单元指令 = 管理端配置的单元指令 + 用户本次追加（空行分隔）。"""
    instruction = (configured or "").strip()
    extra = (custom or "").strip()
    if extra:
        instruction = f"{instruction}\n\n{extra}".strip()
    return instruction


def _archive_unit_records(db: Session, user_id: int, conversation_no: int, unit_no: int) -> str | None:
    """修改覆盖：归档（软删除）该任务该单元已有的可见记录，并返回其自定义名称。

    用户侧每个单元只保留最新一张卡片；被覆盖的记录在管理端审计中仍保留可查。
    """
    previous = (
        db.query(AuditLog)
        .filter(
            AuditLog.user_id == user_id,
            AuditLog.conversation_no == conversation_no,
            AuditLog.unit_no == unit_no,
            AuditLog.is_deleted == False,  # noqa: E712
        )
        .order_by(AuditLog.id.desc())
        .first()
    )
    inherited_name = previous.display_name if previous else None
    db.query(AuditLog).filter(
        AuditLog.user_id == user_id,
        AuditLog.conversation_no == conversation_no,
        AuditLog.unit_no == unit_no,
        AuditLog.is_deleted == False,  # noqa: E712
    ).update({AuditLog.is_deleted: True}, synchronize_session=False)
    db.commit()
    return inherited_name


def _call_and_audit(
    db: Session,
    *,
    user: User,
    unit_no: int,
    conversation_no: int,
    action: str,
    input_prompt: str,
    unit_instruction: str,
    base_template: str,
    base_source: str,
    chained_from: int | None,
    global_instruction: str,
    display_name: str | None = None,
) -> UnitRunResponse:
    """公共执行流程：调用 LLM（无论成败都写审计）→ 返回响应。"""
    audit = AuditLog(
        user_id=user.id,
        username=user.username,
        unit_no=unit_no,
        conversation_no=conversation_no,
        action=action,
        input_prompt=input_prompt,
        unit_instruction=unit_instruction,
        base_template_source=base_source,
        base_template=base_template,
        status="error",  # 先按失败占位，成功后覆盖
        model_name=llm_service.current_model_name(),
        display_name=display_name,
    )
    try:
        output_text, usage, elapsed_ms = llm_service.run_optimization(
            base_template=base_template,
            global_instruction=global_instruction,
            unit_instruction=unit_instruction,
            input_prompt=input_prompt,
        )
    except Exception as exc:  # LLM 调用失败/超时：审计留痕后返回 502
        audit.error_message = f"{type(exc).__name__}: {exc}"[:2000]
        db.add(audit)
        db.commit()
        logger.error("单元 %s %s 失败 user=%s: %s", unit_no, action, user.username, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"模型调用失败：{exc}") from exc

    audit.status = "success"
    audit.output_text = output_text
    audit.prompt_tokens = usage["prompt_tokens"]
    audit.completion_tokens = usage["completion_tokens"]
    audit.total_tokens = usage["total_tokens"]
    audit.elapsed_ms = elapsed_ms
    db.add(audit)
    db.commit()

    return UnitRunResponse(
        unit_no=unit_no,
        action=action,
        conversation_no=conversation_no,
        output_text=output_text,
        base_template_source=base_source,
        chained_from_unit=chained_from,
        base_template_preview=base_template[:200],
        model_name=llm_service.current_model_name(),
        usage=usage,
        elapsed_ms=elapsed_ms,
        created_at=audit.created_at,
    )


def _sse(payload: dict) -> str:
    """序列化一条 SSE 事件。"""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _stream_run(
    db: Session,
    *,
    user: User,
    unit_no: int,
    conversation_no: int,
    action: str,
    input_prompt: str,
    unit_instruction: str,
    base_template: str,
    base_source: str,
    chained_from: int | None,
    global_instruction: str,
    display_name: str | None = None,
):
    """SSE 生成器：流式输出优化结果（delta 事件），结束后发 meta 事件；无论成败写审计。"""
    audit = AuditLog(
        user_id=user.id,
        username=user.username,
        unit_no=unit_no,
        conversation_no=conversation_no,
        action=action,
        input_prompt=input_prompt,
        unit_instruction=unit_instruction,
        base_template_source=base_source,
        base_template=base_template,
        status="error",  # 先按失败占位，成功后覆盖
        model_name=llm_service.current_model_name(),
        display_name=display_name,
    )
    committed = False
    full_text = ""
    try:
        stats: dict = {}
        for piece in llm_service.stream_optimization(
            base_template=base_template,
            global_instruction=global_instruction,
            unit_instruction=unit_instruction,
            input_prompt=input_prompt,
            stats=stats,
        ):
            full_text += piece
            yield _sse({"type": "delta", "text": piece})

        usage = stats.get("usage") or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        elapsed_ms = stats.get("elapsed_ms") or 0
        audit.status = "success"
        audit.output_text = full_text
        audit.prompt_tokens = usage["prompt_tokens"]
        audit.completion_tokens = usage["completion_tokens"]
        audit.total_tokens = usage["total_tokens"]
        audit.elapsed_ms = elapsed_ms
        db.add(audit)
        db.commit()
        committed = True
        yield _sse({
            "type": "meta",
            "unit_no": unit_no,
            "action": action,
            "conversation_no": conversation_no,
            "base_template_source": base_source,
            "chained_from_unit": chained_from,
            "model_name": llm_service.current_model_name(),
            "usage": usage,
            "elapsed_ms": elapsed_ms,
        })
    except Exception as exc:  # 模型调用失败：审计留痕后发送 error 事件
        if not committed:
            audit.error_message = f"{type(exc).__name__}: {exc}"[:2000]
            db.add(audit)
            db.commit()
            committed = True
            logger.error("单元 %s %s 失败 user=%s: %s", unit_no, action, user.username, exc)
        yield _sse({"type": "error", "message": f"模型调用失败：{exc}"})
    finally:
        # 客户端中途断开：也留痕，保证审计完整
        if not committed:
            audit.error_message = "客户端连接中断"
            db.add(audit)
            db.commit()
            logger.warning("单元 %s %s 客户端中断 user=%s", unit_no, action, user.username)


@router.get("", response_model=list[UnitSummary])
def list_units(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    conversation_no: int | None = Query(None, ge=1, description="对话号（缺省为当前对话）"),
):
    """6 个单元概览（指定对话内）：has_chained_base（上一单元是否有成功输出）与最近运行时间，
    前端据此渲染链式进度条（查看历史对话时同步切换）。
    单元名称优先取当前用户的自定义显示名，否则用配置名（单元1~单元6）。"""
    conversation_no = _resolve_conversation_no(db, user, conversation_no)
    configs = db.query(UnitConfig).order_by(UnitConfig.unit_no).all()
    user_names = {
        n.unit_no: n.name
        for n in db.query(UserUnitName).filter(UserUnitName.user_id == user.id).all()
    }
    summaries = []
    for cfg in configs:
        has_chained_base, chained_from = False, None
        if cfg.unit_no > UNIT_MIN:
            prev = _latest_success(db, user.id, cfg.unit_no - 1, conversation_no)
            if prev is not None:
                has_chained_base, chained_from = True, cfg.unit_no - 1
        last_run = (
            db.query(AuditLog)
            .filter(
                AuditLog.user_id == user.id,
                AuditLog.conversation_no == conversation_no,
                AuditLog.unit_no == cfg.unit_no,
                AuditLog.is_deleted == False,  # noqa: E712
            )
            .order_by(AuditLog.id.desc())
            .first()
        )
        summaries.append(UnitSummary(
            unit_no=cfg.unit_no,
            name=user_names.get(cfg.unit_no),
            has_chained_base=has_chained_base,
            chained_from_unit=chained_from,
            last_run_at=last_run.created_at if last_run else None,
        ))
    return summaries


@router.post("/{unit_no}/run", response_model=UnitRunResponse)
def run_unit(
    unit_no: int,
    body: UnitRunRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    stream: bool = Query(False, description="true 时以 SSE 流式返回（前端默认使用）"),
):
    """执行一轮提示词优化。

    单元 1（首次对话）：结合 s1 指令，无基础模板；
    单元 i(≥2)（后续对话）：结合 s2 指令 + 链式基础模板 T_{i-1}。
    stream=true 时返回 text/event-stream：delta（输出增量）/ meta（统计）/ error 事件。
    """
    if not UNIT_MIN <= unit_no <= UNIT_MAX:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"优化单元 {unit_no} 不存在")
    config = _get_unit_config(db, unit_no)
    conversation_no = _resolve_conversation_no(db, user, body.conversation_no)

    # 1. 调用指令：单元 1、2 使用 s1 指令；单元 3-6 使用 s2 指令
    if unit_no <= 2:
        global_instruction = chain_state.get_global_instruction(db, chain_state.INSTRUCTION_S1_KEY)
    else:
        global_instruction = chain_state.get_global_instruction(db, chain_state.INSTRUCTION_S2_KEY)

    # 2. 基础模板：单元 1 无基础模板；单元 2-6 链式（同一对话内 T_{i-1} 或回退默认模板）
    if unit_no == UNIT_MIN:
        base_template, base_source, chained_from = "", "none", None
    else:
        base_template, base_source, chained_from = chain_state.resolve_base_template(
            db, user.id, unit_no, conversation_no
        )

    # 2. 本单元生效指令 = 管理端配置的单元指令 + 用户本次追加
    unit_instruction = _merge_instruction(config.unit_instruction, body.custom_instruction)

    # 3. 流式 / 同步两种返回方式
    if stream:
        return StreamingResponse(
            _stream_run(
                db,
                user=user,
                unit_no=unit_no,
                conversation_no=conversation_no,
                action="optimize",
                input_prompt=body.input_prompt,
                unit_instruction=unit_instruction,
                base_template=base_template,
                base_source=base_source,
                chained_from=chained_from,
                global_instruction=global_instruction,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    return _call_and_audit(
        db,
        user=user,
        unit_no=unit_no,
        conversation_no=conversation_no,
        action="optimize",
        input_prompt=body.input_prompt,
        unit_instruction=unit_instruction,
        base_template=base_template,
        base_source=base_source,
        chained_from=chained_from,
        global_instruction=global_instruction,
    )


@router.post("/{unit_no}/revise", response_model=UnitRunResponse)
def revise_unit(
    unit_no: int,
    body: UnitReviseRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    stream: bool = Query(False, description="true 时以 SSE 流式返回（前端默认使用）"),
):
    """修改已生成提示词：结合 s3 指令重新优化。

    修改对话框 1 输入「上一次生成的最终提示词」→ 作为基础模板（source='manual'）；
    修改对话框 2 输入「需要修改的提示词」→ 作为待优化提示词。
    单元 1 无上一对话：previous_final_prompt 可留空；其他单元留空时自动取链式历史。
    修改成功后的输出会作为该单元的最新 T_i 接续链式关系（后续单元自动引用）。
    """
    if not UNIT_MIN <= unit_no <= UNIT_MAX:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"优化单元 {unit_no} 不存在")
    config = _get_unit_config(db, unit_no)
    conversation_no = _resolve_conversation_no(db, user, body.conversation_no)

    # 0. 修改覆盖：归档该单元已有卡片（用户侧只保留最新一张），继承其自定义名称
    inherited_name = _archive_unit_records(db, user.id, conversation_no, unit_no)

    # 1. 基础模板：优先用户手动输入的上一次最终提示词
    previous = body.previous_final_prompt.strip()
    if previous:
        base_template, base_source, chained_from = previous, "manual", None
    elif unit_no == UNIT_MIN:
        # 单元 1 修改：无上一对话，无基础模板
        base_template, base_source, chained_from = "", "none", None
    else:
        # 留空回退：自动取同一对话内链式历史或默认模板
        base_template, base_source, chained_from = chain_state.resolve_base_template(
            db, user.id, unit_no, conversation_no
        )

    # 2. 修改流程统一使用 s3 指令
    global_instruction = chain_state.get_global_instruction(db, chain_state.INSTRUCTION_S3_KEY)

    # 3. 本单元生效指令
    unit_instruction = _merge_instruction(config.unit_instruction, body.custom_instruction)

    # 4. 流式 / 同步两种返回方式（新卡片继承原卡片的自定义名称）
    if stream:
        return StreamingResponse(
            _stream_run(
                db,
                user=user,
                unit_no=unit_no,
                conversation_no=conversation_no,
                action="revise",
                input_prompt=body.prompt_to_revise,
                unit_instruction=unit_instruction,
                base_template=base_template,
                base_source=base_source,
                chained_from=chained_from,
                global_instruction=global_instruction,
                display_name=inherited_name,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    return _call_and_audit(
        db,
        user=user,
        unit_no=unit_no,
        conversation_no=conversation_no,
        action="revise",
        input_prompt=body.prompt_to_revise,
        unit_instruction=unit_instruction,
        base_template=base_template,
        base_source=base_source,
        chained_from=chained_from,
        global_instruction=global_instruction,
        display_name=inherited_name,
    )


@router.get("/{unit_no}/history", response_model=list[AuditDetail])
def unit_history(
    unit_no: int,
    limit: int = Query(10, ge=1, le=50),
    conversation_no: int | None = Query(None, ge=1, description="对话号（缺省为当前对话）"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """当前用户在某对话内该单元的最近运行历史（倒序，不含已删除记录）。"""
    if not UNIT_MIN <= unit_no <= UNIT_MAX:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"优化单元 {unit_no} 不存在")
    conv_no = _resolve_conversation_no(db, user, conversation_no)
    logs = (
        db.query(AuditLog)
        .filter(
            AuditLog.user_id == user.id,
            AuditLog.conversation_no == conv_no,
            AuditLog.unit_no == unit_no,
            AuditLog.is_deleted == False,  # noqa: E712
        )
        .order_by(AuditLog.id.desc())
        .limit(limit)
        .all()
    )
    return [_to_detail(log) for log in logs]


def _get_own_record(db: Session, user: User, unit_no: int, record_id: int) -> AuditLog:
    """获取当前用户自己的记录（不存在/非本人/单元不符 → 404）。"""
    record = db.get(AuditLog, record_id)
    if record is None or record.user_id != user.id or record.unit_no != unit_no:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="记录不存在")
    return record


@router.put("/{unit_no}/rename")
def rename_unit(
    unit_no: int,
    body: UnitRenameRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """重命名优化单元（按当前用户存储显示名，不影响管理端全局配置名称）。"""
    if not UNIT_MIN <= unit_no <= UNIT_MAX:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"优化单元 {unit_no} 不存在")
    _get_unit_config(db, unit_no)  # 校验单元存在
    name = body.name.strip()
    row = db.query(UserUnitName).filter(
        UserUnitName.user_id == user.id, UserUnitName.unit_no == unit_no
    ).first()
    if row is None:
        db.add(UserUnitName(user_id=user.id, unit_no=unit_no, name=name))
    else:
        row.name = name
    db.commit()
    return {"detail": "单元已重命名"}


@router.put("/{unit_no}/records/{record_id}/rename")
def rename_record(
    unit_no: int,
    record_id: int,
    body: RecordRenameRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """重命名自己的对话记录（display_name 显示在左侧记录列表中）。"""
    if not UNIT_MIN <= unit_no <= UNIT_MAX:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"优化单元 {unit_no} 不存在")
    record = _get_own_record(db, user, unit_no, record_id)
    record.display_name = body.name.strip()
    db.commit()
    return {"detail": "记录已重命名"}


@router.delete("/{unit_no}/records/{record_id}")
def delete_record(
    unit_no: int,
    record_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除自己的对话记录（软删除：用户列表不再展示，管理端审计仍保留可查）。"""
    if not UNIT_MIN <= unit_no <= UNIT_MAX:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"优化单元 {unit_no} 不存在")
    record = _get_own_record(db, user, unit_no, record_id)
    record.is_deleted = True
    db.commit()
    return {"detail": "记录已删除"}


def _to_detail(log: AuditLog) -> AuditDetail:
    """审计记录 → 详情模型（含输入输出截断预览）。"""
    return AuditDetail(
        id=log.id,
        username=log.username,
        unit_no=log.unit_no,
        action=log.action,
        status=log.status,
        conversation_no=log.conversation_no,
        base_template_source=log.base_template_source,
        input_preview=log.input_prompt[:100],
        output_preview=(log.output_text[:100] if log.output_text else None),
        total_tokens=log.total_tokens,
        elapsed_ms=log.elapsed_ms,
        created_at=log.created_at,
        input_prompt=log.input_prompt,
        unit_instruction=log.unit_instruction,
        base_template=log.base_template,
        output_text=log.output_text,
        error_message=log.error_message,
        model_name=log.model_name,
        prompt_tokens=log.prompt_tokens,
        completion_tokens=log.completion_tokens,
        is_deleted=bool(log.is_deleted),
        display_name=log.display_name,
    )
