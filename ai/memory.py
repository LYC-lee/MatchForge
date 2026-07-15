"""
MatchForge 记忆工具函数
已迁移至 LangGraph Store (supervisor.py memory_inject_node / memory_save_node)

此文件保留为外部调用的便利接口 (管理后台/CLI)，核心编排不再依赖它。
"""

import json
import logging
from sqlalchemy import create_engine, text
from ai.config import POSTGRESQL_URL

logger = logging.getLogger("matchforge.memory")
MEMORY_TABLE = "user_memories"


def _get_engine():
    try:
        return create_engine(POSTGRESQL_URL, pool_pre_ping=True, pool_size=3)
    except Exception:
        return None


def get_user_memory_snapshot(user_id: str) -> dict:
    """同步获取用户记忆快照 (管理后台用)
    用法: snapshot = get_user_memory_snapshot("user-abc")
    """
    engine = _get_engine()
    if not engine:
        return {}
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT memory_key, memory_value FROM user_memories WHERE user_id = :uid"),
                {"uid": user_id},
            ).fetchall()
            return {r[0]: json.loads(r[1]) if isinstance(r[1], str) else r[1] for r in rows}
    except Exception as e:
        logger.warning(f"[memory] 读取失败: {e}")
        return {}