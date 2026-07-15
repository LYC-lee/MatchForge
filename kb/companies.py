"""
公司源数据采集 (Company Source Collector)。

资料来源优先级 (遵循任务要求):
  1. MySQL pc_industry.companies + company_segments + industry_segments  (优先级1)
  2. 项目 CSV 种子文件 database/04_seed_data/                              (优先级2, 当前生效)
  3. 公开网页                                                              (优先级3, 当前环境无网络)
  4. AI 业务边界内补全                                                     (优先级4, 见 generator.py)

MySQL 不可达时自动降级到 CSV, 不中断任务。
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
from pathlib import Path
from typing import Iterator

from sqlalchemy import text

from kb.config import COMPANY_CSV_DIR, COMPANY_MYSQL_URL
from kb.models import CompanyCache

logger = logging.getLogger("kb.companies")

_BOM = "﻿"


def _clean(v: str | None) -> str | None:
    if v is None:
        return None
    s = str(v).strip().lstrip(_BOM)
    return s if s else None


def _hash_company_source(row: dict) -> str:
    """对源数据关键字段哈希, 用于增量更新判断。"""
    key = json.dumps(
        {
            "name": row.get("name"),
            "description": row.get("description"),
            "website": row.get("website"),
            "segment": row.get("segment_code"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


# ============================================================
# 优先级2: CSV 种子文件
# ============================================================
def _read_csv(filename: str) -> list[dict]:
    path = COMPANY_CSV_DIR / filename
    if not path.exists():
        logger.warning("CSV 不存在: %s", path)
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _load_segment_map() -> dict[str, dict]:
    """company_id -> {segment_code, role, is_primary}; segment_code -> segment info."""
    seg_info: dict[str, dict] = {}
    for row in _read_csv("01_industry_segments_seed.csv"):
        code = _clean(row.get("segment_code"))
        if not code:
            continue
        seg_info[code] = {
            "segment_code": code,
            "segment_name_cn": _clean(row.get("segment_name_cn")),
            "segment_name_en": _clean(row.get("segment_name_en")),
            "chain_position": _clean(row.get("chain_position")),
            "description": _clean(row.get("description")),
            "typical_products": _clean(row.get("typical_products")),
            "typical_companies": _clean(row.get("typical_companies")),
        }

    company_seg: dict[str, dict] = {}
    for row in _read_csv("09_company_segments_seed.csv"):
        cid = _clean(row.get("company_id"))
        code = _clean(row.get("segment_code"))
        if cid and code:
            company_seg[cid] = {
                "segment_code": code,
                "role": _clean(row.get("role")) or "制造商",
                "is_primary": _clean(row.get("is_primary")) == "1",
            }
    return {"by_company": company_seg, "seg_info": seg_info}


def _iter_csv_companies() -> Iterator[dict]:
    seg = _load_segment_map()
    for row in _read_csv("02_companies_seed.csv"):
        cid = _clean(row.get("id"))
        if not cid:
            continue
        cs = seg["by_company"].get(cid, {})
        code = cs.get("segment_code")
        si = seg["seg_info"].get(code, {})
        yield {
            "id": int(cid),
            "name": _clean(row.get("name")) or "",
            "name_en": _clean(row.get("name_en")),
            "name_alias": _clean(row.get("name_alias")),
            "country": _clean(row.get("country")),
            "region": _clean(row.get("region")),
            "website": _clean(row.get("website")),
            "description": _clean(row.get("description")),
            "confidence_level": _clean(row.get("confidence_level")) or "official",
            "source_name": _clean(row.get("source_name")) or "project_file",
            "source_url": _clean(row.get("source_url")),
            "segment_code": code,
            "segment_name_cn": si.get("segment_name_cn"),
            "segment_name_en": si.get("segment_name_en"),
            "chain_position": si.get("chain_position"),
            "role": cs.get("role"),
            "typical_products": si.get("typical_products"),
            "segment_description": si.get("description"),
            "_source_priority": "project_file",
        }


# ============================================================
# 优先级1: MySQL pc_industry
# ============================================================
def _mysql_reachable() -> bool:
    try:
        from sqlalchemy import create_engine

        eng = create_engine(COMPANY_MYSQL_URL, pool_pre_ping=True, future=True)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        eng.dispose()
        return True
    except Exception as e:
        logger.info("MySQL pc_industry 不可达, 降级到 CSV: %s", str(e)[:120])
        return False


def _iter_mysql_companies() -> Iterator[dict]:
    from sqlalchemy import create_engine

    eng = create_engine(COMPANY_MYSQL_URL, pool_pre_ping=True, future=True)
    sql = text(
        """
        SELECT c.id, c.name, c.name_en, c.name_alias, c.country, c.region,
               c.website, c.description, c.confidence_level, c.source_name,
               c.source_url,
               cs.segment_code, cs.role,
               s.segment_name_cn, s.segment_name_en, s.chain_position,
               s.typical_products, s.description AS segment_description
        FROM companies c
        LEFT JOIN company_segments cs ON cs.company_id = c.id AND cs.is_primary = 1
        LEFT JOIN industry_segments s ON s.segment_code = cs.segment_code
        ORDER BY c.id
        """
    )
    with eng.connect() as conn:
        for r in conn.execute(sql):
            d = r._mapping
            yield {
                "id": int(d["id"]),
                "name": d["name"],
                "name_en": d["name_en"],
                "name_alias": d["name_alias"],
                "country": d["country"],
                "region": d["region"],
                "website": d["website"],
                "description": d["description"],
                "confidence_level": d["confidence_level"] or "official",
                "source_name": d["source_name"] or "company_database",
                "source_url": d["source_url"],
                "segment_code": d["segment_code"],
                "segment_name_cn": d["segment_name_cn"],
                "segment_name_en": d["segment_name_en"],
                "chain_position": d["chain_position"],
                "role": d["role"],
                "typical_products": d["typical_products"],
                "segment_description": d["segment_description"],
                "_source_priority": "company_database",
            }
    eng.dispose()


# ============================================================
# 统一入口: 采集并写入 CompanyCache
# ============================================================
def collect_companies(session) -> tuple[list[CompanyCache], str]:
    """采集公司并 upsert 到 kb_companies。返回 (公司列表, 来源标签)。"""
    source = "project_file"
    rows: list[dict] = []
    if _mysql_reachable():
        try:
            rows = list(_iter_mysql_companies())
            if rows:
                source = "company_database"
        except Exception as e:
            logger.warning("MySQL 读取失败, 降级 CSV: %s", str(e)[:120])
            rows = []
    if not rows:
        rows = list(_iter_csv_companies())
        source = "project_file"

    result: list[CompanyCache] = []
    for row in rows:
        src_hash = _hash_company_source(row)
        existing = session.get(CompanyCache, row["id"])
        if existing:
            existing.name = row["name"]
            existing.name_en = row.get("name_en")
            existing.name_alias = row.get("name_alias")
            existing.country = row.get("country")
            existing.region = row.get("region")
            existing.website = row.get("website")
            existing.description = row.get("description")
            existing.segment_code = row.get("segment_code")
            existing.segment_name_cn = row.get("segment_name_cn")
            existing.segment_name_en = row.get("segment_name_en")
            existing.chain_position = row.get("chain_position")
            existing.role = row.get("role")
            existing.typical_products = row.get("typical_products")
            existing.confidence_level = row.get("confidence_level")
            existing.source_name = row.get("source_name")
            existing.source_url = row.get("source_url")
            existing.source_hash = src_hash
            existing.updated_at = __import__("datetime").datetime.utcnow()
            obj = existing
        else:
            obj = CompanyCache(
                id=row["id"],
                name=row["name"],
                name_en=row.get("name_en"),
                name_alias=row.get("name_alias"),
                country=row.get("country"),
                region=row.get("region"),
                website=row.get("website"),
                description=row.get("description"),
                segment_code=row.get("segment_code"),
                segment_name_cn=row.get("segment_name_cn"),
                segment_name_en=row.get("segment_name_en"),
                chain_position=row.get("chain_position"),
                role=row.get("role"),
                typical_products=row.get("typical_products"),
                confidence_level=row.get("confidence_level"),
                source_name=row.get("source_name"),
                source_url=row.get("source_url"),
                source_hash=src_hash,
            )
            session.add(obj)
        result.append(obj)
    session.flush()
    logger.info("采集公司 %d 家, 来源=%s", len(result), source)
    return result, source


def get_companies(session) -> list[CompanyCache]:
    return session.query(CompanyCache).order_by(CompanyCache.id).all()


def get_company(session, company_id: int) -> CompanyCache | None:
    return session.get(CompanyCache, int(company_id))
