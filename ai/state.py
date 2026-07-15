"""
MatchForge Graph State 定义
与前端 types/procure.ts 严格对齐
"""

from typing import TypedDict, Optional, Union


class SpecField(TypedDict):
    """规格字段（带置信度）"""
    value: str
    confidence: float
    missing: bool
    editable: bool


class ParamDiff(TypedDict):
    """参数差异项"""
    field: str
    original: str
    alternative: str
    status: str             # 'match' | 'diff' | 'risk'
    note: str


class DiffItem(TypedDict):
    """参数差异项（兼容旧版）"""
    param: str
    original: str
    alternative: str
    type: str               # 'match' | 'diff' | 'risk'


class Alternative(TypedDict):
    """替代料 — 与前端 Alternative 接口对齐"""
    part_name: str
    part: str               # 兼容旧版
    brand: str
    package: str
    key_params: dict
    level: str              # L1/L2/L3/L4/L5
    confidence: float
    verified: bool
    source: str
    updated_at: str
    diffs: list[ParamDiff]
    diff_items: list[DiffItem]  # 兼容旧版
    specs: dict
    reason: str
    note: str


class Supplier(TypedDict):
    """候选供应商 — 与前端 Supplier 接口对齐"""
    id: str
    name: str
    score: float
    category: str
    region: str
    location: str           # 兼容旧版
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
    """线索分级"""
    grade: str              # A/B/C/D
    score: int
    reasons: list[str]


class ProcureState(TypedDict):
    """
    Graph State — 6 个智能体间的共享状态
    与前端 ProcureState 接口对齐
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
    started_at: str
    completed_at: Optional[str]