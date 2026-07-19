"""
Pydantic 请求/响应模型
与前端 types/procure.ts 和 ai/state.py 对齐
"""

from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field


# ── Auth ─────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    account: str
    password: str

class RegisterRequest(BaseModel):
    name: str
    account: str
    password: str
    company: str = ""
    role: str = "member"
    enterprise_type: str = "other"

class TokenResponse(BaseModel):
    token: str
    refresh_token: str
    user: dict

class UserInfo(BaseModel):
    id: str
    name: str
    account: str
    company: str
    role: str


# ── Procure / SSE ────────────────────────────────────────────

class ProcureRequest(BaseModel):
    query: str = ""
    thread_id: Optional[str] = None
    confirmed_spec: Optional[dict] = None
    phase: str = "spec"  # spec | match


# ── 单个 Agent ───────────────────────────────────────────────

class ParseRequest(BaseModel):
    query: str

class AlternativesRequest(BaseModel):
    spec: dict

class MatchRequest(BaseModel):
    spec: dict
    alternatives: list[dict] = []
    filters: Optional[dict] = None

class RfqGenerateRequest(BaseModel):
    spec: dict
    alternatives: list[dict] = []
    suppliers: list[dict] = []


# ── RFQ ──────────────────────────────────────────────────────

class RfqSubmitRequest(BaseModel):
    rfq_doc: str
    parsed_spec: dict = {}
    target_supplier_ids: list[str] = []


# ── Admin ────────────────────────────────────────────────────

class AuditAction(BaseModel):
    action: str = Field(..., pattern="^(approve|reject|mark_risk)$")
    note: str = ""


# ── 通用 ─────────────────────────────────────────────────────

class ApiResponse(BaseModel):
    ok: bool = True
    data: Any = None
    msg: str = ""

class ErrorResponse(BaseModel):
    code: str
    message: str
    agent: Optional[str] = None
    trace_id: Optional[str] = None
