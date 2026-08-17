"""对话路由：一个对话 = 一轮 6 阶段（单元 1-6）优化任务。

完成当前对话的 6 个阶段后，可开启新对话重新生成 6 个阶段的任务；
链式关系按对话隔离（新对话的单元 i 不会引用上一对话的输出）。
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditLog, Conversation, User
from app.schemas import AuditDetail, ConversationOut
from app.security import get_current_user

router = APIRouter(prefix="/api/conversations", tags=["对话"])


def _to_out(db: Session, conv: Conversation) -> ConversationOut:
    """对话 → 输出模型（附该对话内完成阶段数/最近阶段/最近时间）。"""
    records = (
        db.query(AuditLog)
        .filter(
            AuditLog.user_id == conv.user_id,
            AuditLog.conversation_no == conv.conversation_no,
            AuditLog.is_deleted == False,  # noqa: E712
        )
        .all()
    )
    done_units = {r.unit_no for r in records if r.status == "success"}
    last = max(records, key=lambda r: r.id, default=None)
    return ConversationOut(
        id=conv.id,
        conversation_no=conv.conversation_no,
        created_at=conv.created_at,
        completed_at=conv.completed_at,
        stage_done=len(done_units),
        last_stage=last.unit_no if last else None,
        last_run_at=last.created_at if last else None,
    )


def get_current_conversation(db: Session, user: User) -> Conversation:
    """当前对话 = 该用户对话号最大的对话；不存在则自动创建「对话 1」。"""
    conv = (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id)
        .order_by(Conversation.conversation_no.desc())
        .first()
    )
    if conv is None:
        conv = Conversation(user_id=user.id, conversation_no=1)
        db.add(conv)
        db.commit()
        db.refresh(conv)
    return conv


@router.get("", response_model=list[ConversationOut])
def list_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """当前用户的全部对话（按对话号倒序，最新在前）。"""
    convs = (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id)
        .order_by(Conversation.conversation_no.desc())
        .all()
    )
    return [_to_out(db, conv) for conv in convs]


@router.post("", response_model=ConversationOut)
def start_conversation(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """开启新对话：对话号 = 当前最大对话号 + 1，从单元 1 重新开始 6 阶段任务。"""
    max_no = (
        db.query(Conversation.conversation_no)
        .filter(Conversation.user_id == user.id)
        .order_by(Conversation.conversation_no.desc())
        .first()
    )
    new_no = (max_no[0] if max_no else 0) + 1
    conv = Conversation(user_id=user.id, conversation_no=new_no, created_at=datetime.now())
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return _to_out(db, conv)


@router.put("/{conversation_no}/complete", response_model=ConversationOut)
def complete_conversation(
    conversation_no: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """完成任务：保存当前任务进度（标记完成时间）。

    要求该任务的 6 个阶段均有成功记录；已完成的任务再次点击为幂等操作。
    """
    conv = (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id, Conversation.conversation_no == conversation_no)
        .first()
    )
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"任务 {conversation_no} 不存在")
    if conv.completed_at is None:
        done_units = {
            r.unit_no
            for r in db.query(AuditLog)
            .filter(
                AuditLog.user_id == user.id,
                AuditLog.conversation_no == conversation_no,
                AuditLog.status == "success",
                AuditLog.is_deleted == False,  # noqa: E712
            )
            .all()
        }
        if len(done_units) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"任务还有未完成的阶段（已完成 {len(done_units)}/6），请完成全部 6 个阶段后再点击完成",
            )
        conv.completed_at = datetime.now()
        db.commit()
        db.refresh(conv)
    return _to_out(db, conv)


@router.get("/{conversation_no}/records", response_model=list[AuditDetail])
def get_conversation_records(
    conversation_no: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """指定对话的全部运行记录（跨 6 个阶段，倒序，不含已删除），用于回看历史对话。"""
    from app.routers.units import _to_detail

    conv = (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id, Conversation.conversation_no == conversation_no)
        .first()
    )
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"对话 {conversation_no} 不存在")
    logs = (
        db.query(AuditLog)
        .filter(
            AuditLog.user_id == user.id,
            AuditLog.conversation_no == conversation_no,
            AuditLog.is_deleted == False,  # noqa: E712
        )
        .order_by(AuditLog.id.desc())
        .all()
    )
    return [_to_detail(log) for log in logs]
