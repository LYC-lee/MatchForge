"""
Neo4j 图查询工具
替代料交叉引用图查询

所有查询函数均以 @tool 装饰，Agent LLM 可自主调用。
"""

from __future__ import annotations

from neo4j import GraphDatabase
from langchain_core.tools import tool

from ai.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


def get_driver():
    """获取 Neo4j 驱动。"""
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


@tool
def query_direct_equivalents(part_number: str, min_confidence: float = 0.7) -> list[dict]:
    """从知识图谱中查询与指定型号有直接等效关系 (1跳) 的替代型号。

    MATCH (a:Part)-[:EQUIVALENT_TO]-(b:Part) — 经人工核验的直接替代关系。

    Args:
        part_number: 元器件型号，如 GRM188R61A106KE69D
        min_confidence: 最低置信度阈值 (0.0-1.0)，默认 0.7
    """
    query = """
    MATCH (a:Part {part_number: $pn})-[r:EQUIVALENT_TO]-(b:Part)
    WHERE r.confidence >= $min_conf
    RETURN b.part_number AS part, b.brand AS brand, b.specs AS specs,
           r.confidence AS confidence, r.source AS source,
           r.verified AS verified
    """
    with get_driver().session() as session:
        result = session.run(query, pn=part_number, min_conf=min_confidence)
        return [record.data() for record in result]


@tool
def query_transitive_equivalents(part_number: str, min_confidence: float = 0.7) -> list[dict]:
    """从知识图谱中查询通过中间型号间接等效 (2跳) 的替代型号。

    MATCH (a:Part)-[:EQUIVALENT_TO]-(mid:Part)-[:EQUIVALENT_TO]-(b:Part) — 传递替代关系。

    Args:
        part_number: 元器件型号，如 GRM188R61A106KE69D
        min_confidence: 最低置信度阈值 (0.0-1.0)，默认 0.7
    """
    query = """
    MATCH (a:Part {part_number: $pn})-[r1:EQUIVALENT_TO]-(mid:Part)-[r2:EQUIVALENT_TO]-(b:Part)
    WHERE r1.confidence >= $min_conf AND r2.confidence >= $min_conf AND a <> b
    RETURN b.part_number AS part, b.brand AS brand, b.specs AS specs,
           (r1.confidence * r2.confidence * 0.9) AS confidence,
           r1.source + ' → ' + r2.source AS source,
           false AS verified
    """
    with get_driver().session() as session:
        result = session.run(query, pn=part_number, min_conf=min_confidence)
        return [record.data() for record in result]


@tool
def query_cross_refs(part_number: str) -> list[dict]:
    """从知识图谱中查询与指定型号有交叉引用关系的替代型号。

    MATCH (a:Part)-[:CROSS_REF]-(b:Part) — 非等效但可参考的替代关系。

    Args:
        part_number: 元器件型号，如 GRM188R61A106KE69D
    """
    query = """
    MATCH (a:Part {part_number: $pn})-[r:CROSS_REF]-(b:Part)
    RETURN b.part_number AS part, b.brand AS brand, b.specs AS specs,
           r.confidence AS confidence, r.source AS source,
           r.verified AS verified
    """
    with get_driver().session() as session:
        result = session.run(query, pn=part_number)
        return [record.data() for record in result]


@tool
def query_all_alternatives(part_number: str) -> list[dict]:
    """查询指定型号的所有替代关系 — 合并直接等效 + 传递等效 + 交叉引用。

    这是替代料查询的主入口，内部依次尝试三种查询方式。
    适合作为替代料推荐 Agent 的首选工具。

    Args:
        part_number: 元器件型号，如 GRM188R61A106KE69D
    """
    results = []
    try:
        results.extend(query_direct_equivalents.invoke({"part_number": part_number}))
    except Exception:
        pass
    try:
        results.extend(query_transitive_equivalents.invoke({"part_number": part_number}))
    except Exception:
        pass
    try:
        results.extend(query_cross_refs.invoke({"part_number": part_number}))
    except Exception:
        pass
    return results