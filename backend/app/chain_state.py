"""链式状态解析：确定本轮优化的基础模板来源与调用指令。

链式递进优化机制（对话 1-6 对应单元 1-6）：
- 单元 1（首次对话）：无基础模板（source='none'），使用 s1 指令；
- 单元 i(≥2)（后续对话）：取「当前用户最近一次单元 i-1 的成功输出」T_{i-1} 作为基础模板
  （source='chained'），使用 s2 指令；若无成功历史，回退该单元默认模板（source='default'）。
- 修改流程（revise）：用户手动提供「上一次生成的最终提示词」（source='manual'），使用 s3 指令。

来源记录在审计日志 base_template_source 字段：'chained' / 'default' / 'manual' / 'none'。
链式血缘可直接由审计表追溯，不另建状态表（单事实源，避免双写不一致）。
"""
from sqlalchemy.orm import Session

from app.models import AuditLog, GlobalConfig, UnitConfig

# 三份调用指令的配置键（管理端可编辑）
INSTRUCTION_S1_KEY = "global_instruction_s1"  # 首次对话（单元 1）
INSTRUCTION_S2_KEY = "global_instruction_s2"  # 后续对话（单元 2-6）
INSTRUCTION_S3_KEY = "global_instruction_s3"  # 修改提示词


def resolve_base_template(db: Session, user_id: int, unit_no: int, conversation_no: int) -> tuple[str, str, int | None]:
    """返回 (基础模板, 来源, 链式来源单元号)。

    链式关系按对话隔离：只引用「同一对话内」上一单元最近成功输出。
    单元 1 无基础模板（首次对话直接使用 s1 指令）；
    单元 i(≥2) 优先取同一对话内上一单元最近成功输出，无则回退该单元默认模板。
    """
    # 单元 1（首次对话）：无基础模板
    if unit_no == 1:
        return "", "none", None

    # 查询同一对话内上一单元最近一次成功输出（命中复合索引 ix_audit_user_unit_time；跳过已删除记录）
    last = (
        db.query(AuditLog)
        .filter(
            AuditLog.user_id == user_id,
            AuditLog.conversation_no == conversation_no,
            AuditLog.unit_no == unit_no - 1,
            AuditLog.status == "success",
            AuditLog.is_deleted == False,  # noqa: E712
        )
        .order_by(AuditLog.id.desc())
        .first()
    )
    if last is not None and last.output_text:
        return last.output_text, "chained", unit_no - 1

    # 无链式历史 → 回退该单元默认模板
    config = db.query(UnitConfig).filter(UnitConfig.unit_no == unit_no).one()
    return config.default_template, "default", None


def get_global_instruction(db: Session, key: str = INSTRUCTION_S2_KEY) -> str:
    """读取指定调用指令（s1/s2/s3）；不存在时返回空串。"""
    row = db.query(GlobalConfig).filter(GlobalConfig.key == key).first()
    return row.value if row is not None else ""
