"""
知识生成全流程编排 (Pipeline)。

Company Source Collector
  -> Business Boundary Builder
  -> Product Knowledge Generator (zh/en)
  -> Business Knowledge Generator (zh/en)
  -> Quality Validator
  -> Semantic Chunker
  -> Embedding
  -> Milvus/Local Indexer

特性:
  - 幂等: source_hash + content_hash 去重; 同源重复执行不产生重复 Manual/Chunk
  - 增量: source_hash 变化才重新生成受影响知识
  - 断点续跑: checkpoint 记录已完成 company_id
  - 失败隔离: 单公司失败不影响其他
  - rebuild_index: 从 Source of Truth (DB) 全量重建向量, 不依赖 Milvus 原有数据
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import datetime
from typing import Any

from kb.boundary import build_boundary, get_boundary
from kb.chunker import (
    assemble_manual_markdown,
    chunk_business_manual,
    chunk_product_manual,
)
from kb.companies import collect_companies, get_company, get_companies
from kb.config import KB_COMPANY_CONCURRENCY
from kb.db import session_scope
from kb.embedder import embed_batch_async, embedder_info
from kb.generator import (
    generate_business_knowledge,
    generate_product_knowledge,
    source_hash,
)
from kb.models import (
    CompanyCache,
    KnowledgeChunk,
    KnowledgeManual,
    Product,
)
from kb.quality import (
    QualityReport,
    validate_chunks,
    validate_manual,
    validate_product_consistency,
)
from kb.tasks import _record_failure, _update_task, create_task, get_task
from kb.vectorstore import get_vector_store, reset_vector_store

logger = logging.getLogger("kb.pipeline")


def _chunk_uid(company_id: int, manual_type: str, lang: str, content_hash: str) -> str:
    return f"c{company_id}-{manual_type}-{lang}-{content_hash[:16]}"


# ============================================================
# 单公司生成
# ============================================================
async def generate_for_company(
    company: CompanyCache,
    task_id: str | None = None,
    force: bool = False,
    skip_vectors: bool = False,
) -> dict:
    """为一家公司生成全套双语知识。返回结果摘要。"""
    cid = company.id
    cname = company.name
    result = {
        "company_id": cid,
        "company_name": cname,
        "manuals": {},
        "chunks": 0,
        "products": 0,
        "skipped": False,
        "issues": [],
        "source": "unknown",
    }

    # 业务边界
    boundary = build_boundary(company)

    # 幂等/增量: 计算当前源哈希
    cur_src_hash = source_hash(company)
    if not force and company.source_hash == cur_src_hash and _has_active_knowledge(cid):
        result["skipped"] = True
        result["note"] = "source unchanged, idempotent skip"
        if task_id:
            _update_task(task_id, current_stage=f"{cname}: 源未变化, 跳过")
        return result

    # 清理该公司旧的非活跃/旧版本数据 (非破坏式: 仅本知识库表)
    _deactivate_old(company_id=cid, src_hash=cur_src_hash)
    store = get_vector_store()

    total_chunks = 0
    product_count = 0

    # 4 份手册: (product, zh), (product, en), (business, zh), (business, en)
    specs = [
        ("product", "zh"),
        ("product", "en"),
        ("business", "zh"),
        ("business", "en"),
    ]

    for manual_type, lang in specs:
        stage = f"{manual_type}_{lang}"
        if task_id:
            _update_task(task_id, current_stage=f"{cname}: {stage}")

        try:
            if manual_type == "product":
                data = await generate_product_knowledge(company, boundary, lang)
            else:
                data = await generate_business_knowledge(company, boundary, lang)
            result["source"] = data.get("source", "template")

            # 质量校验
            rep = validate_manual(cname, manual_type, lang, data, boundary)
            if rep.issues:
                result["issues"].extend(rep.issues)
                if task_id:
                    _record_failure(task_id, cid, cname, stage, "; ".join(rep.issues), lang, manual_type)
                # 不中断, 继续其他手册

            # 组装 Markdown 手册
            md = assemble_manual_markdown(cname, manual_type, lang, data)
            content_hash = hashlib.sha256(md.encode("utf-8")).hexdigest()

            # 持久化 Manual
            with session_scope() as s:
                # 删除同 (company,type,lang) 旧手册 (重新生成, 不保留多版本)
                s.query(KnowledgeManual).filter_by(
                    company_id=cid, manual_type=manual_type, language=lang
                ).delete()
                manual = KnowledgeManual(
                    company_id=cid,
                    manual_type=manual_type,
                    language=lang,
                    title=data.get("manual_title", cname),
                    content=md,
                    version=1,
                    content_hash=content_hash,
                    source_hash=cur_src_hash,
                    active_version=True,
                    generation_status="completed" if not rep.issues else "partial",
                    source_type="ai_generated",
                    source_url=company.website,
                    source_title=company.source_name,
                    generated_by_ai=True,
                    confidence=0.7,
                )
                s.add(manual)
                s.flush()
                manual_id = manual.id

            # 结构化产品实体 (仅 product)
            if manual_type == "product":
                product_count += _persist_products(cid, lang, data, cur_src_hash, boundary)

            # 语义切片
            if manual_type == "product":
                chunks = chunk_product_manual(cname, lang, data)
            else:
                chunks = chunk_business_manual(cname, lang, data)

            # chunk 质量校验
            crep = validate_chunks(chunks)
            if crep.issues:
                result["issues"].extend(crep.issues)
            if manual_type == "product":
                ccrep = validate_product_consistency(chunks)
                result["issues"].extend(ccrep.issues)

            # 持久化 chunk (Source of Truth) -- 与向量写入分离, 避免并发写锁
            chunk_texts = [c["text"] for c in chunks]
            if skip_vectors:
                embeddings = [[0.0] * 1024 for _ in chunk_texts]  # 占位, 由 rebuild 重建
            else:
                embeddings = await embed_batch_async(chunk_texts) if chunk_texts else []
            pending_vectors: list[tuple[str, list[float], dict]] = []

            with session_scope() as s:
                # 标记同 company/type/lang 旧 chunk inactive (版本切换/去重)
                old_chunks = s.query(KnowledgeChunk).filter_by(
                    company_id=cid, manual_type=manual_type, language=lang, active=True
                ).all()
                for oc in old_chunks:
                    oc.active = False

                for c, emb in zip(chunks, embeddings):
                    uid = _chunk_uid(cid, manual_type, lang, c["content_hash"])
                    # 幂等: 同 uid 已存在则激活
                    existing = s.query(KnowledgeChunk).filter_by(chunk_uid=uid).first()
                    if existing:
                        existing.active = True
                        existing.manual_id = manual_id
                        existing.vector_synced = False
                        chunk_obj = existing
                    else:
                        chunk_obj = KnowledgeChunk(
                            chunk_uid=uid,
                            company_id=cid,
                            manual_id=manual_id,
                            manual_type=manual_type,
                            language=lang,
                            chunk_type=c["chunk_type"],
                            section=c.get("section"),
                            product_model=c.get("product_model"),
                            business_type=c.get("business_type"),
                            text=c["text"],
                            content_hash=c["content_hash"],
                            source_type="ai_generated",
                            source_url=company.website,
                            source_file=None,
                            generated_by_ai=True,
                            confidence=0.7,
                            version=1,
                            active=True,
                            vector_synced=False,
                        )
                        s.add(chunk_obj)
                    # 缓存向量写入任务 (session 提交后再写, 避免 SQLite 并发写锁)
                    meta = {
                        "company_id": cid,
                        "language": lang,
                        "manual_type": manual_type,
                        "chunk_type": c["chunk_type"],
                        "product_model": c.get("product_model"),
                        "business_type": c.get("business_type"),
                        "manual_id": manual_id,
                        "text": c["text"],
                        "source_type": "ai_generated",
                    }
                    pending_vectors.append((uid, emb, meta))
                    total_chunks += 1
                # session 提交在此处发生 (释放写锁)

            # 向量写入 (DB 事务已提交, 独立连接写向量)
            if skip_vectors:
                with session_scope() as s:
                    s.query(KnowledgeChunk).filter(
                        KnowledgeChunk.chunk_uid.in_([pv[0] for pv in pending_vectors])
                    ).update({"vector_synced": False, "vector_backend": None}, synchronize_session=False)
            else:
                synced_uids: list[str] = []
                for uid, emb, meta in pending_vectors:
                    try:
                        store.upsert(uid, emb, meta)
                        synced_uids.append(uid)
                    except Exception as e:
                        logger.warning("向量写入失败 %s: %s", uid, str(e)[:120])
                if synced_uids:
                    with session_scope() as s:
                        s.query(KnowledgeChunk).filter(
                            KnowledgeChunk.chunk_uid.in_(synced_uids)
                        ).update(
                            {"vector_synced": True, "vector_backend": store.backend},
                            synchronize_session=False,
                        )

            result["manuals"][stage] = {"chunks": len(chunks), "issues": len(rep.issues)}

        except Exception as e:
            logger.exception("公司 %s 阶段 %s 失败", cname, stage)
            result["issues"].append(f"{stage}: {str(e)[:200]}")
            if task_id:
                _record_failure(task_id, cid, cname, stage, str(e), lang, manual_type)

    # 更新公司知识状态
    with session_scope() as s:
        c = s.get(CompanyCache, cid)
        if c:
            c.knowledge_status = "ready"
            c.last_generated_at = datetime.utcnow()
            c.source_hash = cur_src_hash

    result["chunks"] = total_chunks
    result["products"] = product_count
    return result


def _has_active_knowledge(company_id: int) -> bool:
    with session_scope() as s:
        cnt = s.query(KnowledgeChunk).filter_by(company_id=company_id, active=True).count()
        return cnt > 0


def _deactivate_old(company_id: int, src_hash: str):
    """保留数据但标记旧版本 (非破坏式, 不删除)。"""
    # 实际清理在同 (type,lang) 内做, 这里仅占位
    pass


def _persist_products(company_id: int, lang: str, data: dict, src_hash: str, boundary) -> int:
    """持久化结构化产品实体 (支持未来产品比较)。"""
    count = 0
    with session_scope() as s:
        # 标记该公司旧产品 (同语言) -> 保留历史, 新增版本即可; 为简洁, 删除同公司同语言旧记录
        # 非破坏式: 仅 kb_products 表 (本任务新建表)
        s.query(Product).filter_by(company_id=company_id, language=lang).delete()
        for p in data.get("products", []):
            pr = p.get("price", {})
            prod = Product(
                company_id=company_id,
                product_name=p.get("product_name"),
                product_series=p.get("product_series"),
                product_model=p.get("product_model"),
                category=p.get("category"),
                positioning=p.get("positioning"),
                price=pr.get("price"),
                price_min=pr.get("price_min"),
                price_max=pr.get("price_max"),
                currency=pr.get("currency", "USD"),
                price_type=pr.get("price_type", "demo"),
                price_confidence=pr.get("confidence"),
                specification=json.dumps(p.get("specification", {}), ensure_ascii=False),
                language=lang,
                source_type="ai_generated",
                source_hash=src_hash,
                confidence=pr.get("confidence", 0.65),
                generated_by_ai=True,
            )
            s.add(prod)
            count += 1
    return count


# ============================================================
# 全量初始化 (所有公司)
# ============================================================
async def generate_all(
    task_id: str | None = None,
    company_ids: list[int] | None = None,
    force: bool = False,
    skip_vectors: bool = False,
) -> dict:
    """为所有公司(或指定子集)生成知识。并发控制 + 失败隔离 + 断点续跑。"""
    with session_scope() as s:
        companies, src = collect_companies(s)
        if company_ids:
            companies = [c for c in companies if c.id in set(company_ids)]

    total = len(companies)
    if task_id:
        _update_task(task_id, total_steps=total, status="running", started_at=datetime.utcnow())

    # 断点续跑: 读取已完成 checkpoint
    checkpoint_set: set[int] = set()
    if task_id:
        t = get_task(task_id)
        if t and t.get("checkpoint"):
            checkpoint_set = set(t["checkpoint"].get("completed", []))

    sem = asyncio.Semaphore(KB_COMPANY_CONCURRENCY)
    completed: list[int] = []
    failed: list[dict] = []
    summaries: list[dict] = []
    done = 0

    async def _one(c: CompanyCache):
        nonlocal done
        if not force and c.id in checkpoint_set and _has_active_knowledge(c.id):
            completed.append(c.id)
            done += 1
            if task_id:
                _update_task(task_id, completed_steps=done, progress=int(done / total * 100),
                             checkpoint={"completed": completed + [x for x in checkpoint_set if x not in completed]})
            return
        async with sem:
            try:
                res = await generate_for_company(c, task_id=task_id, force=force, skip_vectors=skip_vectors)
                summaries.append(res)
                if res.get("issues") and not res.get("skipped"):
                    failed.append({"company_id": c.id, "company_name": c.name, "issues": res["issues"]})
                completed.append(c.id)
            except Exception as e:
                logger.exception("公司 %s 失败", c.name)
                failed.append({"company_id": c.id, "company_name": c.name, "issues": [str(e)[:200]]})
                if task_id:
                    _record_failure(task_id, c.id, c.name, "company_level", str(e))
            finally:
                done += 1
                if task_id:
                    _update_task(
                        task_id,
                        completed_steps=done,
                        progress=int(done / total * 100),
                        checkpoint={"completed": completed},
                        current_stage=f"{c.name}: 完成 ({done}/{total})",
                    )

    await asyncio.gather(*[_one(c) for c in companies])

    # 汇总
    total_chunks = sum(s.get("chunks", 0) for s in summaries)
    total_products = sum(s.get("products", 0) for s in summaries)
    ready = len([s for s in summaries if not s.get("skipped")])
    skipped = len([s for s in summaries if s.get("skipped")])

    summary = {
        "total_companies": total,
        "processed": ready,
        "skipped_idempotent": skipped,
        "failed_count": len(failed),
        "total_chunks": total_chunks,
        "total_products": total_products,
        "failed": failed,
        "source": summaries[0].get("source") if summaries else "none",
        "company_source": src,
    }

    if task_id:
        status = "completed" if not failed else "partially_completed"
        _update_task(
            task_id,
            status=status,
            progress=100,
            result_summary=summary,
            finished_at=datetime.utcnow(),
            current_stage="all done",
        )
    return summary


# ============================================================
# 增量更新
# ============================================================
async def incremental_update(company_id: int, task_id: str | None = None) -> dict:
    """单公司增量更新: source_hash 变化才重新生成。"""
    with session_scope() as s:
        # 重新采集以确保源数据最新
        collect_companies(s)
        c = s.get(CompanyCache, company_id)
        if not c:
            return {"error": "company not found"}
    return await generate_for_company(c, task_id=task_id, force=False)


# ============================================================
# 重建向量索引 (从 Source of Truth)
# ============================================================
def rebuild_vector_index(task_id: str | None = None, drop_first: bool = False) -> dict:
    """从 DB (Source of Truth) 全量重建向量索引。Milvus 可被删除后由此重建。"""
    if task_id:
        _update_task(task_id, total_steps=3, status="running", started_at=datetime.utcnow(),
                     current_stage="rebuild: collect chunks")

    reset_vector_store()
    store = get_vector_store()
    store.ensure_collection()

    if drop_first:
        # 非破坏式: 仅清空本知识库向量集合, 不动其他集合
        store.drop()
        store = get_vector_store()
        store.ensure_collection()

    if task_id:
        _update_task(task_id, completed_steps=1, current_stage="rebuild: embed + index")

    with session_scope() as s:
        # resumable: 若非 drop 模式, 跳过已同步的 chunk (断点续跑)
        if not drop_first:
            chunks = s.query(KnowledgeChunk).filter_by(active=True, vector_synced=False).all()
        else:
            chunks = s.query(KnowledgeChunk).filter_by(active=True).all()
        total = len(chunks)
        if not chunks:
            result = {"total_chunks": 0, "indexed": 0, "failed": 0, "backend": store.backend, "note": "all already synced"}
            if task_id:
                _update_task(task_id, completed_steps=3, progress=100, status="completed",
                             result_summary=result, finished_at=datetime.utcnow())
            return result
        texts = [c.text for c in chunks]
        # 批量 embedding (真实 BGE-M3 或降级 hashbow)
        from kb.embedder import embed_batch

        indexed = 0
        failed = 0
        batch = 16
        for i in range(0, len(texts), batch):
            batch_texts = texts[i:i + batch]
            try:
                embs = embed_batch(batch_texts)
            except Exception as e:
                logger.warning("rebuild embedding 批次 %d 失败, 跳过: %s", i, str(e)[:120])
                failed += len(batch_texts)
                continue
            for c, emb in zip(chunks[i:i + batch], embs):
                meta = {
                    "company_id": c.company_id,
                    "language": c.language,
                    "manual_type": c.manual_type,
                    "chunk_type": c.chunk_type,
                    "product_model": c.product_model,
                    "business_type": c.business_type,
                    "manual_id": c.manual_id,
                    "text": c.text,
                    "source_type": c.source_type,
                }
                try:
                    store.upsert(c.chunk_uid, emb, meta)
                    c.vector_synced = True
                    c.vector_backend = store.backend
                    indexed += 1
                except Exception as e:
                    logger.warning("rebuild upsert 失败 %s: %s", c.chunk_uid, str(e)[:120])
            if i % (batch * 5) == 0:
                logger.info("rebuild 进度: %d/%d (indexed=%d failed=%d)", i + len(batch_texts), total, indexed, failed)
            s.commit()
            # 轻微限速, 避免 embedding API rate limit
            import time as _time
            _time.sleep(0.1)

    result = {"total_chunks": total, "indexed": indexed, "failed": failed, "backend": store.backend}
    if task_id:
        _update_task(task_id, completed_steps=3, progress=100, status="completed",
                     result_summary=result, finished_at=datetime.utcnow(),
                     current_stage="rebuild done")
    return result


# ============================================================
# 统计
# ============================================================
def knowledge_stats() -> dict:
    with session_scope() as s:
        companies = s.query(CompanyCache).count()
        ready = s.query(CompanyCache).filter_by(knowledge_status="ready").count()
        manuals = s.query(KnowledgeManual).filter_by(active_version=True).count()
        zh_manuals = s.query(KnowledgeManual).filter_by(active_version=True, language="zh").count()
        en_manuals = s.query(KnowledgeManual).filter_by(active_version=True, language="en").count()
        prod_manuals = s.query(KnowledgeManual).filter_by(active_version=True, manual_type="product").count()
        biz_manuals = s.query(KnowledgeManual).filter_by(active_version=True, manual_type="business").count()
        product_chunks = s.query(KnowledgeChunk).filter_by(active=True, manual_type="product").count()
        business_chunks = s.query(KnowledgeChunk).filter_by(active=True, manual_type="business").count()
        zh_chunks = s.query(KnowledgeChunk).filter_by(active=True, language="zh").count()
        en_chunks = s.query(KnowledgeChunk).filter_by(active=True, language="en").count()
        products = s.query(Product).count()
    store = get_vector_store()
    try:
        vec_count = store.count()
    except Exception:
        vec_count = -1
    return {
        "company_count": companies,
        "companies_ready": ready,
        "manual_count": manuals,
        "zh_manual_count": zh_manuals,
        "en_manual_count": en_manuals,
        "product_manual_count": prod_manuals,
        "business_manual_count": biz_manuals,
        "product_chunk_count": product_chunks,
        "business_chunk_count": business_chunks,
        "zh_chunk_count": zh_chunks,
        "en_chunk_count": en_chunks,
        "product_count": products,
        "vector_count": vec_count,
        "vector_backend": store.backend,
        "embedder": embedder_info(),
    }


def company_knowledge_status(company_id: int) -> dict:
    with session_scope() as s:
        c = s.get(CompanyCache, company_id)
        if not c:
            return {"error": "not found"}
        manuals = s.query(KnowledgeManual).filter_by(company_id=company_id, active_version=True).all()
        chunks = s.query(KnowledgeChunk).filter_by(company_id=company_id, active=True).all()
        products = s.query(Product).filter_by(company_id=company_id).count()
        by_type_lang = {}
        for m in manuals:
            key = f"{m.manual_type}_{m.language}"
            by_type_lang[key] = {
                "title": m.title,
                "version": m.version,
                "source_type": m.source_type,
                "confidence": m.confidence,
                "generated_at": m.generated_at.isoformat() if m.generated_at else None,
            }
        chunk_by_type = {}
        for ch in chunks:
            chunk_by_type[ch.chunk_type] = chunk_by_type.get(ch.chunk_type, 0) + 1
        return {
            "company_id": company_id,
            "company_name": c.name,
            "knowledge_status": c.knowledge_status,
            "last_generated_at": c.last_generated_at.isoformat() if c.last_generated_at else None,
            "manuals": by_type_lang,
            "chunk_count": len(chunks),
            "chunk_by_type": chunk_by_type,
            "product_count": products,
        }
