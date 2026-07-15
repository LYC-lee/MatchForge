"""
MySQL 查询工具
字典查询 / 供应商查询 / 产品查询

工具函数使用 @tool 装饰器，兼容 LLM tool-calling 和直接调用两种方式。
"""

from __future__ import annotations

from sqlalchemy import create_engine, text
from langchain_core.tools import tool

from ai.config import MYSQL_URL


def get_engine():
    """获取 SQLAlchemy 引擎。"""
    return create_engine(MYSQL_URL, pool_pre_ping=True)


@tool
def lookup_std_code(
    category: str = "",
    package: str = "",
    capacitance: str = "",
    temp_coeff: str = "",
    rated_voltage: str = "",
) -> str:
    """查询标准字典 — 匹配 material_dictionary 中的 std_code。

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


# 保留原始函数（兼容直接 dict 参数调用）
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
        return row._mapping if row else None


@tool
def filter_suppliers(
    category: str = "",
    brands: str = "",
    location: str = "",
) -> str:
    """查询符合条件的供应商列表。

    根据经营品类、品牌覆盖、地区过滤已审核通过的供应商。

    Args:
        category: 经营品类，如 MLCC、电阻
        brands: 品牌名称，多个以逗号分隔，如 "Murata,YAGEO"
        location: 地区过滤，如 "深圳"、"华东"
    """
    brand_list = [b.strip() for b in brands.split(",") if b.strip()] if brands else []

    conditions = ["s.status = 'approved'"]
    params: dict = {"category": category}

    if brand_list:
        brand_conditions = " OR ".join(
            [f"JSON_CONTAINS(s.brand_coverage, JSON_QUOTE(:brand_{i}))" for i in range(len(brand_list))]
        )
        for i, b in enumerate(brand_list):
            params[f"brand_{i}"] = b
        conditions.append(f"({brand_conditions})")
    if location:
        conditions.append("s.location = :location")
        params["location"] = location

    where = " AND ".join(conditions)
    query = text(f"""
        SELECT s.id, s.name, s.category, s.brand_coverage AS brands,
               s.location, s.moq, s.lead_time_weeks,
               s.data_source, s.updated_at
        FROM suppliers s
        WHERE s.category = :category AND {where}
        ORDER BY s.rating DESC
        LIMIT 20
    """)

    with get_engine().connect() as conn:
        result = conn.execute(query, params)
        rows = [dict(row._mapping) for row in result]
        if not rows:
            return "未查询到符合条件的供应商"
        return str(rows)


# 保留原始函数（兼容旧代码）
def filter_suppliers_raw(
    category: str,
    brands: list[str] | None = None,
    location: str | None = None,
) -> list[dict]:
    """查询符合条件的供应商（list 参数版本，兼容旧代码）。"""
    conditions = ["s.status = 'approved'"]
    params: dict = {"category": category}

    if brands:
        brand_conditions = " OR ".join(
            [f"JSON_CONTAINS(s.brand_coverage, JSON_QUOTE(:brand_{i}))" for i in range(len(brands))]
        )
        for i, b in enumerate(brands):
            params[f"brand_{i}"] = b
        conditions.append(f"({brand_conditions})")
    if location:
        conditions.append("s.location = :location")
        params["location"] = location

    where = " AND ".join(conditions)
    query = text(f"""
        SELECT s.id, s.name, s.category, s.brand_coverage AS brands,
               s.location, s.moq, s.lead_time_weeks,
               s.data_source, s.updated_at
        FROM suppliers s
        WHERE s.category = :category AND {where}
        ORDER BY s.rating DESC
        LIMIT 20
    """)

    with get_engine().connect() as conn:
        result = conn.execute(query, params)
        return [row._mapping for row in result]