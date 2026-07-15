"""
轻量后台任务系统。

当前项目无 Celery/RQ/Dramatiq -> 设计与项目规模匹配的轻量方案:
  - 任务持久化到 SQLite (KbTask), 支持状态/进度/断点续跑
  - In-process asyncio 执行, 并发控制 (KB_TASK_MAX_WORKERS)
  - 失败隔离: 单公司失败不影响其他公司
  - 断点续跑: checkpoint 记录已完成 company_id, 重跑只处理未完成或源变化的
  - 重试: retry_count + 指数退避 (LLM 层)

不引入 Kafka 等复杂中间件。
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Callable

from kb.config import KB_COMPANY_CONCURRENCY
from kb.db import session_scope
from kb.models import KbFailure, KbTask

logger = logging.getLogger("kb.tasks")


def create_task(task_type: str, company_id: int | None = None, total_steps: int = 0) -> str:
    task_id = str(uuid.uuid4())
    with session_scope() as s:
        t = KbTask(
            id=task_id,
            company_id=company_id,
            task_type=task_type,
            total_steps=total_steps,
            completed_steps=0,
            progress=0,
            status="pending",
        )
        s.add(t)
    logger.info("任务创建 %s type=%s company=%s", task_id, task_type, company_id)
    return task_id


def get_task(task_id: str) -> dict | None:
    with session_scope() as s:
        t = s.get(KbTask, task_id)
        if not t:
            return None
        return _task_to_dict(t)


def list_tasks(limit: int = 50) -> list[dict]:
    with session_scope() as s:
        rows = s.query(KbTask).order_by(KbTask.created_at.desc()).limit(limit).all()
        return [_task_to_dict(t) for t in rows]


def _task_to_dict(t: KbTask) -> dict:
    return {
        "task_id": t.id,
        "company_id": t.company_id,
        "task_type": t.task_type,
        "total_steps": t.total_steps,
        "completed_steps": t.completed_steps,
        "progress": t.progress,
        "status": t.status,
        "current_stage": t.current_stage,
        "error_message": t.error_message,
        "retry_count": t.retry_count,
        "checkpoint": json.loads(t.checkpoint) if t.checkpoint else None,
        "result_summary": json.loads(t.result_summary) if t.result_summary else None,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "started_at": t.started_at.isoformat() if t.started_at else None,
        "finished_at": t.finished_at.isoformat() if t.finished_at else None,
    }


def _update_task(task_id: str, **fields):
    with session_scope() as s:
        t = s.get(KbTask, task_id)
        if not t:
            return
        for k, v in fields.items():
            if k == "checkpoint" and isinstance(v, (dict, list)):
                v = json.dumps(v, ensure_ascii=False)
            if k == "result_summary" and isinstance(v, (dict, list)):
                v = json.dumps(v, ensure_ascii=False)
            setattr(t, k, v)


def _record_failure(task_id: str, company_id: int | None, company_name: str | None,
                    stage: str, error: str, language: str | None = None,
                    manual_type: str | None = None, retry: int = 0):
    with session_scope() as s:
        s.add(KbFailure(
            task_id=task_id,
            company_id=company_id,
            company_name=company_name,
            generation_stage=stage,
            language=language,
            manual_type=manual_type,
            retry_count=retry,
            error=error[:2000],
        ))


def list_failures(task_id: str | None = None) -> list[dict]:
    with session_scope() as s:
        q = s.query(KbFailure)
        if task_id:
            q = q.filter_by(task_id=task_id)
        rows = q.order_by(KbFailure.created_at.desc()).limit(200).all()
        return [{
            "company_id": r.company_id,
            "company_name": r.company_name,
            "stage": r.generation_stage,
            "language": r.language,
            "manual_type": r.manual_type,
            "retry_count": r.retry_count,
            "error": r.error,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rows]


def cancel_task(task_id: str) -> bool:
    _update_task(task_id, status="cancelled", finished_at=datetime.utcnow())
    return True
