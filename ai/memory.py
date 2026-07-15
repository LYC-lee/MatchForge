"""
MatchForge 长期记忆系统 (PostgreSQL)

按 user_id 隔离，存储用户跨会话的偏好和历史:
  - brand_pref:           品牌偏好 ["YAGEO", "Murata"]
  - preferred_suppliers:  常用供应商 [{id, name, score}]
  - search_history:       历史搜索 [{query, part_number, time}]
  - part_history:         历史型号 [{part_number, brand, time}]
  - settings:             用户设置 {region, default_lead_time}

用法:
  from ai.memory import AgentMemory

  # 在 Agent 中读取用户记忆
  mem = AgentMemory(user_id)
  brands = await mem.get_brand_pref()     # → ["YAGEO"]

  # 写入
  await mem.add_brand_pref("YAGEO")
  await mem.add_search("TMK212BJ105KG-T", raw_query)

  # 注入 State 让下游 Agent 感知
  state = await mem.inject(state)
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import create_engine, text
from ai.config import (
    MYSQL_URL, MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE,
    POSTGRESQL_URL,
)

logger = logging.getLogger("matchforge.memory")

# ============================================================
# 建表 DDL (MySQL 兼容 — 复用现有 MySQL)
# ============================================================
MEMORY_TABLE = "user_memories"
MEMORY_DDL = f"""
CREATE TABLE IF NOT EXISTS {MEMORY_TABLE} (
    id              BIGSERIAL PRIMARY KEY,
    user_id         VARCHAR(64)     NOT NULL,
    memory_key      VARCHAR(128)    NOT NULL,
    memory_value    JSONB           NOT NULL,
    updated_at      TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, memory_key)
);
CREATE INDEX IF NOT EXISTS idx_user ON {MEMORY_TABLE} (user_id);
"""


def _get_engine():
    """返回 PostgreSQL 引擎（如不可用则降级到 MySQL）"""
    try:
        return create_engine(POSTGRESQL_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)
    except Exception:
        return create_engine(MYSQL_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)


def ensure_table():
    """启动时确保 memory 表存在"""
    try:
        engine = _get_engine()
        with engine.connect() as conn:
            conn.execute(text(MEMORY_DDL))
            conn.commit()
        logger.info("✅ 记忆表已就绪 (MySQL)")
    except Exception as e:
        logger.warning(f"⚠️  记忆表初始化失败: {e}")


# ============================================================
# AgentMemory — 单个用户的记忆管理器
# ============================================================
class AgentMemory:
    """
    Agent 可访问的用户长期记忆。

    所有 key 命名规范:
      - 列表型: 复数 (brand_pref, preferred_suppliers)
      - 记录型: _history 后缀
      - 配置型: 单数 (settings)
    """

    MEMORY_KEYS = {
        "brand_pref",           # list[str] — 品牌偏好
        "preferred_suppliers",  # list[dict] — 常用供应商
        "search_history",       # list[dict] — 搜索历史
        "part_history",         # list[dict] — 型号历史
        "settings",             # dict — 用户设置
    }

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._engine = _get_engine()

    # ============================================================
    # 品牌偏好
    # ============================================================
    async def get_brand_pref(self) -> list[str]:
        val = await self._get("brand_pref")
        return val if isinstance(val, list) else []

    async def add_brand_pref(self, brand: str):
        brands = await self.get_brand_pref()
        if brand not in brands:
            brands.append(brand)
            await self._put("brand_pref", brands)

    async def remove_brand_pref(self, brand: str):
        brands = await self.get_brand_pref()
        if brand in brands:
            brands.remove(brand)
            await self._put("brand_pref", brands)

    # ============================================================
    # 搜索历史
    # ============================================================
    async def get_search_history(self, limit: int = 10) -> list[dict]:
        val = await self._get("search_history")
        if isinstance(val, list):
            return val[-limit:]
        return []

    async def add_search(self, part_number: str, raw_query: str = ""):
        history = await self._get("search_history") or []
        history.append({
            "part_number": part_number[:64],
            "query": raw_query[:200],
            "time": datetime.now(timezone.utc).isoformat(),
        })
        await self._put("search_history", history[-50:])

    # ============================================================
    # 型号历史
    # ============================================================
    async def get_part_history(self, limit: int = 20) -> list[dict]:
        val = await self._get("part_history")
        if isinstance(val, list):
            return val[-limit:]
        return []

    async def add_part(self, part_number: str, brand: str = "", source: str = ""):
        history = await self._get("part_history") or []
        # 去重更新
        for entry in history:
            if entry.get("part_number") == part_number:
                entry["time"] = datetime.now(timezone.utc).isoformat()
                if brand:
                    entry["brand"] = brand
                await self._put("part_history", history)
                return
        history.append({
            "part_number": part_number[:64],
            "brand": brand[:64],
            "source": source[:32],
            "time": datetime.now(timezone.utc).isoformat(),
        })
        await self._put("part_history", history[-100:])

    # ============================================================
    # 常用供应商
    # ============================================================
    async def get_preferred_suppliers(self) -> list[dict]:
        val = await self._get("preferred_suppliers")
        return val if isinstance(val, list) else []

    async def add_preferred_supplier(self, supplier_id: str, name: str, score: float = 0.0):
        suppliers = await self.get_preferred_suppliers()
        for s in suppliers:
            if s.get("id") == supplier_id:
                s["time"] = datetime.now(timezone.utc).isoformat()
                if score:
                    s["score"] = score
                await self._put("preferred_suppliers", suppliers)
                return
        suppliers.append({"id": supplier_id, "name": name[:128], "score": score,
                          "time": datetime.now(timezone.utc).isoformat()})
        await self._put("preferred_suppliers", suppliers)

    # ============================================================
    # 用户设置
    # ============================================================
    async def get_setting(self, key: str, default=None):
        settings = await self._get("settings")
        return settings.get(key, default) if isinstance(settings, dict) else default

    async def set_setting(self, key: str, value):
        settings = await self._get("settings") or {}
        settings[key] = value
        await self._put("settings", settings)

    # ============================================================
    # 注入到 State
    # ============================================================
    async def inject(self, state: dict) -> dict:
        """
        将用户记忆注入到 ProcureState 中，
        让 Agent 可以感知用户偏好。

        注入字段 (不会覆盖已有值):
          - state["user_brand_pref"]   — 品牌偏好
          - state["user_settings"]     — 用户设置
          - state["user_part_history"] — 最近型号
        """
        brands = await self.get_brand_pref()
        if brands and "user_brand_pref" not in state:
            state["user_brand_pref"] = brands
        # 如果 parsed_spec 里没有 brand_pref，用记忆补
        if brands:
            spec = state.get("parsed_spec") or {}
            if isinstance(spec, dict) and "brand_pref" not in spec:
                spec["brand_pref"] = brands
                state["parsed_spec"] = spec

        settings = await self.get_all_settings()
        if settings:
            state["user_settings"] = settings

        parts = await self.get_part_history(5)
        if parts:
            state["user_part_history"] = parts

        return state

    async def get_all_settings(self) -> dict:
        val = await self._get("settings")
        return val if isinstance(val, dict) else {}

    async def get_all(self) -> dict:
        """读取该用户所有记忆"""
        try:
            with self._engine.connect() as conn:
                result = conn.execute(
                    text("SELECT memory_key, memory_value FROM user_memories WHERE user_id = :uid"),
                    {"uid": self.user_id},
                )
                rows = result.fetchall()
                return {row[0]: json.loads(row[1]) if isinstance(row[1], str) else row[1]
                        for row in rows}
        except Exception as e:
            logger.warning(f"[memory] get_all 失败: {e}")
            return {}

    # ============================================================
    # 底层 CRUD
    # ============================================================
    async def _get(self, key: str):
        try:
            with self._engine.connect() as conn:
                result = conn.execute(
                    text("SELECT memory_value FROM user_memories WHERE user_id = :uid AND memory_key = :key"),
                    {"uid": self.user_id, "key": key},
                )
                row = result.fetchone()
                if row:
                    val = row[0]
                    return json.loads(val) if isinstance(val, str) else val
                return None
        except Exception as e:
            logger.warning(f"[memory] get({key}) 失败: {e}")
            return None

    async def _put(self, key: str, value):
        try:
            val_json = json.dumps(value, ensure_ascii=False)
            with self._engine.connect() as conn:
                conn.execute(
                    text(f"""
                        INSERT INTO {MEMORY_TABLE} (user_id, memory_key, memory_value)
                        VALUES (:uid, :key, :val)
                        ON CONFLICT (user_id, memory_key)
                        DO UPDATE SET memory_value = :val2, updated_at = NOW()
                    """),
                    {"uid": self.user_id, "key": key, "val": val_json, "val2": val_json},
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"[memory] put({key}) 失败: {e}")


# ============================================================
# Agent 辅助函数 — 在 Agent 入口处调用
# ============================================================
async def inject_user_memory(state: dict) -> dict:
    """
    如果 state 包含 user_id，注入该用户的长期记忆。

    在 supervisor.run_procure_stream 的入口处调用一次。
    """
    user_id = state.get("user_id")
    if not user_id:
        return state
    mem = AgentMemory(user_id)
    return await mem.inject(state)


async def save_search_to_memory(user_id: str, part_number: str, raw_query: str):
    """保存搜索记录到记忆"""
    if not user_id:
        return
    mem = AgentMemory(user_id)
    await mem.add_search(part_number, raw_query)


async def save_part_to_memory(user_id: str, part_number: str, brand: str = "", source: str = ""):
    """保存型号到记忆"""
    if not user_id:
        return
    mem = AgentMemory(user_id)
    await mem.add_part(part_number, brand, source)


# ============================================================
# 查询工具
# ============================================================
def get_user_memory_snapshot(user_id: str) -> dict:
    """
    同步获取用户记忆快照 (用于调试/管理后台)

    用法:
        snapshot = get_user_memory_snapshot("user-abc")
        print(snapshot["brand_pref"])  # ["YAGEO", "Murata"]
    """
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        mem = AgentMemory(user_id)
        return loop.run_until_complete(mem.get_all())
    finally:
        loop.close()