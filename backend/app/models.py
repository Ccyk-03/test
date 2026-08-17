"""ORM 数据模型：用户 / 审计日志 / 单元配置 / 全局配置。

设计说明：
- audit_logs 是审计与链式状态的双重事实源：
  「用户 A 最近一次单元 i-1 的成功输出」直接由 (user_id, unit_no, status='success')
  按 id 倒序查询得出，不另建状态表，避免双写不一致。
- username 在审计表中做冗余快照：账号被删除后历史记录仍可读。
"""
from datetime import datetime

from sqlalchemy import (Boolean, DateTime, Index, Integer, String, Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserUnitName(Base):
    """用户对优化单元的自定义显示名（按用户存储，不影响管理端全局配置名称）。"""

    __tablename__ = "user_unit_names"
    __table_args__ = (
        UniqueConstraint("user_id", "unit_no", name="uq_user_unit_name"),
        Index("ix_uun_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_no: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-6
    name: Mapped[str] = mapped_column(String(50), nullable=False)


class Conversation(Base):
    """对话：一个对话 = 一轮 6 阶段（单元 1-6）优化任务；对话号按用户递增。"""

    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_user", "user_id"),
        UniqueConstraint("user_id", "conversation_no", name="uq_conversations_user_no"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    conversation_no: Mapped[int] = mapped_column(Integer, nullable=False)  # 每用户从 1 递增
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)  # 完成时间（点「完成」后保存进度）


class User(Base):
    """系统账号：管理员（admin）/ 普通用户（user）两级角色。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)  # 格式 salt_hex$hash_hex
    role: Mapped[str] = mapped_column(String(10), nullable=False, default="user")  # 'admin' / 'user'
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)


class AuditLog(Base):
    """审计日志：每次优化调用必写一条（成功或失败），承载链式状态查询。"""

    __tablename__ = "audit_logs"
    __table_args__ = (
        # 复合索引直接支撑「用户 A 最近一次单元 i 的成功输出」查询
        Index("ix_audit_user_unit_time", "user_id", "unit_no", "created_at"),
        Index("ix_audit_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False)          # 用户名快照
    unit_no: Mapped[int] = mapped_column(Integer, nullable=False)               # 1-6 单元号
    action: Mapped[str] = mapped_column(String(10), nullable=False, default="optimize")  # 'optimize' 优化 / 'revise' 修改
    input_prompt: Mapped[str] = mapped_column(Text, nullable=False)             # 待优化提示词 t_i（修改流程为「需要修改的提示词」）
    unit_instruction: Mapped[str] = mapped_column(Text, nullable=False, default="")  # 生效指令快照
    base_template_source: Mapped[str] = mapped_column(String(10), nullable=False)    # 'chained' / 'default' / 'manual' / 'none'
    base_template: Mapped[str] = mapped_column(Text, nullable=False, default="")     # 基础模板快照（none 时为空）
    output_text: Mapped[str | None] = mapped_column(Text)                       # 优化结果（失败为 NULL）
    status: Mapped[str] = mapped_column(String(10), nullable=False)             # 'success' / 'error'
    error_message: Mapped[str | None] = mapped_column(Text)                     # 失败原因
    model_name: Mapped[str | None] = mapped_column(String(64))                  # 所用模型
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    elapsed_ms: Mapped[int | None] = mapped_column(Integer)                     # 耗时（毫秒）
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # 软删除（用户删除自己的记录；审计保留）
    display_name: Mapped[str | None] = mapped_column(String(100))               # 用户自定义记录名（重命名）
    conversation_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 所属对话号（0=迁移前的历史数据）
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)


class UnitConfig(Base):
    """优化单元配置：6 组独立单元，管理端可编辑默认模板与单元指令。"""

    __tablename__ = "unit_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_no: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)  # 1-6
    name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    default_template: Mapped[str] = mapped_column(Text, nullable=False)         # 默认（回退）基础模板
    unit_instruction: Mapped[str] = mapped_column(Text, nullable=False, default="")  # 单元自定义指令
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class GlobalConfig(Base):
    """全局配置表：目前存放统一调用指令 s2，预留模型名/温度等配置项。"""

    __tablename__ = "global_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
