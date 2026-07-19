"""
MySQL 查询工具 -- 按真实 schema 查询。

事实源:
  - suppliers 表: 供应商主体 (id, name, location, rating, status, ...)
  - supplier_capabilities 表: 品类/品牌/MOQ/交期 (supplier_id, category_name, brand_names, moq, lead_time_days)
  - material_dictionary 表: 标准物料字典 (std_code, category, params, standard)

旧代码的错误:
  - 查询 suppliers.category / suppliers.brand_coverage / suppliers.moq / suppliers.lead_time_weeks / suppliers.data_source
    这些列在真实 suppliers 表中不存在, 实际存储在 supplier_capabilities 表中。
  - 本修复通过 JOIN supplier_capabilities 获取品类/品牌/MOQ 等信息。

工具函数使用 @tool 装饰器，兼容 LLM tool-calling 和直接调用两种方式。
"""

from __future__ import annotations

import logging
from sqlalchemy import create_engine, text
from langchain_core.tools import tool

from ai.config import MYSQL_URL

logger = logging.getLogger(__name__)


def get_engine():
    """获取 SQLAlchemy 引擎。"""
    return create_engine(MYSQL_URL, pool_pre_ping=True, future=True)


# ============================================================
# 标准字典查询
# ============================================================
@tool
def lookup_std_code(
    category: str = "",
    package: str = "",
    capacitance: str = "",
    temp_coeff: str = "",
    rated_voltage: str = "",
) -> str:
    """查询标准字典 - 匹配 material_dictionary 中的 std_code。

    根据元器件的品类、封装、容值、温度系数、额定电压，
    在标准字典中查找匹配的标准编码。

    Args:
        category: 元器件品类，如 MLCC、钽电容
        package: 封装尺寸，如 0805、0603
        capacitance: 标称容值，如 10uF、100nF
        temp_coeff: 温度系数，如 X7R、C0G
        rated_voltage: 额定电压，如 50V、25V
    """
    query = text("""
        SELECT std_code, category, params, standard
        FROM material_dictionary
        WHERE (:category = '' OR category = :category)
          AND (:package = '' OR JSON_EXTRACT(params, '$.package') = :package)
          AND (:capacitance = '' OR JSON_EXTRACT(params, '$.capacitance') = :capacitance)
          AND (:temp_coeff = '' OR JSON_EXTRACT(params, '$.temp_coeff') = :temp_coeff)
          AND (:rated_voltage = '' OR JSON_EXTRACT(params, '$.rated_voltage') = :rated_voltage)
        LIMIT 1
    """)
    with get_engine().connect() as conn:
        result = conn.execute(query, {
            "category": category,
            "package": package,
            "capacitance": capacitance,
            "temp_coeff": temp_coeff,
            "rated_voltage": str(rated_voltage),
        })
        row = result.fetchone()
        if row:
            data = dict(row._mapping)
            return str(data)
        return "未找到匹配的标准编码"


def lookup_std_code_raw(spec: dict) -> dict | None:
    """查询标准字典（dict 参数版本，兼容旧代码）。"""
    query = text("""
        SELECT std_code, category, params, standard
        FROM material_dictionary
        WHERE category = :category
          AND JSON_EXTRACT(params, '$.package') = :package
          AND JSON_EXTRACT(params, '$.capacitance') = :capacitance
          AND JSON_EXTRACT(params, '$.temp_coeff') = :temp_coeff
          AND JSON_EXTRACT(params, '$.rated_voltage') = :rated_voltage
        LIMIT 1
    """)
    with get_engine().connect() as conn:
        result = conn.execute(query, {
            "category": spec.get("category", ""),
            "package": spec.get("package", ""),
            "capacitance": spec.get("capacitance", ""),
            "temp_coeff": spec.get("temp_coeff", ""),
            "rated_voltage": str(spec.get("rated_voltage", "")),
        })
        row = result.fetchone()
        return dict(row._mapping) if row else None


# ============================================================
# 供应商查询 -- 按 JOIN supplier_capabilities 真实 schema
# ============================================================
@tool
def filter_suppliers(
    category: str = "",
    brands: str = "",
    location: str = "",
) -> str:
    """查询符合条件的供应商列表。

    根据经营品类、品牌覆盖、地区过滤已审核通过的供应商。
    品类/品牌/MOQ 等信息存储在 supplier_capabilities 表中，通过 JOIN 查询。

    Args:
        category: 经营品类，如 MLCC、电阻
        brands: 品牌名称，多个以逗号分隔，如 "Murata,YAGEO"
        location: 地区过滤，如 "深圳"、("华东")
    """
    results = filter_suppliers_raw(category, brands.split(",") if brands else None, location)
    if not results:
        return "未查询到符合条件的供应商"
    return str(results)


def filter_suppliers_raw(
    category: str,
    brands: list[str] | None = None,
    location: str | None = None,
) -> list[dict]:
    """查询符合条件的供应商（list 参数版本，兼容旧代码）。

    真实 schema:
      - suppliers 表: id, name, location, rating, status, contact_phone, contact_email
      - supplier_capabilities 表: supplier_id, category_name, brand_names, moq, lead_time_days, region

    通过 LEFT JOIN supplier_capabilities 获取品类/品牌/MOQ 等信息。
    一个供应商可能有多个能力记录 (多个品类)，按 category 过滤时取匹配行。
    """
    conditions = ["s.status = 'approved'"]
    params: dict = {"category": f"%{category}%" if category else ""}

    # 品类过滤: supplier_capabilities.category_name LIKE %category%
    if category:
        conditions.append("(sc.category_name LIKE :category OR sc.category_name IS NULL)")

    # 品牌过滤: supplier_capabilities.brand_names 中包含指定品牌
    if brands:
        brand_conditions = []
        for i, b in enumerate(brands):
            b = b.strip()
            if not b:
                continue
            param_key = f"brand_{i}"
            params[param_key] = f"%{b}%"
            brand_conditions.append(f"sc.brand_names LIKE :{param_key}")
        if brand_conditions:
            conditions.append(f"({' OR '.join(brand_conditions)})")

    # 地区过滤: suppliers.location LIKE %location%
    if location:
        params["location"] = f"%{location}%"
        conditions.append("s.location LIKE :location")

    where = " AND ".join(conditions)

    query = text(f"""
        SELECT s.id, s.name, s.location, s.rating, s.status,
               sc.category_name, sc.brand_names, sc.moq, sc.lead_time_days,
               sc.region, sc.audit_status,
               s.contact_phone, s.contact_email
        FROM suppliers s
        LEFT JOIN supplier_capabilities sc ON sc.supplier_id = s.id
        WHERE {where}
        ORDER BY s.rating DESC
        LIMIT 20
    """)

    try:
        with get_engine().connect() as conn:
            result = conn.execute(query, params)
            return [dict(row._mapping) for row in result]
    except Exception as e:
        logger.error("filter_suppliers_raw 查询失败: %s", e)
        # 降级: 不 JOIN, 只查 suppliers 主体表
        logger.warning("降级查询: 仅查 suppliers 主体表")
        fallback_conditions = ["s.status = 'approved'"]
        if location:
            fallback_conditions.append("s.location LIKE :location")
        fallback_where = " AND ".join(fallback_conditions)
        fallback_query = text(f"""
            SELECT s.id, s.name, s.location, s.rating, s.status,
                   NULL AS category_name, NULL AS brand_names,
                   NULL AS moq, NULL AS lead_time_days, NULL AS region,
                   NULL AS audit_status, s.contact_phone, s.contact_email
            FROM suppliers s
            WHERE {fallback_where}
            ORDER BY s.rating DESC
            LIMIT 20
        """)
        with get_engine().connect() as conn:
            result = conn.execute(fallback_query, params)
            return [dict(row._mapping) for row in result]
