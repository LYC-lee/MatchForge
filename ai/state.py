"""
MatchForge Graph State 定义
与前端 types/procure.ts 严格对齐

使用 LangGraph add_messages reducer 保证消息列表正确追加
"""

from typing import TypedDict, Optional, Any, Annotated

from langgraph.graph import add_messages


class SpecField(TypedDict):
    value: str
    confidence: float
    missing: bool
    editable: bool


class ParamDiff(TypedDict):
    field: str
    original: str
    alternative: str
    status: str             # 'match' | 'diff' | 'risk'
    note: str


class DiffItem(TypedDict):
    param: str
    original: str
    alternative: str
    type: str               # 'match' | 'diff' | 'risk'


class Alternative(TypedDict):
    part_name: str
    part: str
    brand: str
    package: str
    key_params: dict
    level: str              # L1/L2/L3/L4/L5
    confidence: float
    verified: bool
    source: str
    updated_at: str
    diffs: list[ParamDiff]
    diff_items: list[DiffItem]
    specs: dict
    reason: str
    note: str


class Supplier(TypedDict):
    id: str
    name: str
    score: float
    category: str
    region: str
    location: str
    categories: list[str]
    brands: list[str]
    qualifications: list[str]
    moq: int
    lead_time_weeks: int
    in_stock: bool
    response_speed: str
    data_source: str
    updated_at: str
    confirmed_stock: bool
    confirmed_lead: bool
    confirmed_price: bool
    match_score: float


class LeadGrade(TypedDict):
    grade: str              # A/B/C/D
    score: int
    reasons: list[str]


class ProcureState(TypedDict):
    """
    Graph State — 6 个智能体间的共享状态

    核心字段:
      - messages: 使用 add_messages reducer 的对话历史（LangGraph 标准）
      - next_agent: supervisor 路由目标，子 Agent 完成后设为 None
      - route_reason: supervisor 路由理由，调试/日志追踪

    业务字段（带 reducer 的列表字段在 graph 循环时正确追加）:
      - alternatives:    每次返回 append，不覆盖
      - matched_suppliers: 同上
      - errors:          每次返回追加
    """
    # ── LangGraph 标准字段 ──
    messages: Annotated[list, add_messages]
    next_agent: str                     # supervisor 路由用
    route_reason: str | None            # 路由理由，调试/日志

    # ── 会话标识 ──
    thread_id: str
    user_id: Optional[str]              # 用户标识，记忆用

    # ── 执行追踪（防 supervisor 路由循环）──
    _attempted_agents: list[str]          # 已尝试执行的 Agent 列表

    # ── 业务字段 ──
    raw_query: str
    parsed_spec: Optional[dict]
    normalized_spec: Optional[dict]
    alternatives: list[Alternative]
    matched_suppliers: list[Supplier]
    rfq_doc: Optional[str]
    rfq_id: Optional[str]
    lead_grade: Optional[LeadGrade]
    errors: list[str]
    chat_response: Optional[str]        # 💬 聊天 Agent 回复
    started_at: str
    completed_at: Optional[str]