"""
Supervisor + LangGraph 图编排

架构: Supervisor Agent (LLM) → 控制子 Agent → 结果回 Supervisor → 循环直到完成

原理:
  1. Supervisor 是一个 LLM-powered Agent，知道完整工作流 (6 步骤)
  2. 每个子 Agent 是图中的一个节点
  3. Supervisor 检查当前 State，决定调用哪个子 Agent
  4. 子 Agent 执行完毕后回到 Supervisor
  5. 重复直到所有步骤完成 → FINISH

工作流:
  supervisor → parse → supervisor → normalize → supervisor
    → alternatives → supervisor → match → supervisor
    → gen_rfq → supervisor → grade → supervisor → END

SSE 格式 (与前端 api/sse.ts 对齐):
  data: {"type":"start","thread_id":"xxx"}\n\n
  data: {"type":"progress","agent":"parse","status":"running"}\n\n
  data: {"type":"progress","agent":"parse","status":"done","result":{...}}\n\n
  data: {"type":"result","state":{...}}\n\n
  data: {"type":"end"}\n\n

两阶段:
  phase=spec:  supervisor → parse → normalize → END
  phase=match: supervisor → alternatives → match → gen_rfq → grade → END
"""

import uuid
import json
from datetime import datetime
from typing import AsyncGenerator, Optional

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver

from ai.state import ProcureState
from ai.config import LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS, LLM_TIMEOUT
from ai.monitor import TraceLogger, AgentLogger
from ai.memory import inject_user_memory, save_search_to_memory, save_part_to_memory, AgentMemory, ensure_table
from ai.agents.parse import parse_agent
from ai.agents.normalize import normalize_agent
from ai.agents.alternatives import alternatives_agent
from ai.agents.match import match_agent
from ai.agents.gen_rfq import gen_rfq_agent
from ai.agents.grade import grade_agent

# Agent 元信息 — Supervisor 的 Prompt 用
AGENT_META: dict[str, dict] = {
    "parse": {
        "name": "需求解析",
        "description": "将用户自然语言输入解析为结构化元器件规格字段",
        "input": "raw_query (用户原始需求)",
        "output": "parsed_spec (结构化规格，如 category/package/capacitance/temp_coeff/rated_voltage)",
    },
    "normalize": {
        "name": "标准化",
        "description": "将用户规格映射到标准字典编码",
        "input": "parsed_spec",
        "output": "normalized_spec (补充 std_code，字段名统一为英文)",
    },
    "alternatives": {
        "name": "替代料推荐",
        "description": "查找有依据的替代型号，输出5级分类和参数差异",
        "input": "normalized_spec (含 part_number)",
        "output": "alternatives[] (替代列表，含 level/confidence/diff_items)",
    },
    "match": {
        "name": "供应商匹配",
        "description": "匹配经营该品类的候选供应商",
        "input": "normalized_spec + alternatives",
        "output": "matched_suppliers[] (含匹配度/资质/品牌覆盖)",
    },
    "gen_rfq": {
        "name": "询价单生成",
        "description": "生成可编辑的结构化询价单",
        "input": "parsed_spec + alternatives + matched_suppliers",
        "output": "rfq_doc (询价单文本) + rfq_id",
    },
    "grade": {
        "name": "线索分级",
        "description": "根据商务字段评分，输出 A/B/C/D 线索级别",
        "input": "parsed_spec (含月用量、交期、品牌偏好)",
        "output": "lead_grade {grade, score, reasons}",
    },
}

# ============================================================
# Supervisor LLM 路由
# 主 Agent 用 LLM 决定调用哪个子 Agent
# ============================================================
SUPERVISOR_SYSTEM_PROMPT = """你是电子元器件寻源系统的主调度 Agent。你的工作是分析当前任务进度，决定下一步调用哪个子 Agent。

## 可用子 Agent

{agent_meta}

## 当前 State

- raw_query: {raw_query}
- parsed_spec: {parsed_spec_status}  (已结构化规格)
- normalized_spec: {normalized_spec_status}  (已标准化)
- alternatives: {alternatives_status}  (替代料)
- matched_suppliers: {suppliers_status}  (匹配供应商)
- rfq_doc: {rfq_doc_status}  (询价单)
- lead_grade: {grade_status}  (线索分级)
- errors: {errors_status}

## 规则
1. 必须按 parse → normalize → alternatives → match → gen_rfq → grade 顺序执行
2. 只有前面的 Agent 完成后才能调用后面的
3. 如果某个 Agent 失败，记录到 errors，允许跳过它继续
4. 所有 Agent 都已完成 → 输出 FINISH

## 输出格式
只能输出以下之一（纯文本，不要 JSON）：
- parse
- normalize
- alternatives
- match
- gen_rfq
- grade
- FINISH
"""


# 安全兜底 — LLM 失效时的确定性路由
ROUTING_ORDER = ["parse", "normalize", "alternatives", "match", "gen_rfq", "grade"]


def _check_agent_done(state: ProcureState, agent: str) -> bool:
    """检查某个 Agent 是否已完成"""
    checks = {
        "parse": state.get("parsed_spec") is not None,
        "normalize": state.get("normalized_spec") is not None,
        "alternatives": len(state.get("alternatives", [])) > 0,
        "match": len(state.get("matched_suppliers", [])) > 0,
        "gen_rfq": state.get("rfq_doc") is not None,
        "grade": state.get("lead_grade") is not None,
    }
    return checks.get(agent, False)


def _decide_next_agent_fallback(state: ProcureState) -> str:
    """确定性兜底：找到第一个未完成的 Agent"""
    for agent in ROUTING_ORDER:
        if not _check_agent_done(state, agent):
            return agent
    return "FINISH"


def _build_supervisor_prompt(state: ProcureState) -> tuple[str, str]:
    """构建 Supervisor Prompt"""
    agent_lines = "\n".join(
        f"- {key}: {meta['name']} — {meta['description']}"
        f"  输入: {meta['input']}  输出: {meta['output']}"
        for key, meta in AGENT_META.items()
    )

    def status(val, done_text="✅ 已完成", empty_text="⏳ 待处理"):
        return done_text if val is not None and val != [] and val != "" else empty_text

    errors_text = str(state.get("errors", [])) if state.get("errors") else "无"

    prompt = SUPERVISOR_SYSTEM_PROMPT.format(
        agent_meta=agent_lines,
        raw_query=state.get("raw_query", "")[:100],
        parsed_spec_status=status(state.get("parsed_spec")),
        normalized_spec_status=status(state.get("normalized_spec")),
        alternatives_status=status(
            len(state.get("alternatives", [])) > 0,
            f"✅ 已找到 {len(state.get('alternatives', []))} 个",
            "⏳ 待处理",
        ),
        suppliers_status=status(
            len(state.get("matched_suppliers", [])) > 0,
            f"✅ 已匹配 {len(state.get('matched_suppliers', []))} 家",
            "⏳ 待处理",
        ),
        rfq_doc_status=status(state.get("rfq_doc")),
        grade_status=status(state.get("lead_grade")),
        errors_status=errors_text,
    )

    return ("system", prompt)


# ============================================================
# Supervisor 主节点 — LLM 控制
# ============================================================
_supervisor_llm = None


def _get_supervisor_llm():
    global _supervisor_llm
    if _supervisor_llm is None:
        from langchain_openai import ChatOpenAI
        from ai.config import LLM_BASE_URL, DASHSCOPE_API_KEY
        _supervisor_llm = ChatOpenAI(
            base_url=LLM_BASE_URL,
            api_key=DASHSCOPE_API_KEY,
            model=LLM_MODEL,
            temperature=0,
            max_tokens=64,
            timeout=10,
        )
    return _supervisor_llm


async def supervisor_node(state: ProcureState) -> dict:
    """
    Supervisor Agent — LLM 驱动的编排决策中心

    流程:
      1. 调用 LLM 分析当前 State，决定下一步调用哪个子 Agent
      2. LLM 失败时降级到确定性兜底
      3. 写入 state["next_agent"]
    """
    log = AgentLogger("supervisor", thread_id=state.get("thread_id", ""))
    log.start(state)
    next_agent = "FINISH"

    try:
        _, prompt_text = _build_supervisor_prompt(state)
        llm = _get_supervisor_llm()
        messages = [
            ("system", prompt_text),
            ("human", "当前任务进度如上，下一步调用哪个 Agent？"),
        ]
        response = await llm.ainvoke(messages)
        decision = response.content.strip().upper().replace(".", "").strip()

        valid_agents = {"PARSE", "NORMALIZE", "ALTERNATIVES", "MATCH", "GEN_RFQ", "GRADE", "FINISH"}
        if decision in valid_agents:
            next_agent = decision.lower() if decision != "FINISH" else "FINISH"
        else:
            next_agent = _decide_next_agent_fallback(state)

    except Exception:
        next_agent = _decide_next_agent_fallback(state)

    log.end(state)
    return {"next_agent": next_agent}


# ============================================================
# LangGraph 图构建
# ============================================================
def build_supervised_graph() -> StateGraph:
    """
    构建 Supervisor 编排图

    图结构:
      supervisor ──conditional──→ parse/normalize/.../FINISH
          ▲                            │
          └──────── all agents ─────────┘
          (每个子 Agent 执行完回到 supervisor)

    优势:
      - 所有路由决策集中在 supervisor_node
      - 新增/删除 Agent 只需改 ROUTING_ORDER + AGENT_META
      - 错误隔离: 每个子 Agent 独立 try/except
    """
    workflow = StateGraph(ProcureState)

    # 添加所有节点
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("parse", parse_agent)
    workflow.add_node("normalize", normalize_agent)
    workflow.add_node("alternatives", alternatives_agent)
    workflow.add_node("match", match_agent)
    workflow.add_node("gen_rfq", gen_rfq_agent)
    workflow.add_node("grade", grade_agent)

    # Supervisor → 路由到子 Agent (或结束)
    workflow.add_conditional_edges(
        "supervisor",
        lambda s: s.get("next_agent", "parse"),
        {
            "parse": "parse",
            "normalize": "normalize",
            "alternatives": "alternatives",
            "match": "match",
            "gen_rfq": "gen_rfq",
            "grade": "grade",
            "FINISH": END,
        },
    )

    # 所有子 Agent 执行完毕后回到 Supervisor
    for agent in ["parse", "normalize", "alternatives", "match", "gen_rfq", "grade"]:
        workflow.add_edge(agent, "supervisor")

    # 入口
    workflow.set_entry_point("supervisor")

    checkpointer = InMemorySaver()
    return workflow.compile(checkpointer=checkpointer)


# ============================================================
# State 初始化
# ============================================================
def init_state(
    raw_query: str,
    thread_id: str | None = None,
) -> ProcureState:
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


# ============================================================
# SSE 流式执行
# ============================================================
async def run_procure_stream(
    raw_query: str = "",
    thread_id: str | None = None,
    confirmed_spec: dict | None = None,
    phase: str = "spec",
) -> AsyncGenerator[str, None]:
    """
    执行寻源流程，SSE 流式推送

    原理:
      初始化 State → 运行 LangGraph 图 (supervisor 循环路由) → SSE 推送结果

    参数:
      raw_query: 用户原始需求 (phase=spec 时必填)
      thread_id: 会话 ID
      confirmed_spec: 用户确认后的规格 (phase=match 时必填)
      phase: "spec" (第一阶段 parse+normalize) 或 "match" (第二阶段 alternatives+match+gen_rfq+grade)
    """
    # 根据阶段确定运行的 Agent
    if phase == "spec":
        agent_keys = ["parse", "normalize"]
        state = init_state(raw_query, thread_id)
    else:
        agent_keys = ["alternatives", "match", "gen_rfq", "grade"]
        state = _load_or_init_state(raw_query, thread_id, confirmed_spec)

    # ---- 注入用户长期记忆 ----
    state = await inject_user_memory(state)

    app = build_supervised_graph()
    config_key = f"{state['thread_id']}_{phase}"
    config = {"configurable": {"thread_id": config_key}}

    # 追踪日志
    trace = TraceLogger(state["thread_id"], phase)
    trace.begin(state.get("raw_query", ""))

    # SSE: start
    yield _sse("start", {
        "thread_id": state["thread_id"],
        "rfq_id": state.get("rfq_id"),
    })

    # ---- 逐 Agent 执行 ----
    for agent_key in agent_keys:
        yield _sse("progress", {"agent": agent_key, "status": "running"})

        try:
            state = await _agent_fn(agent_key)(state)
            state["next_agent"] = _decide_next_agent_fallback(state)

            yield _sse("progress", {
                "agent": agent_key,
                "status": "done",
                "result": _get_result(state, agent_key),
            })

        except Exception as e:
            state["errors"].append(f"[{agent_key}] {str(e)}")
            yield _sse("error", {"agent": agent_key, "message": str(e)[:200]})

    state["completed_at"] = datetime.now().isoformat()

    # ---- 保存到用户记忆 ----
    user_id = state.get("user_id")
    if user_id and phase == "spec":
        parsed = state.get("parsed_spec") or {}
        await save_search_to_memory(user_id, parsed.get("part_number", ""), state.get("raw_query", ""))
        if parsed.get("part_number"):
            await save_part_to_memory(user_id, parsed.get("part_number", ""),
                                      parsed.get("brand", ""), "parse")

    # 结束追踪
    trace.end(state)

    # SSE: result
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


def _agent_fn(agent_key: str):
    """获取子 Agent 的调用函数"""
    mapping = {
        "parse": parse_agent,
        "normalize": normalize_agent,
        "alternatives": alternatives_agent,
        "match": match_agent,
        "gen_rfq": gen_rfq_agent,
        "grade": grade_agent,
    }
    return mapping[agent_key]


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


def _sse(event_type: str, data: dict) -> str:
    """格式化 SSE 事件"""
    payload = {"type": event_type, **data}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


# ============================================================
# 全局图实例
# ============================================================
_graph: StateGraph | None = None


def get_graph() -> StateGraph:
    global _graph
    if _graph is None:
        _graph = build_supervised_graph()
    return _graph


# 启动时确保 memory 表存在（不阻塞应用）
try:
    ensure_table()
except Exception:
    pass