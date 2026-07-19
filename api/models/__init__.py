"""
MatchForge 双库 SQLAlchemy ORM 模型
====================================
matchforge 运营库: User, Enterprise, Buyer, Lead
pc_industry 事实库: Company, Part, Supplier, SupplierCapability, RFQ, Quotation

依据: docs/architecture/schema-convergence.md
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime, Enum, Float, Integer,
    String, Text, JSON, ForeignKey, Text as SqlText,
)
from sqlalchemy.orm import declarative_base, relationship

# ── 两个 Base（对应两个库）──
MatchforgeBase = declarative_base()
PcIndustryBase = declarative_base()


# ============================================================
# matchforge 运营库模型
# ============================================================

class Enterprise(MatchforgeBase):
    __tablename__ = "enterprises"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, comment="企业名称")
    type = Column(String(20), nullable=False, comment="buyer=采购方/supplier=供应方")
    credit_code = Column(String(50), comment="统一社会信用代码")
    contact = Column(String(100), comment="联系方式")
    created_at = Column(DateTime, default=datetime.utcnow)


class User(MatchforgeBase):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False, unique=True, comment="用户名")
    name = Column(String(100), default="", comment="用户姓名(展示用)")
    password_hash = Column(String(128), nullable=False, comment="bcrypt 密码哈希")
    enterprise_id = Column(BigInteger, ForeignKey("enterprises.id"), comment="关联企业")
    role = Column(String(20), nullable=False, default="member", comment="用户权限角色: member/enterprise_admin/platform_admin")
    enterprise_type = Column(String(40), default="other", comment="企业类型: manufacturer/component_material/oem_brand/channel_customer/logistics_service/government_park/other")
    company = Column(String(200), default="", comment="企业名称(展示用; 关联企业见 enterprise_id)")
    email = Column(String(100))
    is_active = Column(Boolean, default=True, comment="是否激活")
    created_at = Column(DateTime, default=datetime.utcnow)


class Buyer(MatchforgeBase):
    __tablename__ = "buyers"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    enterprise_id = Column(BigInteger, ForeignKey("enterprises.id"), nullable=False)
    industry = Column(String(50), comment="所属行业")
    created_at = Column(DateTime, default=datetime.utcnow)


class Lead(MatchforgeBase):
    __tablename__ = "leads"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    rfq_id = Column(BigInteger, comment="询价单ID（跨库关联 pc_industry.rfqs.id）")
    supplier_id = Column(BigInteger, comment="供应商ID（跨库关联）")
    grade = Column(String(2), comment="分级 A/B/C/D")
    score = Column(Integer, comment="评分 0-100")
    reasons = Column(JSON, comment="分级原因")
    status = Column(String(20), default="new", comment="new/contacted/won/lost")
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================
# pc_industry 事实库模型
# ============================================================

class Company(PcIndustryBase):
    __tablename__ = "companies"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, comment="公司名称")
    name_en = Column(String(200), comment="英文名称")
    name_alias = Column(String(500), comment="别名/简称")
    country = Column(String(50), comment="国家")
    region = Column(String(50), comment="地区")
    website = Column(String(500), comment="官网")
    description = Column(Text, comment="公司简介")
    confidence_level = Column(String(30), default="unknown", comment="可信度")
    source_name = Column(String(200), comment="数据来源名称")
    source_url = Column(String(500), comment="数据来源链接")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Category(PcIndustryBase):
    __tablename__ = "categories"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True, comment="品类名称")
    parent_id = Column(BigInteger, comment="父品类ID")
    description = Column(Text, comment="品类说明")
    created_at = Column(DateTime, default=datetime.utcnow)


class Part(PcIndustryBase):
    __tablename__ = "parts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    part_number = Column(String(100), nullable=False, comment="料号/型号")
    brand = Column(String(100), nullable=False, comment="品牌")
    category_id = Column(BigInteger, ForeignKey("categories.id"), nullable=False, comment="品类ID")
    category_name = Column(String(50), nullable=False, comment="品类名称（冗余）")
    specs = Column(JSON, comment="规格参数 JSON")
    lifecycle_status = Column(Enum("active", "nrnd", "eol", "obsolete", "unknown"), default="active", comment="生命周期")
    datasheet_url = Column(String(500), comment="Datasheet 链接")
    description = Column(Text, comment="物料描述")
    confidence_level = Column(String(30), default="unknown", comment="可信度")
    source_name = Column(String(200), comment="数据来源")
    source_url = Column(String(500), comment="来源链接")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Supplier(PcIndustryBase):
    __tablename__ = "suppliers"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    company_id = Column(BigInteger, ForeignKey("companies.id"), comment="关联公司ID")
    name = Column(String(200), nullable=False, comment="供应商名称")
    location = Column(String(100), comment="所在地")
    rating = Column(Float, default=0.0, comment="评分 0-5")
    status = Column(Enum("pending", "approved", "rejected", "needs_review"), default="pending", comment="审核状态")
    contact_phone = Column(String(50), comment="联系电话")
    contact_email = Column(String(100), comment="联系邮箱")
    source_name = Column(String(200), comment="数据来源")
    source_url = Column(String(500), comment="来源链接")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SupplierCapability(PcIndustryBase):
    __tablename__ = "supplier_capabilities"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    supplier_id = Column(BigInteger, ForeignKey("suppliers.id"), nullable=False, comment="供应商ID")
    category_id = Column(BigInteger, ForeignKey("categories.id"), nullable=False, comment="品类ID")
    category_name = Column(String(50), nullable=False, comment="品类名称（冗余）")
    brand_names = Column(String(500), comment="代理/覆盖品牌，逗号分隔")
    moq = Column(Integer, comment="最小起订量")
    lead_time_days = Column(Integer, comment="交期（天）")
    region = Column(String(100), comment="供货区域")
    audit_status = Column(Enum("pending", "approved", "rejected", "needs_review"), default="pending", comment="审核状态")
    audit_note = Column(Text, comment="审核备注")
    source_name = Column(String(200), comment="数据来源")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PartAlternative(PcIndustryBase):
    __tablename__ = "part_alternatives"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    original_part_id = Column(BigInteger, ForeignKey("parts.id"), nullable=False, comment="原物料ID")
    alternative_part_id = Column(BigInteger, ForeignKey("parts.id"), nullable=False, comment="替代物料ID")
    original_part_number = Column(String(100), nullable=False, comment="原型号")
    alternative_part_number = Column(String(100), nullable=False, comment="替代型号")
    level = Column(Enum("l1", "l2", "l3", "l4", "l5"), default="l3", comment="替代等级")
    level_desc = Column(String(100), comment="等级描述")
    confidence = Column(Float, default=0.80, comment="置信度 0-1")
    param_diff = Column(Text, comment="参数差异说明")
    risk_note = Column(Text, comment="风险说明")
    source_name = Column(String(200), comment="数据来源")
    source_url = Column(String(500), comment="来源链接")
    review_status = Column(Enum("pending", "approved", "rejected", "needs_review"), default="pending", comment="审核状态")
    reviewed_by = Column(String(50), comment="审核人")
    reviewed_at = Column(DateTime, comment="审核时间")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RFQ(PcIndustryBase):
    __tablename__ = "rfqs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    rfq_number = Column(String(50), nullable=False, unique=True, comment="询价单号")
    title = Column(String(200), comment="询价标题")
    raw_query = Column(Text, comment="原始需求描述")
    part_id = Column(BigInteger, ForeignKey("parts.id"), comment="目标物料ID")
    part_number = Column(String(100), comment="目标料号")
    quantity = Column(Integer, comment="需求数量")
    unit = Column(String(20), default="pcs", comment="单位")
    target_price = Column(Float, comment="目标单价（USD）")
    lead_time_weeks = Column(Integer, comment="期望交期（周）")
    accept_alternatives = Column(Boolean, default=True, comment="是否接受替代料")
    scenario = Column(Enum("stockout", "cost_reduction", "new_sourcing"), default="stockout", comment="场景")
    status = Column(Enum("draft", "sent", "quoted", "closed", "cancelled"), default="draft", comment="状态")
    created_by = Column(String(50), comment="创建人")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Quotation(PcIndustryBase):
    __tablename__ = "quotations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    rfq_id = Column(BigInteger, ForeignKey("rfqs.id"), nullable=False, comment="RFQ ID")
    supplier_id = Column(BigInteger, ForeignKey("suppliers.id"), nullable=False, comment="供应商ID")
    part_number = Column(String(100), comment="报价料号")
    unit_price = Column(Float, nullable=False, comment="单价（USD）")
    moq = Column(Integer, comment="最小起订量")
    lead_time_days = Column(Integer, comment="报价交期（天）")
    stock_qty = Column(Integer, comment="库存数量")
    valid_until = Column(Date, comment="报价有效期")
    is_in_stock = Column(Boolean, default=False, comment="是否有库存")
    note = Column(Text, comment="备注")
    created_at = Column(DateTime, default=datetime.utcnow)
