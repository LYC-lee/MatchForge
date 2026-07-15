"""
Supervisor — LangGraph 图编排（主 Agent LLM 路由）

架构:
  START → memory_inject → supervisor → chat/parse → supervisor → normalize
    → supervisor → alternatives → supervisor → match → supervisor
    → gen_rfq → supervisor → grade → memory_save → END

关键设计:
  - 💬 chat Agent 处理闲聊/问候，qwen-plus 轻量模型
  - Supervisor 用 LLM 判断用户意图，路由到 chat 或 parse
  - LangGraph Store 跨会话长期记忆
  - LangSmith 自动 trace
  - PostgresSaver 生产级 checkpointer
"""

import uuid
import json
from datetime import datetime
from typing import AsyncGenerator, Any

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

from ai.state import ProcureState
from ai.config import LLM_MODEL, LLM_BASE_URL, DASHSCOPE_API_KEY, POSTGRESQL_URL
from ai.agents.parse import parse_agent
from ai.agents.normalize import normalize_agent
from ai.agents.alternatives import alternatives_agent
from ai.agents.match import match_agent
from ai.agents.gen_rfq import gen_rfq_agent
from ai.agents.grade import grade_agent
from ai.agents.chat import chat_agent
from ai.monitor import TraceLogger, AgentLogger

AGENT_META: dict[str, dict] = {
    "chat": {"name": "💬 聊天对话", "description": "回复用户的闲聊、问候、功能介绍等非寻源问题",
             "input": "raw_query", "output": "chat_response"},
    "parse": {"name": "需求解析", "description": "将用户自然语言输入解析为结构化元器件规格字段",
              "input": "raw_query", "output": "parsed_spec"},
    "normalize": {"name": "标准化", "description": "将用户规格映射到标准字典编码",
                  "input": "parsed_spec", "output": "normalized_spec"},
    "alternatives": {"name": "替代料推荐", "description": "查找有依据的替代型号，输出5级分类和参数差异",
                     "input": "normalized_spec", "output": "alternatives[]"},
    "match": {"name": "供应商匹配", "description": "匹配经营该品类的候选供应商",
              "input": "normalized_spec + alternatives", "output": "matched_suppliers[]"},
    "gen_rfq": {"name": "询价单生成", "description": "生成可编辑的结构化询价单",
                "input": "parsed_spec + alternatives + matched_suppliers", "output": "rfq_doc"},
    "grade": {"name": "线索分级", "description": "根据商务字段评分，输出 A/B/C/D",
              "input": "parsed_spec", "output": "lead_grade"},
}

SUPERVISOR_PROMPT = PromptTemplate.from_template("""你是电子元器件寻源系统的主调度 Agent。

## 可用子 Agent
{agent_meta}

## 当前 State
- raw_query: "{raw_query}"
- parsed_spec: {parsed_spec_status}
- normalized_spec: {normalized_spec_status}
- alternatives: {alternatives_status}
- matched_suppliers: {suppliers_status}
- rfq_doc: {rfq_doc_status}
- lead_grade: {grade_status}
- errors: {errors_status}

## 用户长期记忆
{brand_memory}

## 路由规则
1. 如果用户是闲聊/问候/问功能 → 输出 chat
2. 如果是寻源需求 → 按 parse → normalize → alternatives → match → gen_rfq → grade 顺序
3. 已完成的不再执行
4. 失败时记录 error，允许跳过
5. 全部完成 → 输出 FINISH

## 输出
只能输出以下之一（纯文本）：
chat / parse / normalize / alternatives / match / gen_rfq / grade / FINISH
""")

ROUTING_ORDER = ["chat", "parse", "normalize", "alternatives", "match", "gen_rfq", "grade"]


def _check_done(state: ProcureState, agent: str) -> bool:
    checks = {
        "chat": state.get("chat_response") is not None,
        "parse": state.get("parsed_spec") is not None,
        "normalize": state.get("normalized_spec") is not None,
        "alternatives": len(state.get("alternatives", [])) > 0,
        "match": len(state.get("matched_suppliers", [])) > 0,
        "gen_rfq": state.get("rfq_doc") is not None,
        "grade": state.get("lead_grade") is not None,
    }
    return checks.get(agent, False)


def _fallback(state: ProcureState) -> str:
    for a in ROUTING_ORDER:
        if not _check_done(state, a):
            return a
    return "FINISH"


_supervisor_llm: ChatOpenAI | None = None


def _get_llm() -> ChatOpenAI:
    global _supervisor_llm
    if _supervisor_llm is None:
        _supervisor_llm = ChatOpenAI(
            base_url=LLM_BASE_URL, api_key=DASHSCOPE_API_KEY,
            model=LLM_MODEL, temperature=0, max_tokens=64, timeout=10,
        )
    return _supervisor_llm


async def supervisor_node(state: ProcureState) -> dict:
    """Supervisor 节点：LLM 判断用户意图，路由到 chat 或 寻源 Agent"""
    agent_lines = "\n".join(
        f"- {k}: {m['name']} — {m['description']}  输入: {m['input']}  输出: {m['output']}"
        for k, m in AGENT_META.items()
    )
    def s(val, done="✅ 已完成", empty="⏳ 待处理"):
        return done if val is not None and val != [] and val != "" else empty
    brands = state.get("user_brand_pref", [])
    brand_line = f"该用户常用品牌: {brands}" if brands else "暂无长期记忆"

    prompt = SUPERVISOR_PROMPT.format(
        agent_meta=agent_lines,
        raw_query=str(state.get("raw_query", ""))[:100],
        parsed_spec_status=s(state.get("parsed_spec")),
        normalized_spec_status=s(state.get("normalized_spec")),
        alternatives_status=s(len(state.get("alternatives", [])) > 0, f"✅ 已找到 {len(state.get('alternatives', []))} 个"),
        suppliers_status=s(len(state.get("matched_suppliers", [])) > 0, f"✅ 已匹配 {len(state.get('matched_suppliers', []))} 家"),
        rfq_doc_status=s(state.get("rfq_doc")),
        grade_status=s(state.get("lead_grade")),
        errors_status=str(state.get("errors", [])) if state.get("errors") else "无",
        brand_memory=brand_line,
    )

    llm = _get_llm()
    try:
        resp = await llm.ainvoke([
            ("human", prompt + "\n\n用户输入: \"" + str(state.get("raw_query", ""))[:100] + "\"\n下一步调用哪个 Agent？"),
        ])
        decision = resp.content.strip().upper().replace(".", "").strip()
        valid = {"CHAT", "PARSE", "NORMALIZE", "ALTERNATIVES", "MATCH", "GEN_RFQ", "GRADE", "FINISH"}
        if decision in valid:
            return {"next_agent": decision.lower() if decision != "FINISH" else "FINISH"}
    except Exception:
        pass
    return {"next_agent": _fallback(state)}


# ============================================================
# 记忆 Store 节点
# ============================================================
async def memory_inject_node(state: ProcureState, runtime: Any) -> dict:
    uid = state.get("user_id")
    if not uid or not runtime.store:
        return {}
    result = {}
    for key in ("brand_pref", "settings"):
        item = runtime.store.get((uid, "preferences"), key)
        if item:
            sk = f"user_{key}" if key == "brand_pref" else "user_settings"
            result[sk] = item.value
    return result


async def memory_save_node(state: ProcureState, runtime: Any) -> dict:
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
                p["time"] = datetime.now().isoformat(); break
        else:
            parts.append({"part_number": pn, "brand": parsed.get("brand", ""),
                          "time": datetime.now().isoformat()})
        runtime.store.put((uid, "preferences"), "part_history", parts[-100:])
    if parsed.get("brand"):
        pi = runtime.store.get((uid, "preferences"), "brand_pref")
        brands = set(pi.value) if pi else set()
        brands.add(parsed["brand"])
        runtime.store.put((uid, "preferences"), "brand_pref", sorted(brands))
    return {}


# ============================================================
# 构建图
# ============================================================
def build_supervised_graph(use_postgres: bool = False) -> StateGraph:
    workflow = StateGraph(ProcureState)
    workflow.add_node("memory_inject", memory_inject_node)
    workflow.add_node("supervisor", supervisor_node)
    for name in ["chat", "parse", "normalize", "alternatives", "match", "gen_rfq", "grade"]:
        workflow.add_node(name, globals()[f"{name}_agent"])
    workflow.add_node("memory_save", memory_save_node)

    workflow.add_edge(START, "memory_inject")
    workflow.add_edge("memory_inject", "supervisor")

    route_map = {a: a for a in ROUTING_ORDER} | {"FINISH": "memory_save"}
    workflow.add_conditional_edges("supervisor", lambda s: s.get("next_agent", "chat"), route_map)
    for a in ROUTING_ORDER:
        workflow.add_edge(a, "supervisor")
    workflow.add_edge("memory_save", END)

    if use_postgres and POSTGRESQL_URL:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            checkpointer = PostgresSaver.from_conn_string(POSTGRESQL_URL)
        except Exception:
            checkpointer = InMemorySaver()
    else:
        checkpointer = InMemorySaver()

    return workflow.compile(checkpointer=checkpointer, store=InMemoryStore())


def init_state(raw_query: str, user_id: str = "", thread_id: str | None = None) -> ProcureState:
    return ProcureState(
        thread_id=thread_id or uuid.uuid4().hex[:12],
        raw_query=raw_query, parsed_spec=None, normalized_spec=None,
        alternatives=[], matched_suppliers=[], rfq_doc=None, rfq_id=None,
        lead_grade=None, chat_response=None, errors=[], next_agent="chat",
        user_id=user_id or None,
        started_at=datetime.now().isoformat(), completed_at=None,
    )


# ============================================================
# SSE 流式执行
# ============================================================
async def run_procure_stream(
    raw_query: str = "", thread_id: str | None = None,
    confirmed_spec: dict | None = None, phase: str = "spec", user_id: str = "",
) -> AsyncGenerator[str, None]:
    if phase == "spec":
        state = init_state(raw_query, user_id, thread_id)
    else:
        state = init_state(raw_query, user_id, thread_id)
        if confirmed_spec:
            state["parsed_spec"] = state["normalized_spec"] = confirmed_spec

    agent_keys = set(ROUTING_ORDER)
    graph = build_supervised_graph()
    config = {"configurable": {"thread_id": state["thread_id"]}}
    trace = TraceLogger(state["thread_id"], phase)
    trace.begin(state.get("raw_query", ""))
    yield _sse("start", {"thread_id": state["thread_id"]})

    try:
        async for event in graph.astream(state, config, stream_mode="updates"):
            for node_name, node_output in event.items():
                if node_name in agent_keys:
                    yield _sse("progress", {"agent": node_name, "status": "done",
                                            "result": _result(state, node_output, node_name)})
                elif node_name == "supervisor" and node_output.get("next_agent") in agent_keys:
                    yield _sse("progress", {"agent": node_output["next_agent"], "status": "running"})
                if isinstance(node_output, dict):
                    state.update(node_output)
    except Exception as e:
        state.setdefault("errors", []).append(f"[graph] {str(e)}")

    trace.end(state)
    yield _sse("result", {
        "state": {k: state.get(k) for k in [
            "thread_id", "raw_query", "parsed_spec", "normalized_spec",
            "alternatives", "matched_suppliers", "rfq_doc", "rfq_id",
            "lead_grade", "chat_response", "errors",
        ]}
    })
    yield _sse("end", {})


def _result(bs: dict, no: dict, agent: str) -> Any:
    m = {"chat": "chat_response", "parse": "parsed_spec", "normalize": "normalized_spec",
         "alternatives": "alternatives", "match": "matched_suppliers",
         "gen_rfq": "rfq_doc", "grade": "lead_grade"}
    return no.get(m.get(agent, ""), bs.get(m.get(agent, "")))


def _sse(et: str, data: dict) -> str:
    return f"data: {json.dumps({'type': et, **data}, ensure_ascii=False)}\n\n"


_graph: StateGraph | None = None


def get_graph() -> StateGraph:
    global _graph
    if _graph is None:
        _graph = build_supervised_graph()
    return _graph