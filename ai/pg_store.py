"""
PostgreSQL 会话存储 — 寻源会话历史的持久化存储。

提供会话的 CRUD 操作，支持跨会话、跨设备的会话历史记录。
使用 psycopg2 连接池（线程安全），通过 asyncio.to_thread 在异步环境中调用。
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any

import psycopg2
from psycopg2 import pool

from ai.config import (
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
    POSTGRES_DATABASE,
)

logger = logging.getLogger(__name__)

# ── 连接池 ────────────────────────────────────────────────────────────────
_pool: pool.ThreadedConnectionPool | None = None


def _get_pool() -> pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DATABASE,
        )
    return _pool


@contextmanager
def _conn():
    """获取一个数据库连接（上下文管理器，自动归还）。"""
    p = _get_pool()
    conn = p.getconn()
    try:
        yield conn
    finally:
        p.putconn(conn)


# ── 表初始化 ──────────────────────────────────────────────────────────────

def init_sessions_table():
    """创建 procure_sessions 表（幂等）。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS procure_sessions (
                    thread_id   VARCHAR(32)  PRIMARY KEY,
                    user_id     VARCHAR(64)  NOT NULL,
                    title       VARCHAR(200) NOT NULL,
                    phase       VARCHAR(20)  NOT NULL DEFAULT 'spec',
                    status      VARCHAR(20)  NOT NULL DEFAULT 'completed',
                    state_json  JSONB        DEFAULT '{}'::jsonb,
                    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
                    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_ps_user
                    ON procure_sessions (user_id);
                CREATE INDEX IF NOT EXISTS idx_ps_created
                    ON procure_sessions (created_at DESC);
            """)
            conn.commit()
    logger.info("procure_sessions 表已就绪 (PostgreSQL)")


# ── 会话 CRUD ──────────────────────────────────────────────────────────────

def save_session(
    thread_id: str,
    user_id: str,
    title: str,
    phase: str = "spec",
    status: str = "completed",
    state: dict | None = None,
) -> bool:
    """保存/更新会话记录。"""
    state_json = json.dumps(state or {}, ensure_ascii=False)
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO procure_sessions
                        (thread_id, user_id, title, phase, status, state_json)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (thread_id) DO UPDATE SET
                        title      = EXCLUDED.title,
                        phase      = EXCLUDED.phase,
                        status     = EXCLUDED.status,
                        state_json = EXCLUDED.state_json,
                        updated_at = NOW()
                    """,
                    (thread_id, user_id, title[:200], phase, status, state_json),
                )
                conn.commit()
        return True
    except Exception as e:
        logger.error("保存会话失败: %s", e)
        return False


def list_sessions(user_id: str, limit: int = 50) -> list[dict]:
    """列出用户的所有会话（按时间倒序）。"""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT thread_id, user_id, title, phase, status,
                           created_at, updated_at
                    FROM procure_sessions
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (user_id, limit),
                )
                rows = cur.fetchall()
                return [
                    {
                        "thread_id": r[0],
                        "user_id": r[1],
                        "title": r[2],
                        "phase": r[3],
                        "status": r[4],
                        "created_at": r[5].isoformat() if r[5] else "",
                        "updated_at": r[6].isoformat() if r[6] else "",
                    }
                    for r in rows
                ]
    except Exception as e:
        logger.error("列出会话失败: %s", e)
        return []


def get_session(thread_id: str) -> dict | None:
    """获取单个会话的完整数据（含状态快照）。"""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT thread_id, user_id, title, phase, status,
                           state_json, created_at, updated_at
                    FROM procure_sessions
                    WHERE thread_id = %s
                    """,
                    (thread_id,),
                )
                r = cur.fetchone()
                if not r:
                    return None
                state = r[5] if isinstance(r[5], dict) else json.loads(r[5]) if r[5] else {}
                return {
                    "thread_id": r[0],
                    "user_id": r[1],
                    "title": r[2],
                    "phase": r[3],
                    "status": r[4],
                    "state": state,
                    "created_at": r[6].isoformat() if r[6] else "",
                    "updated_at": r[7].isoformat() if r[7] else "",
                }
    except Exception as e:
        logger.error("获取会话失败: %s", e)
        return None


def delete_session(thread_id: str) -> bool:
    """删除指定会话。"""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM procure_sessions WHERE thread_id = %s",
                    (thread_id,),
                )
                conn.commit()
        return True
    except Exception as e:
        logger.error("删除会话失败: %s", e)
        return False