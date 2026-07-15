"""
MySQL 查询工具
字典查询 / 供应商查询 / 产品查询
"""

from sqlalchemy import create_engine, text
from ai.config import MYSQL_URL


def get_engine():
    """获取 SQLAlchemy 引擎"""
    return create_engine(MYSQL_URL, pool_pre_ping=True)


def lookup_std_code(spec: dict) -> dict | None:
    """
    查询标准字典 — 匹配 std_code

    参数: spec = {category, package, capacitance, temp_coeff, rated_voltage}
    返回: {std_code, ...} 或 None
    """
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


def filter_suppliers(
    category: str,
    brands: list[str] | None = None,
    location: str | None = None,
) -> list[dict]:
    """
    查询符合条件的供应商

    参数:
      category: 经营品类
      brands: 品牌覆盖过滤
      location: 地区过滤

    返回: 供应商列表
    """
    conditions = ["s.status = 'approved'"]
    params: dict = {"category": category}

    if brands:
        # JSON 品牌覆盖匹配
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