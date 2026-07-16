"""
Milvus 向量检索工具
供应商产品向量召回
"""

from __future__ import annotations

from pymilvus import connections, Collection

from ai.config import MILVUS_HOST, MILVUS_PORT, MILVUS_COLLECTION_PRODUCTS


def connect_milvus():
    """连接 Milvus。"""
    connections.connect(
        alias="default",
        host=MILVUS_HOST,
        port=MILVUS_PORT,
    )


def search_products(
    embedding: list[float],
    top_k: int = 20,
    category_filter: str | None = None,
) -> list[dict]:
    """向量检索候选产品。

    Args:
        embedding: 规格向量
        top_k: 返回数量
        category_filter: 品类过滤 (可选)

    Returns:
        [{product_id, score, category, brand, part_number}, ...]
    """
    connect_milvus()
    collection = Collection(MILVUS_COLLECTION_PRODUCTS)
    collection.load()

    search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}

    expr = None
    if category_filter:
        expr = f'category == "{category_filter}"'

    results = collection.search(
        data=[embedding],
        anns_field="embedding",
        param=search_params,
        limit=top_k,
        expr=expr,
        output_fields=["product_id", "category", "brand", "part_number"],
    )

    return [
        {
            "product_id": hit.entity.get("product_id"),
            "score": hit.score,
            "category": hit.entity.get("category"),
            "brand": hit.entity.get("brand"),
            "part_number": hit.entity.get("part_number"),
        }
        for hit in results[0]
    ]