"""管理员知识库管理 API: 生成 / 增量更新 / 重建索引 / 任务状态 / 统计。"""

from __future__ import annotations

import asyncio
import threading

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from kb import tasks as kb_tasks
from kb.config import runtime_capabilities
from kb.pipeline import (
    generate_all,
    incremental_update,
    knowledge_stats,
    rebuild_vector_index,
)
from api.deps import require_admin

router = APIRouter(prefix="/admin/kb", tags=["admin-kb"])


def _run_async(coro, task_id: str):
    """在独立线程的 event loop 中运行异步任务 (不阻塞 API)。"""

    def _worker():
        try:
            asyncio.run(coro)
        except Exception as e:  # pragma: no cover
            kb_tasks._update_task(task_id, status="failed",
                                  error_message=str(e)[:2000],
                                  finished_at=__import__("datetime").datetime.utcnow())

    threading.Thread(target=_worker, daemon=True).start()


class GenerateRequest(BaseModel):
    company_ids: list[int] | None = None  # None = 全部
    force: bool = False


@router.post("/generate")
def start_generate(req: GenerateRequest, user: dict = Depends(require_admin)):
    """启动知识生成任务 (全部公司或指定子集)。"""
    task_id = kb_tasks.create_task(
        "generate",
        total_steps=len(req.company_ids) if req.company_ids else 30,
    )
    _run_async(generate_all(task_id=task_id, company_ids=req.company_ids, force=req.force), task_id)
    return {"task_id": task_id, "status": "pending", "message": "知识生成任务已启动"}


@router.post("/incremental/{company_id}")
def start_incremental(company_id: int, user: dict = Depends(require_admin)):
    """单公司增量更新。"""
    task_id = kb_tasks.create_task("incremental_update", company_id=company_id, total_steps=4)
    _run_async(incremental_update(company_id, task_id=task_id), task_id)
    return {"task_id": task_id, "status": "pending"}


class RebuildRequest(BaseModel):
    drop_first: bool = False


@router.post("/rebuild-index")
def start_rebuild(req: RebuildRequest, user: dict = Depends(require_admin)):
    """从 Source of Truth 重建向量索引。"""
    task_id = kb_tasks.create_task("rebuild_index", total_steps=3)

    def _worker():
        try:
            rebuild_vector_index(task_id=task_id, drop_first=req.drop_first)
        except Exception as e:  # pragma: no cover
            kb_tasks._update_task(task_id, status="failed", error_message=str(e)[:2000])

    threading.Thread(target=_worker, daemon=True).start()
    return {"task_id": task_id, "status": "pending"}


@router.get("/tasks")
def list_tasks(user: dict = Depends(require_admin)):
    return {"items": kb_tasks.list_tasks()}


@router.get("/tasks/{task_id}")
def get_task(task_id: str, user: dict = Depends(require_admin)):
    t = kb_tasks.get_task(task_id)
    if not t:
        raise HTTPException(status_code=404, detail="task not found")
    return t


@router.get("/tasks/{task_id}/failures")
def task_failures(task_id: str, user: dict = Depends(require_admin)):
    return {"items": kb_tasks.list_failures(task_id)}


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str, user: dict = Depends(require_admin)):
    kb_tasks.cancel_task(task_id)
    return {"task_id": task_id, "status": "cancelled"}


@router.get("/stats")
def get_stats(user: dict = Depends(require_admin)):
    return knowledge_stats()


@router.get("/capabilities")
def get_capabilities(user: dict = Depends(require_admin)):
    """运行时能力 (LLM/Embedding/向量库/数据库 后端)。"""
    return runtime_capabilities()
