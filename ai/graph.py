"""
LangGraph 多 Agent 工作流编排。

本模块是整个多 Agent 系统的"调度中心"，负责：
1. 构建 LangGraph 状态图（StateGraph），定义节点和边
2. 将 Supervisor 路由决策与 7 个子 Agent 串联为可执行的工作流
3. 提供 run_agent / run_agent_stream 两个入口，供上层调用
4. 长期记忆注入 / 保存（通过 LangGraph Store）

图结构
-------
        START
          │
          ▼
    ┌──────────────┐
    │ memory_inject │  ← 从 Store 加载用户长期记忆
    └──────┬───────┘
           │
           ▼
     ┌───────────┐
     │ supervisor │  ← 入口节点：意图分类 + 路由决策
     └─────┬─────┘
           │ next_agent 决定跳转目标
           ▼
     ┌──────────────────────────────────────────┐
     │ chat │ parse │ normalize │ alternatives  │  ← 7 个子 Agent 节点
     │ match │ gen_rfq │ grade                  │
     └──────────────────────────────────────────┘
           │
           │ 子 Agent 返回 → supervisor（循环）
           │ 或 FINISH → memory_save → END
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from ai.state import ProcureState
from ai.config import POSTGRESQL_URL
from ai.supervisor import route, ROUTING_ORDER
from ai.monitor import TraceLogger

# pg_store 为可选依赖（需要 psycopg2），导入失败不影响主流程
try:
    from ai.pg_store import save_session, init_sessions_table
    _pg_available = True
except ImportError:
    _pg_available = False
    save_session = None  # type: ignore
    init_sessions_table = None  # type: ignore

from ai.agents.parse import parse_agent
from ai.agents.normalize import normalize_agent
from ai.agents.alternatives import alternatives_agent
from ai.agents.match import match_agent
from ai.agents.rag_enrich import rag_enrich_agent
from ai.agents.gen_rfq import gen_rfq_agent
from ai.agents.grade import grade_agent
from ai.agents.chat import chat_agent

logger = logging.getLogger(__name__)

# ── Agent 注册表 ────────────────────────────────────────────────────────
# 将 Agent 名称字符串映射到对应的异步处理函数。
# 新增子 Agent 只需在此字典加一行，图的构建逻辑无需改动。
_AGENT_MAP: dict[str, Any] = {
    "chat": chat_agent,
    "parse": parse_agent,
    "normalize": normalize_agent,
    "alternatives": alternatives_agent,
    "match": match_agent,
    "rag_enrich": rag_enrich_agent,
    "gen_rfq": gen_rfq_agent,
    "grade": grade_agent,
}

# 全局图实例（单例），避免重复构建
_graph: StateGraph | None = None


# ============================================================
# 记忆 Store 节点
# ============================================================
async def memory_inject_node(state: ProcureState, runtime: Any) -> dict:
    """从 LangGraph Store 注入用户长期记忆（品牌偏好、历史记录）。"""
    uid = state.get("user_id")
    if not uid or not runtime.store:
        return {}
    result: dict[str, Any] = {}
    for key in ("brand_pref", "settings"):
        item = runtime.store.get((uid, "preferences"), key)
        if item:
            sk = f"user_{key}" if key == "brand_pref" else "user_settings"
            result[sk] = item.value
    return result


async def memory_save_node(state: ProcureState, runtime: Any) -> dict:
    """保存用户长期记忆到 LangGraph Store（零件历史、品牌偏好）。"""
    uid = state.get("user_id")
    if not uid or not runtime.store:
        return {}
    parsed = state.get("parsed_spec") or {}
    pn = parsed.get("part_number", "")
    hi = runtime.store.get((uid, "preferences"), "part_history")
    parts = list(hi.value) if hi else []
    if pn:
        for p in parts:
            if p.get("part_number") == pn:
                p["time"] = datetime.now().isoformat()
                break
        else:
            parts.append({
                "part_number": pn,
                "brand": parsed.get("brand", ""),
                "time": datetime.now().isoformat(),
            })
        runtime.store.put((uid, "preferences"), "part_history", parts[-100:])
    if parsed.get("brand"):
        pi = runtime.store.get((uid, "preferences"), "brand_pref")
        brands = set(pi.value) if pi else set()
        brands.add(parsed["brand"])
        runtime.store.put((uid, "preferences"), "brand_pref", sorted(brands))
    return {}


# ============================================================
# 图构建
# ============================================================
def build_graph(use_postgres: bool = False) -> StateGraph:
    """构建 LangGraph 多 Agent 工作流图。

    步骤：
    1. 创建 StateGraph，绑定 ProcureState 作为状态类型
    2. 注册 supervisor 节点 + 7 个子 Agent 节点 + 2 个记忆节点
    3. 设置 memory_inject 为入口
    4. 添加条件边：
       - supervisor → 根据 next_agent 路由到对应子 Agent，或 FINISH → memory_save → END
       - 子 Agent → 回到 supervisor（循环）
    5. 编译图，绑定 checkpointer 和 store

    Returns
    -------
    CompiledStateGraph
        编译后的可执行图，支持 ainvoke / astream 等调用方式。
    """
    workflow = StateGraph(ProcureState)

    # ── Agent 执行追踪包装器（防止 supervisor 路由循环）──
    def _wrap_agent(name: str, fn):
        async def _tracked(state: dict) -> dict:
            result = await fn(state)
            if isinstance(result, dict):
                attempted = list(state.get("_attempted_agents", []))
                if name not in attempted:
                    attempted.append(name)
                result["_attempted_agents"] = attempted
            return result
        return _tracked

    # ── 注册节点 ──
    workflow.add_node("memory_inject", memory_inject_node)
    workflow.add_node("supervisor", route)
    for name in _AGENT_MAP:
        workflow.add_node(name, _wrap_agent(name, _AGENT_MAP[name]))
    workflow.add_node("memory_save", memory_save_node)

    # ── 设置入口 ──
    workflow.add_edge(START, "memory_inject")
    workflow.add_edge("memory_inject", "supervisor")

    # ── Supervisor → 子 Agent / FINISH（条件边）──
    route_map = {a: a for a in ROUTING_ORDER} | {"FINISH": "memory_save"}
    workflow.add_conditional_edges(
        "supervisor",
        lambda s: s.get("next_agent", "chat"),
        route_map,
    )

    # ── 子 Agent → supervisor（循环）──
    for a in ROUTING_ORDER:
        workflow.add_edge(a, "supervisor")

    # ── memory_save → END ──
    workflow.add_edge("memory_save", END)

    # ── Checkpointer ──
    if use_postgres and POSTGRESQL_URL:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            checkpointer = PostgresSaver.from_conn_string(POSTGRESQL_URL)
        except Exception:
            logger.warning("PostgresSaver 连接失败，回退到 InMemorySaver")
            checkpointer = InMemorySaver()
    else:
        checkpointer = InMemorySaver()

    return workflow.compile(checkpointer=checkpointer, store=InMemoryStore())


def get_graph() -> StateGraph:
    """获取全局 LangGraph 应用实例（单例模式）。

    首次调用时构建图，后续调用直接返回缓存的实例。
    避免每次请求都重新构建图，节省开销。
    """
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


# ============================================================
# 状态初始化
# ============================================================
def init_state(raw_query: str, user_id: str = "", thread_id: str | None = None) -> ProcureState:
    """创建初始的 ProcureState。"""
    return ProcureState(
        messages=[],
        thread_id=thread_id or uuid.uuid4().hex[:12],
        raw_query=raw_query,
        parsed_spec=None,
        normalized_spec=None,
        alternatives=[],
        matched_suppliers=[],
        rfq_doc=None,
        rfq_id=None,
        lead_grade=None,
        rag_enrichment=None,
        chat_response=None,
        errors=[],
        _attempted_agents=[],
        next_agent="chat",
        route_reason=None,
        user_id=user_id or None,
        started_at=datetime.now().isoformat(),
        completed_at=None,
    )


# ============================================================
# SSE 事件辅助
# ============================================================
def _sse(event_type: str, data: dict) -> str:
    """构建 SSE 格式的事件字符串。"""
    return f"data: {json.dumps({'type': event_type, **data}, ensure_ascii=False)}\n\n"


def _extract_result(base_state: dict, node_output: dict, agent: str) -> Any:
    """从 node_output 或 base_state 中提取 Agent 输出结果。"""
    key_map = {
        "chat": "chat_response",
        "parse": "parsed_spec",
        "normalize": "normalized_spec",
        "alternatives": "alternatives",
        "match": "matched_suppliers",
        "rag_enrich": "rag_enrichment",
        "gen_rfq": "rfq_doc",
        "grade": "lead_grade",
    }
    key = key_map.get(agent, "")
    return node_output.get(key, base_state.get(key))


# ============================================================
# 多轮引用解析 (C4, #23)
# ============================================================
import re as _re

# 指代模式: "第N个" / "第二个" / "刚才那个" / "它" / "这个"
_REFERENCE_RE = _re.compile(
    r"(第\s*(?P<ordinal>[一二三四五六七八九十\d]+)\s*个|刚才那个|那个|它|这个)",
    _re.IGNORECASE,
)

# 序数词映射
_ORDINAL_MAP = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}


def _resolve_references(raw_query: str, snapshot: dict | None) -> tuple[str, str | None]:
    """解析多轮指代, 返回 (增强后的 query, 解析日志)。

    snapshot: 上一轮的 entities_snapshot, 含 alternatives 列表和 current_spec。
    若无法解析, 返回原始 query + 解析日志供 LLM 引导用户。
    """
    if not snapshot or not raw_query:
        return raw_query, None

    m = _REFERENCE_RE.search(raw_query)
    if not m:
        return raw_query, None

    resolved = raw_query
    log = None

    if m.group("ordinal"):
        ordinal_str = m.group("ordinal")
        idx = _ORDINAL_MAP.get(ordinal_str, int(ordinal_str) if ordinal_str.isdigit() else None)
        if idx is not None and snapshot.get("alternatives"):
            alts = snapshot["alternatives"]
            if 1 <= idx <= len(alts):
                target = alts[idx - 1]
                part = target.get("part", target.get("part_name", "未知"))
                resolved = raw_query.replace(m.group(0), f"替代料列表第{idx}项 ({part})")
                log = f"引用解析: 第{idx}个 -> {part}"
    elif m.group(0) == "刚才那个" or m.group(0) == "那个" or m.group(0) == "它" or m.group(0) == "这个":
        spec = snapshot.get("current_spec") or {}
        pn = spec.get("part_number", "")
        if pn:
            resolved = raw_query.replace(m.group(0), f"{pn}")
            log = f"引用解析: {m.group(0)} -> {pn}"
        elif snapshot.get("alternatives"):
            # 没有 spec.part_number, 取第一个替代料
            target = snapshot["alternatives"][0]
            part = target.get("part", target.get("part_name", "未知"))
            resolved = raw_query.replace(m.group(0), f"{part}")
            log = f"引用解析: {m.group(0)} -> {part} (首替代料)"

    return resolved, log


# ============================================================
# 流式执行入口
# ============================================================
async def run_procure_stream(
    raw_query: str = "",
    thread_id: str | None = None,
    confirmed_spec: dict | None = None,
    phase: str = "spec",
    user_id: str = "",
) -> AsyncGenerator[str, None]:
    """SSE 流式执行多 Agent 寻源流程。

    Parameters
    ----------
    raw_query : str
        用户原始输入文本。
    thread_id : str | None
        会话标识，None 则自动生成。
    confirmed_spec : dict | None
        已确认的规格（phase=confirm 时跳过解析）。
    phase : str
        执行阶段，"spec" 或 "confirm"。
    user_id : str
        用户标识，用于长期记忆。

    Yields
    ------
    str
        SSE 格式的事件字符串。
    """
    state = init_state(raw_query, user_id, thread_id)
    state["_phase"] = phase  # 记录原始阶段，供 supervisor 决策

    # ── 多轮引用解析 (C4, #23): 若 state 携带有上一轮的 entities_snapshot ──
    # (前端通过 confirmed_spec 或 extra 字段传入 snapshot; 此处从 confirmed_spec 的 _snapshot 提取)
    if isinstance(confirmed_spec, dict) and confirmed_spec.get("_snapshot"):
        snapshot = confirmed_spec["_snapshot"]
        resolved_query, ref_log = _resolve_references(raw_query, snapshot)
        if ref_log:
            state["raw_query"] = resolved_query
            state["_reference_log"] = ref_log
            logger.info("多轮引用解析: %s", ref_log)

    # phase == "match"（前端传的）或 "confirm"（老名称兼容）时，跳过 parse/normalize
    skip_parse = phase in ("match", "confirm") and confirmed_spec
    if skip_parse:
        state["parsed_spec"] = state["normalized_spec"] = confirmed_spec
        # 标记 parse + normalize 为"已完成"，使 Supervisor 路由直接到 alternatives
        state["_attempted_agents"] = list(state.get("_attempted_agents", []))
        for _done in ("parse", "normalize"):
            if _done not in state["_attempted_agents"]:
                state["_attempted_agents"].append(_done)
        # 标记使用顺序路由（跳过 LLM 决策，避免 LLM 误跳到 gen_rfq/grade）
        state["_use_ordered_fallback"] = True

    agent_keys = set(ROUTING_ORDER)
    graph = get_graph()
    config = {"configurable": {"thread_id": state["thread_id"]}}

    trace = TraceLogger(state["thread_id"], phase)
    trace.begin(state.get("raw_query", ""))
    yield _sse("start", {"thread_id": state["thread_id"]})

    try:
        # #24 真流式: 用 astream_events 捕获 on_chat_model_stream 事件,
        # 逐 token 发 SSE。同时保留 updates 模式的其他事件 (progress/result)。
        # 当 astream_events 不可用时, 降级到 astream(updates) + 伪流式切片。
        use_events = hasattr(graph, "astream_events")

        if use_events:
            try:
                async for event in graph.astream_events(state, config, version="v2"):
                    kind = event.get("event", "")
                    name = event.get("name", "")

                    # on_chat_model_stream: 真 token 流 (#24)
                    # 只发送 chat 节点的 token (排除 supervisor 推理过程)
                    if kind == "on_chat_model_stream" and event.get("data", {}).get("chunk"):
                        chunk = event["data"]["chunk"]
                        if not hasattr(chunk, "content") or not chunk.content:
                            continue
                        # langgraph_node 为 "chat" → 纯 chat 响应; 其他 (如 "supervisor") 忽略
                        node = (event.get("metadata") or {}).get("langgraph_node", "") or event.get("name", "")
                        if node in ("chat",):
                            yield _sse("token", {"agent": "chat", "text": chunk.content})

                    # on_chain_end: 节点完成, 发 progress
                    elif kind == "on_chain_end" and name in agent_keys:
                        node_output = event.get("data", {}).get("output", {}) or {}
                        if isinstance(node_output, dict):
                            state.update(node_output)
                        result = _extract_result(state, node_output, name)

                        # rag_enrich citations (#22)
                        if name == "rag_enrich" and isinstance(node_output, dict):
                            enrich = node_output.get("rag_enrichment")
                            if isinstance(enrich, dict) and enrich.get("citations"):
                                yield _sse("citation", {
                                    "agent": "rag_enrich",
                                    "citations": enrich["citations"],
                                })

                        yield _sse("progress", {
                            "agent": name,
                            "status": "done",
                            "result": result,
                        })
            except Exception:
                # astream_events 失败, 降级到 astream(updates)
                use_events = False

        if not use_events:
            # 降级: astream(updates) + 伪流式切片 (4 字符)
            async for event in graph.astream(state, config, stream_mode="updates"):
                for node_name, node_output in event.items():
                    if node_name in agent_keys:
                        result = _extract_result(state, node_output, node_name)

                        # 伪流式 token (chat/rag_enrich)
                        text_agents = {"chat", "rag_enrich"}
                        if node_name in text_agents and isinstance(result, str) and len(result) > 1:
                            chunk_size = 4
                            for i in range(0, len(result), chunk_size):
                                token = result[i:i + chunk_size]
                                yield _sse("token", {"agent": node_name, "text": token})
                                await asyncio.sleep(0.015)

                        # rag_enrich citations (#22)
                        if node_name == "rag_enrich" and isinstance(node_output, dict):
                            enrich = node_output.get("rag_enrichment")
                            if isinstance(enrich, dict) and enrich.get("citations"):
                                yield _sse("citation", {
                                    "agent": "rag_enrich",
                                    "citations": enrich["citations"],
                                })

                        yield _sse("progress", {
                            "agent": node_name,
                            "status": "done",
                            "result": result,
                        })
                    elif node_name == "supervisor" and node_output.get("next_agent") in agent_keys:
                        yield _sse("progress", {
                            "agent": node_output["next_agent"],
                            "status": "running",
                        })
                    if isinstance(node_output, dict):
                        state.update(node_output)
    except asyncio.CancelledError:
        # abort: 客户端断连 -> 取消流式 (#24)
        logger.info("SSE 流被客户端 abort (CancelledError)")
        state.setdefault("errors", []).append("[graph] 客户端断开连接, 流式已终止")
    except Exception as e:
        state.setdefault("errors", []).append(f"[graph] {str(e)}")

    trace.end(state)

    # ── 保存会话到 PostgreSQL（跨会话/跨设备历史记录）──
    _save_session_safe(state, phase)

    # ── 构建 entities_snapshot (C4, #23): 供前端持久化 + 下轮引用解析 ──
    entities_snapshot = {
        "current_spec": state.get("normalized_spec") or state.get("parsed_spec"),
        "alternatives": state.get("alternatives", []),
        "matched_suppliers": state.get("matched_suppliers", []),
    }
    state["entities_snapshot"] = entities_snapshot

    yield _sse("result", {
        "state": {
            k: state.get(k) for k in [
                "thread_id", "raw_query", "parsed_spec", "normalized_spec",
                "alternatives", "matched_suppliers", "rag_enrichment",
                "rfq_doc", "rfq_id", "lead_grade", "chat_response", "errors",
                "entities_snapshot",
            ]
        }
    })
    yield _sse("end", {})


# ============================================================
# 会话持久化辅助
# ============================================================
def _save_session_safe(state: dict, phase: str):
    """安全保存会话到 PostgreSQL（失败不影响主流程）。"""
    if not _pg_available:
        return

    try:
        # 确保表已创建（幂等，首次调用自动建表）
        init_sessions_table()
    except Exception:
        pass  # 表初始化失败不阻塞主流程

    try:
        thread_id = state.get("thread_id", "")
        user_id = state.get("user_id", "anonymous")
        raw_query = state.get("raw_query", "")[:200]
        title = raw_query if raw_query else "未命名会话"

        # 提取可序列化的状态快照
        state_snapshot = {
            "raw_query": state.get("raw_query", ""),
            "parsed_spec": state.get("parsed_spec"),
            "normalized_spec": state.get("normalized_spec"),
            "alternatives": state.get("alternatives", []),
            "matched_suppliers": state.get("matched_suppliers", []),
            "rag_enrichment": state.get("rag_enrichment"),
            "rfq_doc": state.get("rfq_doc"),
            "rfq_id": state.get("rfq_id"),
            "lead_grade": state.get("lead_grade"),
            "chat_response": state.get("chat_response"),
            "errors": state.get("errors", []),
            "entities_snapshot": state.get("entities_snapshot"),  # C4
        }

        status = "completed" if not state.get("errors") else "error"
        save_session(thread_id, user_id, title, phase, status, state_snapshot)
    except Exception:
        pass  # 保存失败不阻塞 SSE 流