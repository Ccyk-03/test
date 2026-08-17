"""管理端路由：审计查询（分页筛选列表 + 单条完整详情），需管理员权限。

审计字段覆盖：账号、单元号、输入输出、生效指令、基础模板来源与快照、
状态、token 用量、耗时、时间戳 —— 满足「查询每个账号的系统使用历史」需求。
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditLog, User
from app.schemas import AuditDetail, AuditPage, AuditSummary
from app.security import require_admin

router = APIRouter(prefix="/api/admin/audit", tags=["管理端-审计查询"])


def _to_summary(log: AuditLog) -> AuditSummary:
    """审计记录 → 列表摘要（输入输出截断，详情走单独端点）。"""
    return AuditSummary(
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
        is_deleted=bool(log.is_deleted),
        display_name=log.display_name,
        created_at=log.created_at,
    )


def _to_detail(log: AuditLog) -> AuditDetail:
    """审计记录 → 完整详情（含输入输出全文、指令与基础模板快照）。"""
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


@router.get("", response_model=AuditPage)
def list_audit(
    username: str | None = Query(None, description="用户名（模糊匹配）"),
    user_id: int | None = Query(None, description="账号 id"),
    unit_no: int | None = Query(None, ge=1, le=6, description="单元号 1-6"),
    action: str | None = Query(None, description="optimize 优化 / revise 修改"),
    status_value: str | None = Query(None, alias="status", description="success / error"),
    start: datetime | None = Query(None, description="起始时间（含）"),
    end: datetime | None = Query(None, description="结束时间（含）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """审计记录分页筛选查询（按时间倒序）。"""
    q = db.query(AuditLog)
    if username:
        q = q.filter(AuditLog.username.like(f"%{username}%"))
    if user_id is not None:
        q = q.filter(AuditLog.user_id == user_id)
    if unit_no is not None:
        q = q.filter(AuditLog.unit_no == unit_no)
    if action is not None:
        q = q.filter(AuditLog.action == action)
    if status_value is not None:
        q = q.filter(AuditLog.status == status_value)
    if start is not None:
        q = q.filter(AuditLog.created_at >= start)
    if end is not None:
        q = q.filter(AuditLog.created_at <= end)

    total = q.count()
    logs = q.order_by(AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return AuditPage(total=total, page=page, page_size=page_size, items=[_to_summary(log) for log in logs])


@router.get("/{log_id}", response_model=AuditDetail)
def get_audit_detail(log_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """单条审计完整详情（含完整输入输出、指令、基础模板快照）。"""
    log = db.get(AuditLog, log_id)
    if log is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="审计记录不存在")
    return _to_detail(log)
