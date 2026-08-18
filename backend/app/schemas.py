"""Pydantic 请求/响应模型。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------- 认证 ----------

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50, description="用户名")
    password: str = Field(..., min_length=1, max_length=128, description="密码")


class UserOut(BaseModel):
    """账号信息（不含密码哈希）。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- 用户端：优化执行 ----------

class UnitRunRequest(BaseModel):
    input_prompt: str = Field(..., min_length=1, max_length=20000, description="待优化提示词 t_i")
    custom_instruction: str = Field("", max_length=20000, description="本次追加的自定义指令（可选）")
    conversation_no: int | None = Field(None, ge=1, description="所属对话号（缺省为当前对话）")


class UnitReviseRequest(BaseModel):
    """修改已生成提示词：结合 s3 指令重新优化。

    previous_final_prompt = 上一次生成的最终提示词（修改对话框 1 输入；单元 1 可留空）；
    prompt_to_revise     = 需要修改的提示词（修改对话框 2 输入）。
    """
    previous_final_prompt: str = Field("", max_length=20000, description="上一次生成的最终提示词（可留空，留空时自动取链式历史）")
    prompt_to_revise: str = Field(..., min_length=1, max_length=20000, description="需要修改的提示词")
    custom_instruction: str = Field("", max_length=20000, description="本次追加的自定义指令（可选）")
    conversation_no: int | None = Field(None, ge=1, description="所属对话号（缺省为当前对话）")


class UnitRunResponse(BaseModel):
    unit_no: int
    action: str                        # 'optimize' / 'revise'
    conversation_no: int               # 所属对话号
    output_text: str
    base_template_source: str          # 'chained' / 'default' / 'manual' / 'none'
    chained_from_unit: int | None      # 链式来源单元号（source='chained' 时有值）
    base_template_preview: str         # 基础模板前 200 字预览（无基础模板时为空）
    model_name: str
    usage: dict                        # {prompt_tokens, completion_tokens, total_tokens}
    elapsed_ms: int
    created_at: datetime


class ConversationOut(BaseModel):
    """对话信息：一个对话 = 一轮 6 阶段（单元 1-6）优化任务。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_no: int
    created_at: datetime
    completed_at: datetime | None      # 任务完成时间（未完成时为 None）
    stage_done: int                    # 该对话内已完成（有成功记录）的阶段数 0-6
    last_stage: int | None             # 最近一次运行的单元号
    last_run_at: datetime | None       # 最近一次运行时间


class UnitSummary(BaseModel):
    """单元概览（驱动用户端链式进度条）。"""
    unit_no: int
    name: str | None                   # 用户自定义显示名；未设置时为 None（前端兜底显示「单元 N」）
    has_chained_base: bool             # 上一单元是否存在成功输出（单元 1 恒 False）
    chained_from_unit: int | None
    last_run_at: datetime | None       # 当前用户在该单元最近一次运行时间


# ---------- 管理端：账号 ----------

class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=128, description="密码（至少 6 位）")
    role: str = Field("user", pattern="^(admin|user)$", description="角色：admin/user")


class PasswordResetRequest(BaseModel):
    password: str = Field(..., min_length=6, max_length=128, description="新密码（至少 6 位）")


# ---------- 管理端：审计 ----------

class AuditSummary(BaseModel):
    """审计列表摘要（输入输出截断，详情走单独端点）。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    unit_no: int
    action: str
    status: str
    conversation_no: int
    base_template_source: str
    input_preview: str
    output_preview: str | None
    total_tokens: int
    elapsed_ms: int | None
    is_deleted: bool
    display_name: str | None
    created_at: datetime


class AuditDetail(AuditSummary):
    """审计单条完整详情。"""
    input_prompt: str
    unit_instruction: str
    base_template: str
    output_text: str | None
    error_message: str | None
    model_name: str | None
    prompt_tokens: int
    completion_tokens: int


class RecordRenameRequest(BaseModel):
    """用户端：对话记录重命名。"""
    name: str = Field(..., min_length=1, max_length=50, description="记录名称")


class UnitRenameRequest(BaseModel):
    """用户端：优化单元重命名。"""
    name: str = Field(..., min_length=1, max_length=50, description="单元名称")


class AuditPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AuditSummary]


# ---------- 管理端：配置 ----------

class UnitConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    unit_no: int
    name: str
    default_template: str
    unit_instruction: str
    updated_at: datetime | None


class UnitConfigUpdate(BaseModel):
    name: str = Field("", max_length=100)
    default_template: str = Field("", max_length=20000)  # 允许为空：默认不预填模板
    unit_instruction: str = Field("", max_length=20000)


class GlobalConfigOut(BaseModel):
    global_instruction_s1: str          # 首次对话（单元 1）指令
    global_instruction_s2: str          # 后续对话（单元 2-6）统一调用指令
    global_instruction_s3: str          # 修改提示词指令


class GlobalConfigUpdate(BaseModel):
    global_instruction_s1: str | None = Field(None, max_length=20000)
    global_instruction_s2: str | None = Field(None, max_length=20000)
    global_instruction_s3: str | None = Field(None, max_length=20000)


# ---------- 管理端：LLM 模型配置（GPT 接口预留） ----------

class PlatformPreset(BaseModel):
    key: str
    label: str
    base_url: str
    default_model: str
    reasoning: bool


class ModelConfigOut(BaseModel):
    platform: str                        # 平台 key（openai/openrouter/moonshot/zhipu/dashscope/custom）
    model: str                           # 模型名（自由填写）
    base_url: str
    reasoning_enabled: bool              # 是否为推理模型（调用时附带 reasoning 参数）
    api_key_masked: str                  # 掩码后的 API Key（如 sk-abc***wxyz，不明文展示）
    has_api_key: bool                    # 是否已配置 Key
    platforms: list[PlatformPreset]      # 平台预设（前端下拉）


class ModelConfigUpdate(BaseModel):
    platform: str = Field("openai", max_length=30, description="平台 key")
    model: str = Field(..., min_length=1, max_length=200, description="模型名，自由填写")
    base_url: str = Field("", max_length=500)
    api_key: str = Field("", max_length=500, description="留空表示不修改")
    reasoning_enabled: bool | None = Field(None, description="是否为推理模型；缺省跟随平台默认")
