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

from ai.agents.parse import parse_agent
from ai.agents.normalize import normalize_agent
from ai.agents.alternatives import alternatives_agent
from ai.agents.match import match_agent
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

    # ── 注册节点 ──
    workflow.add_node("memory_inject", memory_inject_node)
    workflow.add_node("supervisor", route)
    for name in _AGENT_MAP:
        workflow.add_node(name, _AGENT_MAP[name])
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
        chat_response=None,
        errors=[],
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
        "gen_rfq": "rfq_doc",
        "grade": "lead_grade",
    }
    key = key_map.get(agent, "")
    return node_output.get(key, base_state.get(key))


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

    if phase == "confirm" and confirmed_spec:
        state["parsed_spec"] = state["normalized_spec"] = confirmed_spec

    agent_keys = set(ROUTING_ORDER)
    graph = get_graph()
    config = {"configurable": {"thread_id": state["thread_id"]}}

    trace = TraceLogger(state["thread_id"], phase)
    trace.begin(state.get("raw_query", ""))
    yield _sse("start", {"thread_id": state["thread_id"]})

    try:
        async for event in graph.astream(state, config, stream_mode="updates"):
            for node_name, node_output in event.items():
                if node_name in agent_keys:
                    yield _sse("progress", {
                        "agent": node_name,
                        "status": "done",
                        "result": _extract_result(state, node_output, node_name),
                    })
                elif node_name == "supervisor" and node_output.get("next_agent") in agent_keys:
                    yield _sse("progress", {
                        "agent": node_output["next_agent"],
                        "status": "running",
                    })
                if isinstance(node_output, dict):
                    state.update(node_output)
    except Exception as e:
        state.setdefault("errors", []).append(f"[graph] {str(e)}")

    trace.end(state)
    yield _sse("result", {
        "state": {
            k: state.get(k) for k in [
                "thread_id", "raw_query", "parsed_spec", "normalized_spec",
                "alternatives", "matched_suppliers", "rfq_doc", "rfq_id",
                "lead_grade", "chat_response", "errors",
            ]
        }
    })
    yield _sse("end", {})