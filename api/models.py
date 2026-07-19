"""
SQLAlchemy ORM 模型
与 database/01_schema DDL 对齐 -- 所有主键使用 BIGINT AUTO_INCREMENT。

历史问题: 旧 ORM 使用 String(12) UUID 作为主键，但真实 DDL 全部是 BIGINT。
已于 P0-04 修复中统一为 BigInteger autoincrement。
"""

from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, Integer, BigInteger, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from api.base import Base


def _now():
    return datetime.now()


# ── 用户 / 认证 ──────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
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
    """供应商主体表 -- 与 deploy/docker/mysql/init/01_matchforge_schema.sql DDL 对齐。

    注意: 品类/品牌/MOQ/交期等信息不在本表，在 supplier_capabilities 表中。
    旧 ORM 中的 categories/brands/moq/lead_time_weeks/data_source 等字段
    在真实数据库中不存在，已移除。查询品类等信息请 JOIN supplier_capabilities。
    """
    __tablename__ = "suppliers"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    enterprise_id = Column(BigInteger, nullable=True, index=True)
    name = Column(String(200), nullable=False)
    location = Column(String(100), nullable=True)
    rating = Column(Float, default=0.0)
    status = Column(String(20), default="pending")  # pending / approved / rejected / needs_review
    contact_phone = Column(String(50), nullable=True)
    contact_email = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


# ── 询价单 ───────────────────────────────────────────────────

class RFQ(Base):
    __tablename__ = "rfqs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    buyer_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
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

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    rfq_id = Column(BigInteger, ForeignKey("rfqs.id"), nullable=True)
    supplier_id = Column(BigInteger, ForeignKey("suppliers.id"), nullable=True)
    grade = Column(String(2), default="C")  # A/B/C/D
    score = Column(Integer, default=0)
    reasons = Column(JSON, default=list)
    status = Column(String(20), default="new")  # new / contacted / won / lost
    created_at = Column(DateTime, default=_now)


# ── 审核记录 ─────────────────────────────────────────────────

class AuditRecord(Base):
    __tablename__ = "audit_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    target_type = Column(String(20), nullable=False)  # supplier / alternative
    target_id = Column(BigInteger, nullable=False)
    action = Column(String(20), nullable=False)  # approve / reject / mark_risk
    operator_id = Column(BigInteger, nullable=True)
    note = Column(Text, default="")
    created_at = Column(DateTime, default=_now)
