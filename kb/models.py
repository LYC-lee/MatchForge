"""
知识库 ORM 模型 -- Source of Truth。

设计要点:
  - KnowledgeManual: 每家公司 × (product|business) × (zh|en) 一条手册，含版本/hash/来源
  - Product: 结构化产品实体 (支持未来产品比较/精确型号查询)
  - KnowledgeChunk: 语义切片，含 company_id/language/chunk_type/product_model/business_type
  - KbTask: 后台任务 (状态/进度/断点续跑)
  - RagTrace: RAG 检索追溯 (request_id/召回chunk/分数/来源)
  - CompanyAccess: 最小公司访问校验 (复用/兜底)

Milvus 仅作为索引层; 全部原始知识持久化在此 -> rebuild_vector_index 可全量重建。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)

from kb.db import Base


# SQLite 需要 INTEGER PRIMARY KEY 才能自增; MySQL 用 BIGINT。
# 跨库兼容: SQLite 上渲染为 INTEGER, MySQL 上渲染为 BIGINT。
BigIntPK = BigInteger().with_variant(Integer(), "sqlite")


def _now() -> datetime:
    return datetime.utcnow()


# ============================================================
# 1. KnowledgeManual -- 知识手册 (公司 × 类型 × 语言)
# ============================================================
class KnowledgeManual(Base):
    __tablename__ = "kb_manuals"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    company_id = Column(BigInteger, nullable=False, index=True, comment="公司ID")
    manual_type = Column(String(20), nullable=False, comment="product|business")
    language = Column(String(8), nullable=False, comment="zh|en")
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False, comment="完整手册内容 (Markdown)")

    # 版本与幂等
    version = Column(Integer, nullable=False, default=1)
    content_hash = Column(String(64), nullable=False, comment="内容哈希 (sha256)")
    source_hash = Column(String(64), nullable=False, comment="源数据哈希, 用于增量判断")
    active_version = Column(Boolean, nullable=False, default=True, comment="是否当前活跃版本")

    # 生成状态
    generation_status = Column(String(20), nullable=False, default="completed",
                               comment="completed|failed|partial")

    # 来源追踪
    source_type = Column(String(30), nullable=False, default="ai_generated_demo",
                         comment="company_database|project_file|public_web|ai_generated_demo")
    source_url = Column(String(500), nullable=True)
    source_title = Column(String(300), nullable=True)
    generated_by_ai = Column(Boolean, nullable=False, default=True)
    confidence = Column(Float, nullable=False, default=0.7, comment="0-1")

    generated_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        Index("idx_manual_company_type_lang", "company_id", "manual_type", "language"),
    )


# ============================================================
# 2. Product -- 结构化产品实体 (支持产品比较)
# ============================================================
class Product(Base):
    __tablename__ = "kb_products"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    company_id = Column(BigInteger, nullable=False, index=True)
    product_name = Column(String(200), nullable=False)
    product_series = Column(String(200), nullable=True, comment="产品系列")
    product_model = Column(String(200), nullable=True, index=True, comment="产品型号")
    category = Column(String(100), nullable=True, comment="产品分类")
    positioning = Column(String(300), nullable=True, comment="产品定位/目标客户")

    # 价格 (内部保留完整来源)
    price = Column(Float, nullable=True, comment="单价")
    price_min = Column(Float, nullable=True)
    price_max = Column(Float, nullable=True)
    currency = Column(String(10), nullable=True, default="CNY")
    price_type = Column(String(20), nullable=True, comment="reference|quoted|demo")
    price_confidence = Column(Float, nullable=True)

    # 规格参数 (JSON 文本, 跨数据库兼容)
    specification = Column(Text, nullable=True, comment="规格参数 JSON")
    language = Column(String(8), nullable=False, default="zh")

    # 来源
    source_type = Column(String(30), nullable=False, default="ai_generated_demo")
    source_hash = Column(String(64), nullable=True)
    confidence = Column(Float, nullable=False, default=0.7)
    generated_by_ai = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        Index("idx_product_company_model", "company_id", "product_model"),
    )


# ============================================================
# 3. KnowledgeChunk -- 语义切片 (向量索引的来源)
# ============================================================
class KnowledgeChunk(Base):
    __tablename__ = "kb_chunks"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    chunk_uid = Column(String(80), nullable=False, unique=True,
                      comment="全局唯一 chunk 标识, 同步到向量库主键")
    company_id = Column(BigInteger, nullable=False, index=True)
    manual_id = Column(BigInteger, nullable=False, index=True)
    manual_type = Column(String(20), nullable=False, comment="product|business")
    language = Column(String(8), nullable=False, index=True, comment="zh|en")

    chunk_type = Column(String(40), nullable=False,
                        comment="product_overview/product_specification/product_price/...")
    section = Column(String(200), nullable=True)
    product_id = Column(BigInteger, nullable=True, index=True)
    product_model = Column(String(200), nullable=True, index=True)
    business_type = Column(String(80), nullable=True, comment="业务类型: 采购/ODM/售后...")

    text = Column(Text, nullable=False, comment="切片文本")
    content_hash = Column(String(64), nullable=False, comment="text sha256")

    # 来源追踪
    source_type = Column(String(30), nullable=False, default="ai_generated_demo")
    source_url = Column(String(500), nullable=True)
    source_file = Column(String(500), nullable=True)
    generated_by_ai = Column(Boolean, nullable=False, default=True)
    confidence = Column(Float, nullable=False, default=0.7)
    version = Column(Integer, nullable=False, default=1)
    active = Column(Boolean, nullable=False, default=True, comment="是否活跃 (去重/版本切换)")

    # 向量库同步状态
    vector_synced = Column(Boolean, nullable=False, default=False)
    vector_backend = Column(String(20), nullable=True, comment="milvus|local")

    created_at = Column(DateTime, nullable=False, default=_now)

    __table_args__ = (
        Index("idx_chunk_retrieval", "company_id", "language", "manual_type", "active"),
        Index("idx_chunk_product", "company_id", "product_model", "chunk_type"),
        Index("idx_chunk_business", "company_id", "business_type", "chunk_type"),
    )


# ============================================================
# 4. KbTask -- 后台任务 (状态/进度/断点续跑)
# ============================================================
class KbTask(Base):
    __tablename__ = "kb_tasks"

    id = Column(String(64), primary_key=True, comment="task_id (uuid)")
    company_id = Column(BigInteger, nullable=True, index=True, comment="单公司任务时填写")
    task_type = Column(String(30), nullable=False,
                      comment="generate|incremental_update|rebuild_index")
    total_steps = Column(Integer, nullable=False, default=0)
    completed_steps = Column(Integer, nullable=False, default=0)
    progress = Column(Integer, nullable=False, default=0, comment="0-100")
    status = Column(String(20), nullable=False, default="pending",
                    comment="pending|running|completed|partially_completed|failed|cancelled")
    current_stage = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)

    # 断点续跑: 已完成的公司/步骤 (JSON)
    checkpoint = Column(Text, nullable=True, comment="JSON: 已完成 company_id 列表等")

    result_summary = Column(Text, nullable=True, comment="JSON 结果摘要")
    created_at = Column(DateTime, nullable=False, default=_now)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)


# ============================================================
# 5. KbFailure -- 失败记录 (失败隔离 + 重试依据)
# ============================================================
class KbFailure(Base):
    __tablename__ = "kb_failures"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    task_id = Column(String(64), nullable=False, index=True)
    company_id = Column(BigInteger, nullable=True, index=True)
    company_name = Column(String(200), nullable=True)
    generation_stage = Column(String(80), nullable=True,
                              comment="boundary|product_zh|product_en|business_zh|business_en|chunk|embed|index")
    language = Column(String(8), nullable=True)
    manual_type = Column(String(20), nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    error = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_now)


# ============================================================
# 6. RagTrace -- RAG 检索追溯
# ============================================================
class RagTrace(Base):
    __tablename__ = "kb_rag_traces"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    request_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(100), nullable=True)
    company_id = Column(BigInteger, nullable=True, index=True)
    company_ids = Column(String(300), nullable=True, comment="多公司比较时逗号分隔")
    query = Column(Text, nullable=False)
    detected_language = Column(String(8), nullable=True)
    query_intent = Column(String(20), nullable=True, comment="factual|advisory|comparison")
    retrieved_chunk_ids = Column(Text, nullable=True, comment="JSON 列表")
    retrieval_scores = Column(Text, nullable=True, comment="JSON 列表")
    manual_versions = Column(Text, nullable=True)
    source_types = Column(Text, nullable=True)
    model = Column(String(100), nullable=True)
    answer = Column(Text, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=_now)


# ============================================================
# 7. CompanyAccess -- 最小公司访问校验
#    当前项目无完整 RBAC; 此表记录"用户可访问的公司白名单"。
#    默认策略: B2B 平台公开供应商知识 -> 所有登录用户可查询单公司;
#    但服务端仍强制 RAG 检索阶段 company_id 隔离 (见 rag.py)。
#    如需限制, 向此表插入 (user_id, company_id) 即可。
# ============================================================
class CompanyAccess(Base):
    __tablename__ = "kb_company_access"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False, index=True)
    company_id = Column(BigInteger, nullable=False, index=True)
    granted_at = Column(DateTime, nullable=False, default=_now)

    __table_args__ = (
        UniqueConstraint("user_id", "company_id", name="uq_user_company"),
    )


# ============================================================
# 8. CompanyCache -- 从 CSV/MySQL 采集的公司快照 (供生成与隔离使用)
# ============================================================
class CompanyCache(Base):
    __tablename__ = "kb_companies"

    id = Column(BigInteger, primary_key=True, comment="= 源 company_id")
    name = Column(String(200), nullable=False)
    name_en = Column(String(200), nullable=True)
    name_alias = Column(String(500), nullable=True)
    country = Column(String(50), nullable=True)
    region = Column(String(50), nullable=True)
    website = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)

    # 业务边界 (由 boundary.py 填充)
    segment_code = Column(String(80), nullable=True, index=True)
    segment_name_cn = Column(String(120), nullable=True)
    segment_name_en = Column(String(160), nullable=True)
    chain_position = Column(String(20), nullable=True)
    role = Column(String(50), nullable=True, comment="制造商/分销商/ODM...")
    typical_products = Column(Text, nullable=True, comment="JSON 数组")
    business_boundary_json = Column(Text, nullable=True, comment="完整业务边界 JSON")

    confidence_level = Column(String(30), nullable=True)
    source_name = Column(String(200), nullable=True)
    source_url = Column(String(500), nullable=True)

    knowledge_status = Column(String(20), nullable=False, default="none",
                              comment="none|partial|ready")
    last_generated_at = Column(DateTime, nullable=True)
    source_hash = Column(String(64), nullable=True, comment="源数据哈希, 增量判断")
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)


# ============================================================
# 9. CompanyRelationship -- 企业上下游关系 (驾驶舱产业链协同)
#    轻量关系表, 复用 KB 数据库 (本阶段不切换 pc_industry 全 ORM)。
#
#  语义: source_company_id 对 target_company_id 持有 [direction] 关系。
#    direction=upstream   -> target 是 source 的上游 (source 向 target 采购)
#    direction=downstream -> target 是 source 的下游 (source 向 target 供货)
#    direction=support    -> target 向 source 提供支撑服务 (物流/检测/认证)
#  每条货物上下游边建议存两行 (双向视角), 保证 /upstream /downstream 各自可查。
# ============================================================
class CompanyRelationship(Base):
    __tablename__ = "kb_company_relationships"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    source_company_id = Column(BigInteger, nullable=False, index=True, comment="关系发起方公司ID")
    target_company_id = Column(BigInteger, nullable=False, index=True, comment="关系对方公司ID")
    relationship_type = Column(String(40), nullable=False,
                               comment="supply|service|channel|...")
    direction = Column(String(20), nullable=False,
                       comment="upstream|downstream|support")
    product_scope = Column(Text, nullable=True, comment="JSON 数组: 涉及产品/品类")
    business_scope = Column(Text, nullable=True, comment="JSON 数组: 涉及业务范围")
    confidence_level = Column(String(30), nullable=False, default="manual")
    status = Column(String(20), nullable=False, default="active",
                    comment="active|inactive|pending")
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        Index("idx_rel_source_target", "source_company_id", "target_company_id", "direction"),
        Index("idx_rel_direction", "direction"),
        Index("idx_rel_target", "target_company_id"),
    )
