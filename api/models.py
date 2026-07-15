"""
SQLAlchemy ORM 模型
与 database/01_schema 对齐，默认 SQLite 兼容
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, Integer, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from api.base import Base


def _uuid():
    return uuid.uuid4().hex[:12]


def _now():
    return datetime.now()


# ── 用户 / 认证 ──────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(String(12), primary_key=True, default=_uuid)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    name = Column(String(100), default="")
    company = Column(String(200), default="")
    role = Column(String(20), default="buyer")  # buyer / supplier / admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_now)

    rfqs = relationship("RFQ", back_populates="buyer", lazy="selectin")


# ── 供应商 ───────────────────────────────────────────────────

class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(String(12), primary_key=True, default=_uuid)
    name = Column(String(200), nullable=False)
    location = Column(String(100), default="")
    region = Column(String(50), default="")
    categories = Column(JSON, default=list)
    brands = Column(JSON, default=list)
    qualifications = Column(JSON, default=list)
    moq = Column(Integer, default=0)
    lead_time_weeks = Column(Integer, default=0)
    response_speed = Column(String(50), default="")
    data_source = Column(String(50), default="")
    match_score = Column(Float, default=0.0)
    rating = Column(Float, default=0.0)
    status = Column(String(20), default="approved")  # pending / approved / rejected
    updated_at = Column(DateTime, default=_now, onupdate=_now)


# ── 询价单 ───────────────────────────────────────────────────

class RFQ(Base):
    __tablename__ = "rfqs"

    id = Column(String(12), primary_key=True, default=_uuid)
    buyer_id = Column(String(12), ForeignKey("users.id"), nullable=True)
    thread_id = Column(String(64), default="")
    raw_query = Column(Text, default="")
    parsed_spec = Column(JSON, nullable=True)
    normalized_spec = Column(JSON, nullable=True)
    alternatives = Column(JSON, default=list)
    matched_suppliers = Column(JSON, default=list)
    rfq_doc = Column(Text, default="")
    status = Column(String(20), default="draft")  # draft / sent / quoted / closed
    lead_grade = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_now)

    buyer = relationship("User", back_populates="rfqs", lazy="selectin")


# ── 线索 ─────────────────────────────────────────────────────

class Lead(Base):
    __tablename__ = "leads"

    id = Column(String(12), primary_key=True, default=_uuid)
    rfq_id = Column(String(12), ForeignKey("rfqs.id"), nullable=True)
    supplier_id = Column(String(12), ForeignKey("suppliers.id"), nullable=True)
    grade = Column(String(2), default="C")  # A/B/C/D
    score = Column(Integer, default=0)
    reasons = Column(JSON, default=list)
    status = Column(String(20), default="new")  # new / contacted / won / lost
    created_at = Column(DateTime, default=_now)


# ── 审核记录 ─────────────────────────────────────────────────

class AuditRecord(Base):
    __tablename__ = "audit_records"

    id = Column(String(12), primary_key=True, default=_uuid)
    target_type = Column(String(20), nullable=False)  # supplier / alternative
    target_id = Column(String(12), nullable=False)
    action = Column(String(20), nullable=False)  # approve / reject / mark_risk
    operator_id = Column(String(12), nullable=True)
    note = Column(Text, default="")
    created_at = Column(DateTime, default=_now)
