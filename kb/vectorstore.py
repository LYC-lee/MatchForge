"""
向量库抽象层 (VectorStore)。

- MilvusVectorStore: 复用现有 pymilvus + ai/config.py 配置, 新建 company_knowledge_chunks
  集合 (现有 knowledge_chunks 缺 company_id/language/chunk_type 等过滤字段, 非破坏式新建)。
- LocalVectorStore: numpy 余弦相似度, 向量持久化到 SQLite (当前环境 Milvus 未启动时生效)。

自动选择: KB_VECTOR_STORE=auto 时优先 Milvus, 不可达降级 Local。
Source of Truth 始终是 MySQL/SQLite 知识表; 向量库可被删除后由 rebuild_vector_index 重建。
"""

from __future__ import annotations

import json
import logging
import math
import uuid
from typing import Any

from kb.config import (
    EMBEDDING_DIM,
    KB_RAG_MIN_SCORE,
    KB_RAG_TOP_K,
    MILVUS_COLLECTION_KB,
    MILVUS_HOST,
    MILVUS_PORT,
    active_vector_store,
)
from kb.db import session_scope
from kb.models import KnowledgeChunk

logger = logging.getLogger("kb.vectorstore")


# ============================================================
# 抽象接口
# ============================================================
class VectorStore:
    backend: str = "abstract"

    def ensure_collection(self) -> None: ...
    def upsert(self, chunk_uid: str, embedding: list[float], meta: dict) -> None: ...
    def delete_by_company(self, company_id: int) -> None: ...
    def search(
        self,
        embedding: list[float],
        company_id: int | None,
        language: str | None,
        manual_type: str | None,
        top_k: int = KB_RAG_TOP_K,
        extra_filter: dict | None = None,
    ) -> list[dict]: ...
    def count(self) -> int: ...
    def drop(self) -> None: ...


# ============================================================
# Local (numpy + SQLite) 向量库
# ============================================================
class LocalVectorStore(VectorStore):
    backend = "local"

    # 序列化所有写操作, 避免 SQLite 并发写锁
    _write_lock = __import__("threading").Lock()

    def __init__(self):
        from kb.db import Base, get_engine
        from sqlalchemy import Column, Float, String, Table, Text

        # 动态注册向量表 (不污染 models.py 的业务表语义)
        if "kb_vectors" not in Base.metadata.tables:
            Table(
                "kb_vectors",
                Base.metadata,
                Column("chunk_uid", String(80), primary_key=True),
                Column("company_id", String(40), index=True),
                Column("embedding", Text, nullable=False, comment="JSON float list"),
                Column("meta", Text, nullable=False, comment="JSON metadata"),
            )
        Base.metadata.create_all(get_engine())

    def _conn(self):
        from kb.db import get_engine

        return get_engine().connect()

    def upsert(self, chunk_uid: str, embedding: list[float], meta: dict) -> None:
        from sqlalchemy import text as sa_text

        with self._write_lock, self._conn() as conn:
            conn.execute(
                sa_text(
                    "DELETE FROM kb_vectors WHERE chunk_uid=:uid"
                ),
                {"uid": chunk_uid},
            )
            conn.execute(
                sa_text(
                    "INSERT INTO kb_vectors (chunk_uid, company_id, embedding, meta) "
                    "VALUES (:uid, :cid, :emb, :meta)"
                ),
                {
                    "uid": chunk_uid,
                    "cid": str(meta.get("company_id")),
                    "emb": json.dumps(list(embedding)),
                    "meta": json.dumps(meta, ensure_ascii=False),
                },
            )
            conn.commit()

    def delete_by_company(self, company_id: int) -> None:
        from sqlalchemy import text as sa_text

        with self._write_lock, self._conn() as conn:
            conn.execute(
                sa_text("DELETE FROM kb_vectors WHERE company_id=:cid"),
                {"cid": str(company_id)},
            )
            conn.commit()

    def _load_all(self, company_id: int | None, language: str | None, manual_type: str | None) -> list[tuple[str, list[float], dict]]:
        from sqlalchemy import text as sa_text

        sql = "SELECT chunk_uid, embedding, meta FROM kb_vectors WHERE 1=1"
        params: dict = {}
        if company_id is not None:
            sql += " AND company_id=:cid"
            params["cid"] = str(company_id)
        rows: list[tuple[str, list[float], dict]] = []
        with self._conn() as conn:
            for r in conn.execute(sa_text(sql), params):
                emb = json.loads(r[1])
                meta = json.loads(r[2])
                if language and meta.get("language") != language:
                    continue
                if manual_type and meta.get("manual_type") != manual_type:
                    continue
                rows.append((r[0], emb, meta))
        return rows

    def search(
        self,
        embedding: list[float],
        company_id: int | None,
        language: str | None,
        manual_type: str | None,
        top_k: int = KB_RAG_TOP_K,
        extra_filter: dict | None = None,
    ) -> list[dict]:
        rows = self._load_all(company_id, language, manual_type)
        if not rows:
            return []
        q = embedding
        qn = math.sqrt(sum(x * x for x in q)) or 1.0
        scored = []
        for uid, emb, meta in rows:
            # extra_filter (product_model / business_type / company_ids)
            if extra_filter:
                if extra_filter.get("product_model") and meta.get("product_model") != extra_filter["product_model"]:
                    continue
                if extra_filter.get("business_type") and meta.get("business_type") != extra_filter["business_type"]:
                    continue
            n = math.sqrt(sum(x * x for x in emb)) or 1.0
            dot = sum(a * b for a, b in zip(q, emb))
            score = dot / (qn * n)
            if score < KB_RAG_MIN_SCORE:
                continue
            scored.append((score, uid, meta))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"chunk_uid": uid, "score": float(s), "meta": m}
            for s, uid, m in scored[:top_k]
        ]

    def count(self) -> int:
        from sqlalchemy import text as sa_text

        with self._conn() as conn:
            r = conn.execute(sa_text("SELECT COUNT(*) FROM kb_vectors")).scalar()
            return int(r or 0)

    def drop(self) -> None:
        from sqlalchemy import text as sa_text

        with self._conn() as conn:
            conn.execute(sa_text("DELETE FROM kb_vectors"))
            conn.commit()


# ============================================================
# Milvus 向量库 (真实, 需 pymilvus + 运行中的 Milvus)
# ============================================================
class MilvusVectorStore(VectorStore):
    backend = "milvus"

    def __init__(self):
        from pymilvus import connections

        if not connections.has_connection("default"):
            connections.connect(alias="default", host=MILVUS_HOST, port=str(MILVUS_PORT))

    def _collection(self):
        from pymilvus import Collection

        return Collection(MILVUS_COLLECTION_KB)

    def ensure_collection(self) -> None:
        from pymilvus import (
            Collection,
            CollectionSchema,
            DataType,
            FieldSchema,
            utility,
        )

        if utility.has_collection(MILVUS_COLLECTION_KB):
            col = self._collection()
            col.load()
            return
        fields = [
            FieldSchema("chunk_uid", DataType.VARCHAR, max_length=80, is_primary=True),
            FieldSchema("embedding", DataType.FLOAT_VECTOR, dim=int(EMBEDDING_DIM)),
            FieldSchema("company_id", DataType.INT64),
            FieldSchema("language", DataType.VARCHAR, max_length=8),
            FieldSchema("manual_type", DataType.VARCHAR, max_length=20),
            FieldSchema("chunk_type", DataType.VARCHAR, max_length=40),
            FieldSchema("product_model", DataType.VARCHAR, max_length=200),
            FieldSchema("business_type", DataType.VARCHAR, max_length=80),
            FieldSchema("manual_id", DataType.INT64),
            FieldSchema("product_id", DataType.INT64),
            FieldSchema("source_type", DataType.VARCHAR, max_length=30),
            FieldSchema("text", DataType.VARCHAR, max_length=65535),
        ]
        schema = CollectionSchema(fields, description="公司级知识库切片 (company-scoped RAG)", enable_dynamic_field=False)
        col = Collection(MILVUS_COLLECTION_KB, schema=schema)
        col.create_index(
            "embedding",
            {"index_type": "IVF_FLAT", "metric_type": "COSINE", "params": {"nlist": 128}},
        )
        col.load()

    def upsert(self, chunk_uid: str, embedding: list[float], meta: dict) -> None:
        col = self._collection()
        col.upsert(
            [
                [chunk_uid],
                [list(embedding)],
                [int(meta.get("company_id", 0))],
                [meta.get("language", "zh")],
                [meta.get("manual_type", "product")],
                [meta.get("chunk_type", "")],
                [meta.get("product_model") or ""],
                [meta.get("business_type") or ""],
                [int(meta.get("manual_id", 0))],
                [int(meta.get("product_id") or 0)],
                [meta.get("source_type", "ai_generated_demo")],
                [meta.get("text", "")[:65535]],
            ]
        )
        col.flush()

    def delete_by_company(self, company_id: int) -> None:
        col = self._collection()
        col.delete(f"company_id == {int(company_id)}")
        col.flush()

    def search(
        self,
        embedding: list[float],
        company_id: int | None,
        language: str | None,
        manual_type: str | None,
        top_k: int = KB_RAG_TOP_K,
        extra_filter: dict | None = None,
    ) -> list[dict]:
        col = self._collection()
        expr_parts: list[str] = []
        if company_id is not None:
            expr_parts.append(f"company_id == {int(company_id)}")
        if language:
            expr_parts.append(f'language == "{language}"')
        if manual_type:
            expr_parts.append(f'manual_type == "{manual_type}"')
        expr = " and ".join(expr_parts) if expr_parts else None
        results = col.search(
            data=[list(embedding)],
            anns_field="embedding",
            param={"metric_type": "COSINE", "params": {"nprobe": 16}},
            limit=top_k,
            expr=expr,
            output_fields=[
                "chunk_uid", "company_id", "language", "manual_type",
                "chunk_type", "product_model", "business_type", "text", "source_type",
            ],
        )
        out = []
        for hit in results[0]:
            e = hit.entity
            out.append({
                "chunk_uid": e.get("chunk_uid"),
                "score": float(hit.score),
                "meta": {
                    "company_id": e.get("company_id"),
                    "language": e.get("language"),
                    "manual_type": e.get("manual_type"),
                    "chunk_type": e.get("chunk_type"),
                    "product_model": e.get("product_model"),
                    "business_type": e.get("business_type"),
                    "text": e.get("text"),
                    "source_type": e.get("source_type"),
                },
            })
        return out

    def count(self) -> int:
        col = self._collection()
        col.flush()
        return int(col.num_entities)

    def drop(self) -> None:
        from pymilvus import utility

        if utility.has_collection(MILVUS_COLLECTION_KB):
            utility.drop_collection(MILVUS_COLLECTION_KB)


# ============================================================
# 工厂
# ============================================================
_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is not None:
        return _store
    backend = active_vector_store()
    if backend == "milvus":
        try:
            _store = MilvusVectorStore()
            _store.ensure_collection()
            logger.info("向量库后端: Milvus (%s)", MILVUS_COLLECTION_KB)
            return _store
        except Exception as e:
            logger.warning("Milvus 初始化失败, 降级 Local: %s", str(e)[:160])
    _store = LocalVectorStore()
    logger.info("向量库后端: Local (numpy+SQLite)")
    return _store


def reset_vector_store():
    global _store
    _store = None
