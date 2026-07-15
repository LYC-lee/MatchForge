"""
Neo4j 图查询工具
替代料交叉引用图查询
"""

from __future__ import annotations

from neo4j import GraphDatabase

from ai.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


def get_driver():
    """获取 Neo4j 驱动。"""
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def query_direct_equivalents(part_number: str, min_confidence: float = 0.7):
    """查询直接替代关系 (1跳)。

    MATCH (a:Part)-[:EQUIVALENT_TO]-(b:Part)
    WHERE a.part_number = $pn AND r.confidence >= $min_conf
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


def query_transitive_equivalents(part_number: str, min_confidence: float = 0.7):
    """查询传递替代关系 (2跳)。

    MATCH (a:Part)-[:EQUIVALENT_TO]-(mid)-[:EQUIVALENT_TO]-(b:Part)
    WHERE a.part_number = $pn AND a <> b
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


def query_cross_refs(part_number: str):
    """查询交叉引用关系。

    MATCH (a:Part)-[:CROSS_REF]-(b:Part)
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


def query_all_alternatives(part_number: str) -> list[dict]:
    """查询所有替代关系 — 合并直接+传递+交叉引用。

    这是 Agent 直接调用的主入口，内部依次尝试三种查询方式。
    """
    results = []
    try:
        results.extend(query_direct_equivalents(part_number))
    except Exception:
        pass
    try:
        results.extend(query_transitive_equivalents(part_number))
    except Exception:
        pass
    try:
        results.extend(query_cross_refs(part_number))
    except Exception:
        pass
    return results