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


# ============================================================
# 10. CompanyProduct -- 驾驶舱 Phase2: 当前企业生产的产品 (产能/状态)
#    与 kb_products (知识库结构化产品) 区分: 本表面向"经营驾驶舱",
#    描述企业自身在产产品 + 月产能 + 状态, 驱动 BOM/订单/缺件计算。
# ============================================================
class CompanyProduct(Base):
    __tablename__ = "kb_company_products"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    company_id = Column(BigInteger, nullable=False, index=True, comment="所属企业ID")
    product_name = Column(String(200), nullable=False, comment="产品名称")
    product_model = Column(String(200), nullable=True, index=True, comment="产品型号")
    product_type = Column(String(80), nullable=True, comment="整机|主板|模组|...")
    description = Column(Text, nullable=True)
    monthly_capacity = Column(Integer, nullable=True, comment="月产能")
    unit = Column(String(20), nullable=False, default="台", comment="产能/用量单位")
    status = Column(String(20), nullable=False, default="active",
                    comment="active|paused|eol")
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        Index("idx_cprod_company_status", "company_id", "status"),
    )


# ============================================================
# 11. ProductBomItem -- 产品 BOM 零件
#    preferred_supplier_company_id 指向产业链上游企业 (CompanyCache.id),
#    用于缺件推荐动作 (联系上游 / 关系缺失标记)。
# ============================================================
class ProductBomItem(Base):
    __tablename__ = "kb_product_bom_items"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    product_id = Column(BigInteger, nullable=False, index=True, comment="CompanyProduct.id")
    part_number = Column(String(120), nullable=False, index=True, comment="零件号")
    part_name = Column(String(200), nullable=False, comment="零件名称")
    category_name = Column(String(120), nullable=True, comment="零件分类")
    qty_per_unit = Column(Float, nullable=False, default=1.0, comment="单台用量")
    unit = Column(String(20), nullable=False, default="个")
    is_critical = Column(Boolean, nullable=False, default=False, comment="是否关键件")
    preferred_supplier_company_id = Column(BigInteger, nullable=True, index=True,
                                           comment="首选上游供应商企业ID")
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        Index("idx_bom_product_part", "product_id", "part_number"),
    )


# ============================================================
# 12. ProductionOrder -- 生产订单
#    status=completed|cancelled 不计入需求; priority 影响缺件严重度。
# ============================================================
class ProductionOrder(Base):
    __tablename__ = "kb_production_orders"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    company_id = Column(BigInteger, nullable=False, index=True)
    product_id = Column(BigInteger, nullable=False, index=True, comment="CompanyProduct.id")
    order_number = Column(String(80), nullable=False, index=True)
    customer_company_id = Column(BigInteger, nullable=True, comment="下游客户企业ID")
    quantity = Column(Integer, nullable=False)
    due_date = Column(DateTime, nullable=True)
    priority = Column(String(20), nullable=False, default="normal",
                      comment="urgent|high|normal|low")
    status = Column(String(20), nullable=False, default="open",
                    comment="open|confirmed|in_progress|completed|cancelled")
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        Index("idx_order_company_status", "company_id", "status", "priority"),
    )


# ============================================================
# 13. DemandForecast -- 预测需求
# ============================================================
class DemandForecast(Base):
    __tablename__ = "kb_demand_forecasts"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    company_id = Column(BigInteger, nullable=False, index=True)
    product_id = Column(BigInteger, nullable=False, index=True, comment="CompanyProduct.id")
    forecast_period = Column(String(20), nullable=False, comment="如 2026-08")
    forecast_quantity = Column(Integer, nullable=False)
    confidence = Column(Float, nullable=False, default=0.7, comment="0-1")
    source_type = Column(String(30), nullable=False, default="manual",
                         comment="manual|ai|history")
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        Index("idx_forecast_company_product", "company_id", "product_id"),
    )


# ============================================================
# 14. InventoryItem -- 库存 (按企业 × 零件号)
#    可用库存 = on_hand_qty - reserved_qty; 安全库存用于预警。
# ============================================================
class InventoryItem(Base):
    __tablename__ = "kb_inventory_items"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    company_id = Column(BigInteger, nullable=False, index=True)
    part_number = Column(String(120), nullable=False, index=True)
    part_name = Column(String(200), nullable=True)
    category_name = Column(String(120), nullable=True)
    on_hand_qty = Column(Integer, nullable=False, default=0, comment="在手库存")
    reserved_qty = Column(Integer, nullable=False, default=0, comment="已预留库存")
    safety_stock_qty = Column(Integer, nullable=False, default=0, comment="安全库存")
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        UniqueConstraint("company_id", "part_number", name="uq_inv_company_part"),
    )


# ============================================================
# 15. Shortage -- 缺件/库存预警 (recalculate 物化, 持久化)
#    shortage_type=shortage  -> 缺口>0 (真正缺件)
#    shortage_type=warning   -> 可用库存<安全库存 但 未缺货
#    relationship_missing    -> 首选供应商与本企业无直接上下游关系
# ============================================================
class Shortage(Base):
    __tablename__ = "kb_shortages"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    company_id = Column(BigInteger, nullable=False, index=True)
    product_id = Column(BigInteger, nullable=True, index=True,
                        comment="代表关联产品 (多产品共用零件时取首个)")
    product_name = Column(String(300), nullable=True, comment="关联产品名 (可能多个, /分隔)")
    part_number = Column(String(120), nullable=False, index=True)
    part_name = Column(String(200), nullable=False)
    category_name = Column(String(120), nullable=True)
    shortage_type = Column(String(20), nullable=False, comment="shortage|warning")
    required_qty = Column(Float, nullable=False, default=0.0, comment="BOM 需求量")
    available_qty = Column(Float, nullable=False, default=0.0,
                           comment="可用库存 = on_hand - reserved")
    shortage_qty = Column(Float, nullable=False, default=0.0,
                          comment="缺口 = required - available (>0 为缺件)")
    safety_stock_qty = Column(Integer, nullable=False, default=0)
    unit = Column(String(20), nullable=False, default="个")
    is_critical = Column(Boolean, nullable=False, default=False)
    severity = Column(String(20), nullable=False, default="medium",
                      comment="critical|high|medium|low")
    status = Column(String(20), nullable=False, default="open", comment="open|resolved")
    preferred_supplier_company_id = Column(BigInteger, nullable=True, index=True)
    relationship_missing = Column(Boolean, nullable=False, default=False,
                                  comment="首选供应商是否与本企业无直接关系")
    affected_order_numbers = Column(Text, nullable=True, comment="JSON 数组: 受影响订单号")
    affected_product_ids = Column(Text, nullable=True, comment="JSON 数组: 受影响产品ID")
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        Index("idx_shortage_company_type", "company_id", "shortage_type", "status"),
    )


# ============================================================
# 16. RfqRecord -- 询价单 (缺件后的采购动作闭环)
#    轻量模型, 复用 KB 数据库 (与 Phase 1 一致, 不切 pc_industry 全 ORM)。
#    Phase 2 Dashboard 的 shortage_id / product_id / recommended_action_id
#    等尚未落地的字段统一存入 context_json, 不强依赖外部模型。
# ============================================================
class RfqRecord(Base):
    __tablename__ = "kb_rfqs"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    rfq_number = Column(String(64), nullable=False, unique=True, index=True,
                        comment="业务编号 RFQ-YYYY-NNNN")
    buyer_company_id = Column(BigInteger, nullable=False, index=True, comment="买方公司ID")
    title = Column(String(300), nullable=False)
    raw_query = Column(Text, nullable=True, comment="原始用户询价文本")
    part_number = Column(String(200), nullable=True, index=True)
    part_name = Column(String(200), nullable=True)
    quantity = Column(Integer, nullable=False, default=1)
    unit = Column(String(20), nullable=False, default="个")
    target_price = Column(Float, nullable=True, comment="目标单价")
    lead_time_days = Column(Integer, nullable=True, comment="期望交期(天)")
    accept_alternatives = Column(Boolean, nullable=False, default=False)
    scenario = Column(String(40), nullable=True,
                      comment="shortage|sourcing|cost_down|...")
    status = Column(String(20), nullable=False, default="draft",
                    comment="draft|sent|quoted|closed|cancelled")
    created_by = Column(String(100), nullable=True, comment="创建人 user_id")

    # Phase 2 兼容: shortage_id / product_id / recommended_action_id 等
    # 未落地的外部引用统一存 JSON, 不建强外键。
    context_json = Column(Text, nullable=True, comment="Phase2 兼容字段 JSON")

    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        Index("idx_rfq_buyer_status", "buyer_company_id", "status"),
    )


# ============================================================
# 17. RfqSupplierLink -- RFQ × 候选供应商 (供应商线索)
#    一条记录 = 一个供应商收到的一条 RFQ 线索。
#    status: pending(已关联未发送) -> sent(RFQ已发送) -> viewed(供应商已查看)
#            -> quoted(已报价) | declined(已拒绝) | expired
# ============================================================
class RfqSupplierLink(Base):
    __tablename__ = "kb_rfq_suppliers"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    rfq_id = Column(BigInteger, nullable=False, index=True)
    supplier_company_id = Column(BigInteger, nullable=False, index=True)
    match_score = Column(Float, nullable=True, comment="匹配分 0-1")
    match_reason = Column(Text, nullable=True, comment="匹配理由")
    status = Column(String(20), nullable=False, default="pending",
                    comment="pending|sent|viewed|quoted|declined|expired")
    sent_at = Column(DateTime, nullable=True)
    viewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)

    __table_args__ = (
        UniqueConstraint("rfq_id", "supplier_company_id", name="uq_rfq_supplier"),
        Index("idx_rfq_supplier_status", "supplier_company_id", "status"),
    )


# ============================================================
# 18. QuotationRecord -- 供应商报价
# ============================================================
class QuotationRecord(Base):
    __tablename__ = "kb_quotations"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    rfq_id = Column(BigInteger, nullable=False, index=True)
    supplier_company_id = Column(BigInteger, nullable=False, index=True)
    part_number = Column(String(200), nullable=True)
    unit_price = Column(Float, nullable=False, comment="报价单价")
    currency = Column(String(10), nullable=False, default="CNY")
    moq = Column(Integer, nullable=True, comment="最小起订量")
    lead_time_days = Column(Integer, nullable=True, comment="报价交期(天)")
    stock_qty = Column(Integer, nullable=True, comment="现货库存")
    valid_until = Column(DateTime, nullable=True, comment="报价有效期")
    is_in_stock = Column(Boolean, nullable=False, default=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)

    __table_args__ = (
        Index("idx_quote_rfq_supplier", "rfq_id", "supplier_company_id"),
    )


# ============================================================
# 19. AuditQueueItem -- 审核队列 (轻量, 不做复杂工作流)
#    item_type: supplier_capability | rfq_supplier_match | quotation_anomaly
#    status:    pending | approved | rejected
# ============================================================
class AuditQueueItem(Base):
    __tablename__ = "kb_audit_queue"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    item_type = Column(String(40), nullable=False, index=True,
                       comment="supplier_capability|rfq_supplier_match|quotation_anomaly")
    entity_id = Column(BigInteger, nullable=True, comment="关联实体ID (link_id/quote_id/...)")
    company_id = Column(BigInteger, nullable=True, index=True)
    title = Column(String(300), nullable=False)
    payload_json = Column(Text, nullable=True, comment="审核上下文 JSON")
    status = Column(String(20), nullable=False, default="pending",
                    comment="pending|approved|rejected")
    review_note = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)
    reviewed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_audit_status_type", "status", "item_type"),
    )


# ============================================================
# 20. DemoScenario -- 演示场景沙盘
#    一个 scenario_id (如 default_mvp_demo) 标识一次独立演示会话。
#    所有演示变化 (订单/库存/RFQ/报价/事件) 都带 scenario_id,
#    重置只删除该 scenario_id 下的演示数据, 不触碰基线业务表。
# ============================================================
class DemoScenario(Base):
    __tablename__ = "demo_scenarios"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    scenario_id = Column(String(64), nullable=False, unique=True, index=True,
                         comment="场景标识 如 default_mvp_demo")
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="active",
                    comment="active|archived|reset")
    primary_company_ids = Column(Text, nullable=True,
                                  comment="JSON 数组: 可登录主视角企业ID")
    config_json = Column(Text, nullable=True, comment="场景配置 JSON")
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)


# ============================================================
# 21. DemoEvent -- 演示事件日志 (因果链叙事)
#    每个动作产生一条或多条事件, parent_event_id 串联因果链。
#    phase 标识分阶段按钮, event_type 标识事件类型。
# ============================================================
class DemoEvent(Base):
    __tablename__ = "demo_events"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    scenario_id = Column(String(64), nullable=False, index=True)
    seq = Column(Integer, nullable=False, comment="全局递增序号, 排序用")
    phase = Column(String(40), nullable=True,
                   comment="generate_orders|consume_inventory|recalculate_shortages|"
                           "generate_rfq|simulate_quotes|execute_replenishment|select_alternative")
    action_log_id = Column(BigInteger, nullable=True, index=True, comment="触发该事件的动作日志ID")
    company_id = Column(BigInteger, nullable=False, index=True, comment="事件主体企业ID")
    company_name = Column(String(200), nullable=True)
    linked_company_id = Column(BigInteger, nullable=True,
                               comment="联动企业ID (上游/下游/支撑)")
    linked_company_name = Column(String(200), nullable=True)
    event_type = Column(String(60), nullable=False,
                        comment="order_created|order_demand_received|upstream_demand_forecast|"
                                "inventory_consumed|shortage_triggered|no_direct_supplier|"
                                "rfq_created|rfq_received|quote_received|replenishment_executed|"
                                "order_confirmed|transport_task|alternative_selected|...")
    title = Column(String(300), nullable=False)
    detail = Column(Text, nullable=True)
    payload_json = Column(Text, nullable=True, comment="结构化载荷 JSON")
    parent_event_id = Column(BigInteger, nullable=True, comment="父事件ID (因果链)")
    created_at = Column(DateTime, nullable=False, default=_now)

    __table_args__ = (
        Index("idx_demo_event_scenario_seq", "scenario_id", "seq"),
        Index("idx_demo_event_company", "scenario_id", "company_id"),
    )


# ============================================================
# 22. DemoActionLog -- 演示动作执行日志 (审计)
#    每次按按钮 = 一条 action_log, 记录请求/结果/产生的事件。
# ============================================================
class DemoActionLog(Base):
    __tablename__ = "demo_action_logs"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    scenario_id = Column(String(64), nullable=False, index=True)
    company_id = Column(BigInteger, nullable=False, index=True, comment="操作的主视角企业")
    action_type = Column(String(60), nullable=False,
                         comment="generate_orders|consume_inventory|recalculate_shortages|"
                                 "generate_rfq|simulate_quotes|execute_replenishment|select_alternative")
    request_json = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True, comment="动作结果摘要 JSON")
    event_ids_json = Column(Text, nullable=True, comment="产生的事件ID列表 JSON")
    status = Column(String(20), nullable=False, default="success",
                    comment="success|partial|failed|no_direct_supplier")
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)


# ============================================================
# 23. DemoCompanyState -- 演示企业状态快照 (缓存)
#    每个场景 × 企业的当前演示状态聚合 (基线 + 演示增量)。
#    recalculate_shortages 等动作刷新本表。
# ============================================================
class DemoCompanyState(Base):
    __tablename__ = "demo_company_states"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    scenario_id = Column(String(64), nullable=False, index=True)
    company_id = Column(BigInteger, nullable=False, index=True)
    company_name = Column(String(200), nullable=True)
    is_primary = Column(Boolean, nullable=False, default=False,
                        comment="是否可登录主视角企业")
    role = Column(String(50), nullable=True)
    chain_position = Column(String(20), nullable=True)
    state_json = Column(Text, nullable=True,
                        comment="聚合状态 JSON: orders/inventory/shortages/rfq 摘要")
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        UniqueConstraint("scenario_id", "company_id", name="uq_demo_state_company"),
    )


# ============================================================
# 24. DemoInventoryOverride -- 演示库存增量 (消耗/补货)
#    不修改 kb_inventory_items 基线; 演示可用库存 =
#      baseline_on_hand - baseline_reserved - consumed_qty + replenished_qty
# ============================================================
class DemoInventoryOverride(Base):
    __tablename__ = "demo_inventory_overrides"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    scenario_id = Column(String(64), nullable=False, index=True)
    company_id = Column(BigInteger, nullable=False, index=True)
    part_number = Column(String(120), nullable=False, index=True)
    part_name = Column(String(200), nullable=True)
    category_name = Column(String(120), nullable=True)
    baseline_on_hand = Column(Integer, nullable=False, default=0)
    baseline_reserved = Column(Integer, nullable=False, default=0)
    safety_stock_qty = Column(Integer, nullable=False, default=0)
    consumed_qty = Column(Integer, nullable=False, default=0, comment="演示消耗量")
    replenished_qty = Column(Integer, nullable=False, default=0, comment="演示补货量")
    unit = Column(String(20), nullable=False, default="个")
    source = Column(String(40), nullable=True,
                    comment="consume_inventory|execute_replenishment|select_alternative")
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        UniqueConstraint("scenario_id", "company_id", "part_number",
                         name="uq_demo_inv_override"),
    )


# ============================================================
# 25. DemoOrder -- 演示生成订单 (场景内, 不写入 kb_production_orders)
# ============================================================
class DemoOrder(Base):
    __tablename__ = "demo_orders"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    scenario_id = Column(String(64), nullable=False, index=True)
    company_id = Column(BigInteger, nullable=False, index=True, comment="生产方(主视角)企业")
    product_id = Column(BigInteger, nullable=False, index=True)
    product_name = Column(String(200), nullable=True)
    order_number = Column(String(80), nullable=False, index=True,
                          comment="DEMO-ORD-...")
    customer_company_id = Column(BigInteger, nullable=True, comment="下游客户企业ID")
    customer_company_name = Column(String(200), nullable=True)
    quantity = Column(Integer, nullable=False)
    due_date = Column(DateTime, nullable=True)
    priority = Column(String(20), nullable=False, default="normal")
    status = Column(String(20), nullable=False, default="open",
                    comment="open|confirmed|in_progress|completed|cancelled")
    event_id = Column(BigInteger, nullable=True, comment="关联事件ID")
    created_at = Column(DateTime, nullable=False, default=_now)

    __table_args__ = (
        Index("idx_demo_order_company_status", "company_id", "status"),
    )


# ============================================================
# 26. DemoRfq -- 演示询价单 (场景内, 不写入 kb_rfqs)
#    candidates_json 存直接关系候选供应商列表 (仅直接上下游/支撑企业)。
# ============================================================
class DemoRfq(Base):
    __tablename__ = "demo_rfqs"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    scenario_id = Column(String(64), nullable=False, index=True)
    company_id = Column(BigInteger, nullable=False, index=True, comment="买方(主视角)企业")
    rfq_number = Column(String(64), nullable=False, index=True, comment="DEMO-RFQ-...")
    title = Column(String(300), nullable=False)
    part_number = Column(String(200), nullable=True, index=True)
    part_name = Column(String(200), nullable=True)
    quantity = Column(Integer, nullable=False, default=1)
    unit = Column(String(20), nullable=False, default="个")
    target_price = Column(Float, nullable=True)
    lead_time_days = Column(Integer, nullable=True)
    accept_alternatives = Column(Boolean, nullable=False, default=False)
    scenario = Column(String(40), nullable=True, comment="shortage|sourcing|cost_down")
    status = Column(String(20), nullable=False, default="draft",
                    comment="draft|sent|quoted|closed|cancelled")
    candidates_json = Column(Text, nullable=True,
                             comment="JSON: [{supplier_company_id, supplier_name, direction, "
                                     "match_score, match_reason, status}]")
    selected_supplier_company_id = Column(BigInteger, nullable=True)
    shortage_event_id = Column(BigInteger, nullable=True, comment="触发改 RFQ 的缺件事件ID")
    event_id = Column(BigInteger, nullable=True, comment="RFQ 创建事件ID")
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        Index("idx_demo_rfq_company_status", "company_id", "status"),
    )


# ============================================================
# 27. DemoQuotation -- 演示供应商报价 (场景内, 不写入 kb_quotations)
# ============================================================
class DemoQuotation(Base):
    __tablename__ = "demo_quotations"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    scenario_id = Column(String(64), nullable=False, index=True)
    rfq_id = Column(BigInteger, nullable=False, index=True)
    supplier_company_id = Column(BigInteger, nullable=False, index=True)
    supplier_name = Column(String(200), nullable=True)
    part_number = Column(String(200), nullable=True)
    unit_price = Column(Float, nullable=False)
    currency = Column(String(10), nullable=False, default="CNY")
    moq = Column(Integer, nullable=True)
    lead_time_days = Column(Integer, nullable=True)
    stock_qty = Column(Integer, nullable=True)
    is_in_stock = Column(Boolean, nullable=False, default=False)
    note = Column(Text, nullable=True)
    event_id = Column(BigInteger, nullable=True, comment="报价事件ID")
    created_at = Column(DateTime, nullable=False, default=_now)

    __table_args__ = (
        UniqueConstraint("rfq_id", "supplier_company_id", name="uq_demo_quote_supplier"),
        Index("idx_demo_quote_rfq", "rfq_id"),
    )
