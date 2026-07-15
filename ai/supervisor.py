"""
Supervisor + LangGraph 图构建 + SSE 推送

职责:
  1. 接收请求，初始化 Graph State
  2. 按序调度子 Agent
  3. 管理 State 流转
  4. 子 Agent 失败时捕获异常，写入 errors[]，继续下游
  5. 通过 SSE 向前端回传进度

SSE 格式 (与前端 api/sse.ts 对齐):
  data: {"type":"start","thread_id":"xxx","rfq_id":"xxx"}\n\n
  data: {"type":"progress","agent":"parse","status":"running"}\n\n
  data: {"type":"progress","agent":"parse","status":"done","result":{...}}\n\n
  data: {"type":"result","state":{...}}\n\n
  data: {"type":"end"}\n\n

两阶段流程:
  第一阶段 (phase=spec):  parse → normalize → 返回结果，等待用户确认规格
  第二阶段 (phase=match): alternatives → match → gen_rfq → grade → 返回完整结果
"""

import uuid
import json
from datetime import datetime
from typing import AsyncGenerator, Optional

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

from ai.state import ProcureState
from ai.agents.parse import parse_agent
from ai.agents.normalize import normalize_agent
from ai.agents.alternatives import alternatives_agent
from ai.agents.match import match_agent
from ai.agents.gen_rfq import gen_rfq_agent
from ai.agents.grade import grade_agent

# Agent 进度文案
AGENT_LABELS: dict[str, str] = {
    "parse": "正在识别型号与参数…",
    "normalize": "正在标准化规格…",
    "alternatives": "正在查询替代料…",
    "match": "正在匹配供应商…",
    "gen_rfq": "正在生成询价单…",
    "grade": "正在评估线索…",
}

# 第一阶段 agent 列表
PHASE_SPEC_AGENTS = ["parse", "normalize"]
# 第二阶段 agent 列表
PHASE_MATCH_AGENTS = ["alternatives", "match", "gen_rfq", "grade"]


def build_graph() -> StateGraph:
    """
    构建 LangGraph 图

    图保留完整的 6-agent 结构供端到端调试用。
    生产环境的两阶段流通过 run_procure_stream 直接调用 agent 函数，
    避免重复 invoke 全图导致状态混乱。
    """
    workflow = StateGraph(ProcureState)

    workflow.add_node("parse", parse_agent)
    workflow.add_node("normalize", normalize_agent)
    workflow.add_node("alternatives", alternatives_agent)
    workflow.add_node("match", match_agent)
    workflow.add_node("gen_rfq", gen_rfq_agent)
    workflow.add_node("grade", grade_agent)

    workflow.add_edge(START, "parse")
    workflow.add_edge("parse", "normalize")
    workflow.add_edge("normalize", "alternatives")
    workflow.add_edge("alternatives", "match")
    workflow.add_edge("match", "gen_rfq")
    workflow.add_edge("gen_rfq", "grade")
    workflow.add_edge("grade", END)

    checkpointer = InMemorySaver()
    return workflow.compile(checkpointer=checkpointer)


def init_state(raw_query: str, thread_id: str | None = None) -> ProcureState:
    """初始化 Graph State"""
    return ProcureState(
        thread_id=thread_id or uuid.uuid4().hex[:12],
        raw_query=raw_query,
        parsed_spec=None,
        normalized_spec=None,
        alternatives=[],
        matched_suppliers=[],
        rfq_doc=None,
        rfq_id=None,
        lead_grade=None,
        errors=[],
        started_at=datetime.now().isoformat(),
        completed_at=None,
    )


async def run_procure_stream(
    raw_query: str = "",
    thread_id: str | None = None,
    confirmed_spec: dict | None = None,
    phase: str = "spec",
) -> AsyncGenerator[str, None]:
    """
    执行寻源流程，SSE 流式推送

    直接调用每个 Agent 函数而非重复 invoke 全图，
    避免 LangGraph astream 在循环中每次从 entry 重启的状态混乱。

    参数:
      raw_query: 用户原始需求 (phase=spec 时必填)
      thread_id: 会话 ID
      confirmed_spec: 用户确认后的规格 (phase=match 时必填)
      phase: "spec" (第一阶段 parse+normalize) 或 "match" (第二阶段 alternatives+match+gen_rfq+grade)
    """
    if phase == "spec":
        state = init_state(raw_query, thread_id)
        agent_keys = PHASE_SPEC_AGENTS
        agent_fn_map = {
            "parse": parse_agent,
            "normalize": normalize_agent,
        }
    else:
        state = _load_or_init_state(raw_query, thread_id, confirmed_spec)
        agent_keys = PHASE_MATCH_AGENTS
        agent_fn_map = {
            "alternatives": alternatives_agent,
            "match": match_agent,
            "gen_rfq": gen_rfq_agent,
            "grade": grade_agent,
        }

    # SSE: start
    yield _sse("start", {
        "thread_id": state["thread_id"],
        "rfq_id": state.get("rfq_id"),
    })

    # 逐个 Agent 顺序执行
    for agent_key in agent_keys:
        yield _sse("progress", {"agent": agent_key, "status": "running"})

        try:
            # 直接调用 Agent 函数，传入当前 state，收到更新后 state
            state = await agent_fn_map[agent_key](state)

            yield _sse("progress", {
                "agent": agent_key,
                "status": "done",
                "result": _get_result(state, agent_key),
            })

        except Exception as e:
            state["errors"].append(f"[{agent_key}] {str(e)}")
            yield _sse("error", {"agent": agent_key, "message": str(e)[:200]})

    state["completed_at"] = datetime.now().isoformat()

    # SSE: result — 完整 ProcureState
    yield _sse("result", {
        "state": {
            "thread_id": state["thread_id"],
            "raw_query": state["raw_query"],
            "parsed_spec": state["parsed_spec"],
            "normalized_spec": state["normalized_spec"],
            "alternatives": state["alternatives"],
            "matched_suppliers": state["matched_suppliers"],
            "rfq_doc": state["rfq_doc"],
            "rfq_id": state["rfq_id"],
            "lead_grade": state["lead_grade"],
            "errors": state["errors"],
        },
    })

    # SSE: end
    yield _sse("end", {})


def _load_or_init_state(
    raw_query: str,
    thread_id: str | None,
    confirmed_spec: dict | None,
) -> ProcureState:
    """第二阶段：恢复或新建 state"""
    if confirmed_spec:
        return ProcureState(
            thread_id=thread_id or uuid.uuid4().hex[:12],
            raw_query=raw_query,
            parsed_spec=confirmed_spec,
            normalized_spec=confirmed_spec,
            alternatives=[],
            matched_suppliers=[],
            rfq_doc=None,
            rfq_id=None,
            lead_grade=None,
            errors=[],
            started_at=datetime.now().isoformat(),
            completed_at=None,
        )
    return init_state(raw_query, thread_id)


def _get_result(state: ProcureState, agent_key: str):
    """获取指定 Agent 的输出"""
    mapping = {
        "parse": state.get("parsed_spec"),
        "normalize": state.get("normalized_spec"),
        "alternatives": state.get("alternatives"),
        "match": state.get("matched_suppliers"),
        "gen_rfq": state.get("rfq_doc"),
        "grade": state.get("lead_grade"),
    }
    return mapping.get(agent_key)


def _sse(event_type: str, data: dict) -> str:
    """格式化 SSE 事件 — 与前端 api/sse.ts 对齐"""
    payload = {"type": event_type, **data}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


# 全局图实例
_graph: StateGraph | None = None


def get_graph() -> StateGraph:
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph