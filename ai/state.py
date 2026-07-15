"""
MatchForge Graph State 定义
与前端 types/procure.ts 严格对齐

使用 reducer 使 graph 循环时列表字段正确追加而非覆盖
"""

from typing import TypedDict, Optional


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

    带 reducer 的字段:
      - alternatives:    每次返回 append，不覆盖
      - matched_suppliers: 同上
      - errors:          每次返回追加
      - next_agent:      总是覆盖
    """
    thread_id: str
    raw_query: str
    parsed_spec: Optional[dict]
    normalized_spec: Optional[dict]
    alternatives: list[Alternative]
    matched_suppliers: list[Supplier]
    rfq_doc: Optional[str]
    rfq_id: Optional[str]
    lead_grade: Optional[LeadGrade]
    errors: list[str]
    next_agent: str                     # supervisor 路由用
    user_id: Optional[str]              # 用户标识，记忆用
    started_at: str
    completed_at: Optional[str]