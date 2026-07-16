"""
企业产业链种子数据 (驾驶舱 Phase 1)。

构造一条电脑制造产业链 (6 家企业) + 上下游关系:

  毅诚被动元件(9006, 被动元件, upstream)
      │ supply (下游: 创捷)
      ▼
  华芯微电子(9001, 半导体芯片, upstream)
      │ supply (下游: 创捷)
      ▼
  创捷主板模组(9002, PCB/PCBA, upstream)  ◄── 上游: 毅诚 + 华芯
      │ supply (下游: 鼎云)
      ▼
  鼎云整机制造(9003, ODM/EMS, midstream)  ◄── 上游: 创捷
      │ channel (下游: 星河)
      ▼
  星河数码渠道(9005, 分销, downstream)     ◄── 上游: 鼎云

  远达供应链服务(9004, 物流, support) ── support ──> 创捷 / 鼎云 / 星河

幂等: 重复执行只更新不重复插入 (公司按 id, 关系按 source+target+direction)。
知识: 为每家企业写入少量手工艺知识 (manual + chunks + 向量), 无需 LLM/API Key
      (embedding 走 hashbow 降级, 向量库走 Local 降级)。

运行: python scripts/seed_enterprise_chain.py
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# 确保项目根在 sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from kb.db import init_db, session_scope
from kb.models import CompanyCache, CompanyRelationship, KnowledgeChunk, KnowledgeManual

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("seed_enterprise_chain")


# ============================================================
# 企业定义 (ID 9001-9006, 避免与现有 30 家公司碰撞)
# ============================================================
COMPANIES = [
    {
        "id": 9001,
        "name": "华芯微电子有限公司",
        "name_en": "Huaxin Microelectronics Co., Ltd.",
        "name_alias": "华芯",
        "country": "中国",
        "region": "上海",
        "website": "https://example.com/huaxin",
        "description": "专注于 CPU/GPU/SoC 等核心计算与控制芯片的设计与销售, 服务 PC 与服务器整机制造商。",
        "segment_code": "semiconductor_chips",
        "segment_name_cn": "半导体芯片",
        "segment_name_en": "Semiconductor Chips",
        "chain_position": "upstream",
        "role": "芯片设计商",
        "typical_products": json.dumps(["CPU", "GPU", "SoC", "芯片组"], ensure_ascii=False),
        "confidence_level": "manual",
        "source_name": "enterprise_chain_seed",
    },
    {
        "id": 9002,
        "name": "创捷主板模组科技有限公司",
        "name_en": "Chuangjie Mainboard & Module Tech Co., Ltd.",
        "name_alias": "创捷",
        "country": "中国",
        "region": "深圳",
        "website": "https://example.com/chuangjie",
        "description": "PCB 制板、SMT 贴片、PCBA 加工与主板/模组设计制造, 向整机制造商交付主板与模组。",
        "segment_code": "pcb_pcba",
        "segment_name_cn": "PCB与PCBA",
        "segment_name_en": "PCB and PCBA",
        "chain_position": "upstream",
        "role": "主板/模组制造商",
        "typical_products": json.dumps(["主板", "PCBA", "HDI板", "SMT贴片"], ensure_ascii=False),
        "confidence_level": "manual",
        "source_name": "enterprise_chain_seed",
    },
    {
        "id": 9003,
        "name": "鼎云整机制造有限公司",
        "name_en": "Dingyun ODM Manufacturing Co., Ltd.",
        "name_alias": "鼎云",
        "country": "中国",
        "region": "苏州",
        "website": "https://example.com/dingyun",
        "description": "ODM 方案设计与 EMS 电子制造, 整机组装、软件烧录、老化测试与包装, 向品牌方交付整机。",
        "segment_code": "odm_ems_manufacturing",
        "segment_name_cn": "ODM/EMS制造组装",
        "segment_name_en": "ODM EMS Manufacturing",
        "chain_position": "midstream",
        "role": "ODM/EMS",
        "typical_products": json.dumps(["ODM设计方案", "EMS代工", "整机组装", "台式机", "笔记本"], ensure_ascii=False),
        "confidence_level": "manual",
        "source_name": "enterprise_chain_seed",
    },
    {
        "id": 9004,
        "name": "远达供应链服务有限公司",
        "name_en": "Yuanda Supply Chain Service Co., Ltd.",
        "name_alias": "远达",
        "country": "中国",
        "region": "上海",
        "website": "https://example.com/yuanda",
        "description": "面向电子制造产业链的物流仓储、干线配送、通关与末端配送服务。",
        "segment_code": "logistics_service",
        "segment_name_cn": "物流与供应链服务",
        "segment_name_en": "Logistics and Supply Chain Service",
        "chain_position": "support",
        "role": "物流服务商",
        "typical_products": json.dumps(["仓储", "干线配送", "通关", "末端配送"], ensure_ascii=False),
        "confidence_level": "manual",
        "source_name": "enterprise_chain_seed",
    },
    {
        "id": 9005,
        "name": "星河数码渠道有限公司",
        "name_en": "Xinghe Digital Channel Co., Ltd.",
        "name_alias": "星河",
        "country": "中国",
        "region": "北京",
        "website": "https://example.com/xinghe",
        "description": "电子整机产品的渠道分销与零售, 连接整机制造商与终端客户, 提供 BOM 配单与现货贸易。",
        "segment_code": "sourcing_distribution",
        "segment_name_cn": "采购寻源与分销",
        "segment_name_en": "Sourcing and Distribution",
        "chain_position": "downstream",
        "role": "渠道分销商",
        "typical_products": json.dumps(["台式机", "笔记本", "授权分销", "现货贸易"], ensure_ascii=False),
        "confidence_level": "manual",
        "source_name": "enterprise_chain_seed",
    },
    {
        "id": 9006,
        "name": "毅诚被动元件有限公司",
        "name_en": "Yicheng Passive Components Co., Ltd.",
        "name_alias": "毅诚",
        "country": "中国",
        "region": "东莞",
        "website": "https://example.com/yicheng",
        "description": "MLCC 电容、贴片电阻、电感等被动元件的研发与制造, 向主板/模组厂与 EMS 供货。",
        "segment_code": "passive_components",
        "segment_name_cn": "被动元件",
        "segment_name_en": "Passive Components",
        "chain_position": "upstream",
        "role": "元器件制造商",
        "typical_products": json.dumps(["MLCC电容", "贴片电阻", "电感", "磁珠"], ensure_ascii=False),
        "confidence_level": "manual",
        "source_name": "enterprise_chain_seed",
    },
]


# ============================================================
# 关系定义
# direction 语义:
#   downstream -> source 向 target 供货 (target 是 source 的下游)
#   upstream   -> source 向 target 采购 (target 是 source 的上游)
#   support    -> target 向 source 提供支撑服务
# 每条货物上下游边存两行 (双向视角), 保证 /upstream /downstream 各自可查。
# ============================================================
RELATIONSHIPS = [
    # 毅诚(9006) -> 创捷(9002): 被动元件供货
    {"source": 9006, "target": 9002, "type": "supply", "direction": "downstream",
     "product_scope": ["MLCC电容", "贴片电阻", "电感"], "business_scope": ["批量供货", "样品申请"]},
    {"source": 9002, "target": 9006, "type": "supply", "direction": "upstream",
     "product_scope": ["MLCC电容", "贴片电阻", "电感"], "business_scope": ["批量供货", "样品申请"]},
    # 华芯(9001) -> 创捷(9002): 芯片供货
    {"source": 9001, "target": 9002, "type": "supply", "direction": "downstream",
     "product_scope": ["CPU", "SoC", "芯片组"], "business_scope": ["批量供货", "技术支持"]},
    {"source": 9002, "target": 9001, "type": "supply", "direction": "upstream",
     "product_scope": ["CPU", "SoC", "芯片组"], "business_scope": ["批量供货", "技术支持"]},
    # 创捷(9002) -> 鼎云(9003): 主板/PCBA 供货
    {"source": 9002, "target": 9003, "type": "supply", "direction": "downstream",
     "product_scope": ["主板", "PCBA", "模组"], "business_scope": ["批量供货", "PCBA代工"]},
    {"source": 9003, "target": 9002, "type": "supply", "direction": "upstream",
     "product_scope": ["主板", "PCBA", "模组"], "business_scope": ["批量供货", "PCBA代工"]},
    # 鼎云(9003) -> 星河(9005): 整机渠道
    {"source": 9003, "target": 9005, "type": "channel", "direction": "downstream",
     "product_scope": ["台式机", "笔记本"], "business_scope": ["整机组装", "渠道供货"]},
    {"source": 9005, "target": 9003, "type": "channel", "direction": "upstream",
     "product_scope": ["台式机", "笔记本"], "business_scope": ["整机组装", "渠道供货"]},
    # 远达(9004) 支撑 创捷/鼎云/星河 (target=9004, direction=support)
    # 制造/渠道方视角: 远达是我的支撑(物流)伙伴。
    {"source": 9002, "target": 9004, "type": "service", "direction": "support",
     "product_scope": ["仓储", "配送"], "business_scope": ["物流服务"]},
    {"source": 9003, "target": 9004, "type": "service", "direction": "support",
     "product_scope": ["仓储", "配送", "通关"], "business_scope": ["物流服务"]},
    {"source": 9005, "target": 9004, "type": "service", "direction": "support",
     "product_scope": ["仓储", "末端配送"], "business_scope": ["物流服务"]},
    # 远达(9004) 视角反向边: 创捷/鼎云/星河 是远达的下游客户 (远达向其提供物流服务)。
    # 使远达登录后驾驶舱 downstream_summary 非空, generate_orders 能联动客户。
    {"source": 9004, "target": 9002, "type": "service", "direction": "downstream",
     "product_scope": ["仓储", "配送"], "business_scope": ["物流服务"]},
    {"source": 9004, "target": 9003, "type": "service", "direction": "downstream",
     "product_scope": ["仓储", "配送", "通关"], "business_scope": ["物流服务"]},
    {"source": 9004, "target": 9005, "type": "service", "direction": "downstream",
     "product_scope": ["仓储", "末端配送"], "business_scope": ["物流服务"]},
]


# ============================================================
# 知识内容生成 (基于 segment 边界, 确定性, 无需 LLM)
# ============================================================
def _knowledge_for(cdata: dict) -> list[dict]:
    """根据企业 segment 生成少量手工艺知识 chunks (中文)。"""
    from kb.boundary import _FALLBACK, _SEGMENT_BOUNDARIES

    cname = cdata["name"]
    seg = cdata["segment_code"]
    desc = cdata["description"]
    b = _SEGMENT_BOUNDARIES.get(seg, _FALLBACK)
    industry = b.get("industry_cn", "电子元器件")
    primary = b.get("primary_business_cn", "")
    products = b.get("product_categories", [])
    scope = b.get("allowed_business_scope_cn", [])
    upstream_role = b.get("upstream_role", "")
    downstream_role = b.get("downstream_role", "")

    chunks = [
        {
            "manual_type": "product", "language": "zh",
            "chunk_type": "product_overview",
            "section": "公司概述",
            "text": f"{cname} 是一家{industry}企业。{desc or primary}",
        },
        {
            "manual_type": "business", "language": "zh",
            "chunk_type": "business_overview",
            "section": "业务概述",
            "business_type": scope[0] if scope else "产品销售",
            "text": (
                f"{cname} 可提供的业务范围: {', '.join(scope[:6])}。"
                f"上游角色: {upstream_role}。下游角色: {downstream_role}。"
            ),
        },
    ]
    if products:
        chunks.append({
            "manual_type": "product", "language": "zh",
            "chunk_type": "product_specification",
            "section": "产品规格",
            "product_model": products[0],
            "text": (
                f"{cname} 代表性产品类别: {', '.join(products[:5])}。"
                f"主打 {products[0]} 产品线, 面向电脑制造产业链上下游客户。"
                f"价格类型: 参考报价 (demo), 具体价格以询价单 RFQ 为准。"
            ),
        })
    return chunks


# ============================================================
# Upsert: 公司 / 关系
# ============================================================
def upsert_companies() -> None:
    with session_scope() as s:
        for cdata in COMPANIES:
            existing = s.get(CompanyCache, cdata["id"])
            if existing:
                for k, v in cdata.items():
                    setattr(existing, k, v)
                existing.updated_at = datetime.utcnow()
            else:
                s.add(CompanyCache(**cdata))
        logger.info("企业种子 upsert 完成: %d 家", len(COMPANIES))


def upsert_relationships() -> None:
    with session_scope() as s:
        for rdata in RELATIONSHIPS:
            existing = (
                s.query(CompanyRelationship)
                .filter_by(
                    source_company_id=rdata["source"],
                    target_company_id=rdata["target"],
                    direction=rdata["direction"],
                )
                .first()
            )
            payload = {
                "source_company_id": rdata["source"],
                "target_company_id": rdata["target"],
                "relationship_type": rdata["type"],
                "direction": rdata["direction"],
                "product_scope": json.dumps(rdata["product_scope"], ensure_ascii=False),
                "business_scope": json.dumps(rdata["business_scope"], ensure_ascii=False),
                "confidence_level": "manual",
                "status": "active",
            }
            if existing:
                for k, v in payload.items():
                    setattr(existing, k, v)
                existing.updated_at = datetime.utcnow()
            else:
                s.add(CompanyRelationship(**payload))
        logger.info("关系种子 upsert 完成: %d 条", len(RELATIONSHIPS))


# ============================================================
# 知识种子: manual + chunks + 向量 (Local/Milvus 自适应)
# ============================================================
def seed_knowledge() -> None:
    from kb.embedder import embed_text
    from kb.vectorstore import get_vector_store

    store = get_vector_store()
    store.ensure_collection()

    for cdata in COMPANIES:
        cid = cdata["id"]
        cname = cdata["name"]
        chunks_data = _knowledge_for(cdata)

        for mt in ("product", "business"):
            cchunks = [c for c in chunks_data if c["manual_type"] == mt]
            if not cchunks:
                continue
            lang = "zh"
            md = f"# {cname} {mt} 知识手册\n\n" + "\n\n".join(c["text"] for c in cchunks)
            content_hash = hashlib.sha256(md.encode("utf-8")).hexdigest()

            pending: list[tuple[str, str, dict]] = []
            with session_scope() as s:
                # 清理同 company/type/lang 旧 manual + chunks (幂等重跑)
                s.query(KnowledgeChunk).filter_by(
                    company_id=cid, manual_type=mt, language=lang
                ).delete(synchronize_session=False)
                s.query(KnowledgeManual).filter_by(
                    company_id=cid, manual_type=mt, language=lang
                ).delete(synchronize_session=False)

                manual = KnowledgeManual(
                    company_id=cid, manual_type=mt, language=lang,
                    title=f"{cname} {mt} 手册", content=md, version=1,
                    content_hash=content_hash, source_hash=content_hash,
                    active_version=True, generation_status="completed",
                    source_type="ai_generated_demo", source_url=cdata.get("website"),
                    source_title="enterprise_chain_seed",
                    generated_by_ai=True, confidence=0.7,
                )
                s.add(manual)
                s.flush()
                manual_id = manual.id

                for c in cchunks:
                    ch_hash = hashlib.sha256(c["text"].encode("utf-8")).hexdigest()
                    uid = f"c{cid}-{mt}-{lang}-{ch_hash[:16]}"
                    s.add(KnowledgeChunk(
                        chunk_uid=uid, company_id=cid, manual_id=manual_id,
                        manual_type=mt, language=lang, chunk_type=c["chunk_type"],
                        section=c.get("section"), product_model=c.get("product_model"),
                        business_type=c.get("business_type"),
                        text=c["text"], content_hash=ch_hash,
                        source_type="ai_generated_demo", source_url=cdata.get("website"),
                        generated_by_ai=True, confidence=0.7, version=1,
                        active=True, vector_synced=False,
                    ))
                    pending.append((uid, c["text"], {
                        "company_id": cid, "language": lang, "manual_type": mt,
                        "chunk_type": c["chunk_type"],
                        "product_model": c.get("product_model"),
                        "business_type": c.get("business_type"),
                        "manual_id": manual_id, "text": c["text"],
                        "source_type": "ai_generated_demo",
                    }))

            # 向量写入 (DB 事务已提交, 独立连接)
            synced: list[str] = []
            for uid, text, meta in pending:
                try:
                    emb = embed_text(text)
                    store.upsert(uid, emb, meta)
                    synced.append(uid)
                except Exception as e:
                    logger.warning("向量写入失败 %s: %s", uid, str(e)[:120])
            if synced:
                with session_scope() as s:
                    s.query(KnowledgeChunk).filter(
                        KnowledgeChunk.chunk_uid.in_(synced)
                    ).update(
                        {"vector_synced": True, "vector_backend": store.backend},
                        synchronize_session=False,
                    )

        # 更新公司知识状态
        with session_scope() as s:
            c = s.get(CompanyCache, cid)
            if c:
                c.knowledge_status = "ready"
                c.last_generated_at = datetime.utcnow()

        logger.info("种子知识: %s (%d chunks, backend=%s)", cname, len(chunks_data), store.backend)


def main() -> None:
    init_db()
    upsert_companies()
    upsert_relationships()
    try:
        seed_knowledge()
    except Exception as e:
        logger.warning("知识种子失败 (允许, partner-chat 仍可调用): %s", str(e)[:200])
    logger.info("企业产业链种子完成")


if __name__ == "__main__":
    main()
