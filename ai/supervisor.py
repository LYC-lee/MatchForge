"""
Supervisor 路由 Agent：意图分类与子 Agent 调度。

工作流程
--------
1. 接收用户消息列表，调用轻量 LLM 进行意图分类
2. 优先使用 structured output（JSON mode）直接解析路由决策
3. 解析失败时逐级降级：正则兜底 → 最终走顺序 fallback

架构:
  chat → 闲聊/问候 → 直接回复
  parse → normalize → alternatives → match → gen_rfq → grade → FINISH
"""

from __future__ import annotations

import json
import logging
import re
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from ai.config import LLM_API_KEY, LLM_BASE_URL, SUPERVISOR_MODEL

logger = logging.getLogger(__name__)

# ── Agent 元数据 ────────────────────────────────────────────────────────
AGENT_META: dict[str, dict] = {
    "chat": {
        "name": "💬 聊天对话",
        "description": "回复用户的闲聊、问候、功能介绍等非寻源问题",
        "input": "raw_query",
        "output": "chat_response",
    },
    "parse": {
        "name": "需求解析",
        "description": "将用户自然语言输入解析为结构化元器件规格字段",
        "input": "raw_query",
        "output": "parsed_spec",
    },
    "normalize": {
        "name": "标准化",
        "description": "将用户规格映射到标准字典编码",
        "input": "parsed_spec",
        "output": "normalized_spec",
    },
    "alternatives": {
        "name": "替代料推荐",
        "description": "查找有依据的替代型号，输出5级分类和参数差异",
        "input": "normalized_spec",
        "output": "alternatives[]",
    },
    "match": {
        "name": "供应商匹配",
        "description": "匹配经营该品类的候选供应商",
        "input": "normalized_spec + alternatives",
        "output": "matched_suppliers[]",
    },
    "gen_rfq": {
        "name": "询价单生成",
        "description": "生成可编辑的结构化询价单",
        "input": "parsed_spec + alternatives + matched_suppliers",
        "output": "rfq_doc",
    },
    "grade": {
        "name": "线索分级",
        "description": "根据商务字段评分，输出 A/B/C/D",
        "input": "parsed_spec",
        "output": "lead_grade",
    },
}

# 合法的 Agent 名称列表（供 RouteDecision 使用）
ROUTING_ORDER: list[str] = ["chat", "parse", "normalize", "alternatives", "match", "rag_enrich", "gen_rfq", "grade"]

# ── Supervisor 系统提示词 ─────────────────────────────────────────────
SYSTEM_PROMPT = """你是电子元器件寻源系统的主调度 Agent。

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

请输出如下 JSON 格式（不要加 markdown 代码块标记）：
{{"agent": "<Agent名称 或 FINISH>", "reason": "<路由理由>"}}"""


# ── 路由决策数据模型 ─────────────────────────────────────────────────
class RouteDecision(BaseModel):
    """LLM 结构化输出的路由决策，agent 字段限定了合法的 Agent 名称枚举。"""

    agent: Literal["chat", "parse", "normalize", "alternatives", "match", "gen_rfq", "grade", "FINISH"] = Field(
        description="路由到的 Agent 名称，或 FINISH 表示全部完成"
    )
    reason: str = Field(default="", description="路由理由，便于调试和日志追踪")


# ── LLM 实例工厂 ──────────────────────────────────────────────────────
def get_supervisor_llm() -> ChatOpenAI:
    """获取 Supervisor 专用的 LLM 实例。

    使用轻量快速模型（SUPERVISOR_MODEL），temperature 设为 0 保证路由稳定性，
    超时 10s + 2 次重试应对网络抖动。

    注意: glm-5.2 是推理模型，先在 reasoning_content 思考、再在 content 输出最终
    JSON。max_tokens 必须给足“思考+输出”预算，否则 token 耗尽时 content 为空、
    finish_reason=length，json_mode 与正则兜底双双失败 -> 分类器形同不可用。
    """
    return ChatOpenAI(
        model=SUPERVISOR_MODEL,
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
        temperature=0,
        max_tokens=1024,
        timeout=20,
        max_retries=2,
    )


def get_supervisor_chain():
    """创建带结构化输出的 Supervisor 路由链。

    使用 json_mode 让 LLM 直接输出符合 RouteDecision schema 的 JSON，
    省去手动解析步骤，提高成功率。
    """
    llm = get_supervisor_llm()
    return llm.with_structured_output(RouteDecision, method="json_mode")


# ── 状态检查辅助 ──────────────────────────────────────────────────────
def _check_done(state: dict, agent: str) -> bool:
    """检查指定 Agent 是否已完成（已执行过即算完成，不要求非空结果）。"""
    attempted = state.get("_attempted_agents", [])
    return agent in attempted


def _build_supervisor_prompt(state: dict) -> str:
    """根据当前 state 构建 Supervisor 提示词。"""
    agent_lines = "\n".join(
        f"- {k}: {m['name']} — {m['description']}  输入: {m['input']}  输出: {m['output']}"
        for k, m in AGENT_META.items()
    )

    def s(val, done="✅ 已完成", empty="⏳ 待处理"):
        return done if val is not None and val != [] and val != "" else empty

    brands = state.get("user_brand_pref", [])
    brand_line = f"该用户常用品牌: {brands}" if brands else "暂无长期记忆"

    return SYSTEM_PROMPT.format(
        agent_meta=agent_lines,
        raw_query=str(state.get("raw_query", ""))[:100],
        parsed_spec_status=s(state.get("parsed_spec")),
        normalized_spec_status=s(state.get("normalized_spec")),
        alternatives_status=s(
            len(state.get("alternatives", [])) > 0,
            f"✅ 已找到 {len(state.get('alternatives', []))} 个",
        ),
        suppliers_status=s(
            len(state.get("matched_suppliers", [])) > 0,
            f"✅ 已匹配 {len(state.get('matched_suppliers', []))} 家",
        ),
        rfq_doc_status=s(state.get("rfq_doc")),
        grade_status=s(state.get("lead_grade")),
        errors_status=str(state.get("errors", [])) if state.get("errors") else "无",
        brand_memory=brand_line,
    )


# ── 兜底解析 ──────────────────────────────────────────────────────────
def _fallback_extract(text: str) -> str | None:
    """当结构化输出失败时，从 LLM 原始文本中提取 Agent 名称。

    按优先级依次尝试：
    1. 解析 JSON 中的 agent / assistant 字段
    2. 正则匹配 "agent": "xxx"
    3. 在文本中搜索已知 Agent 名称关键词
    4. 遍历 JSON 所有值，匹配第一个合法 Agent 名

    返回 None 表示所有方式均失败，调用方应走最终兜底。
    """
    text = text.strip()

    # 清理可能的 markdown 代码块包裹 ```json ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # ── 尝试 JSON 解析 ──
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None

    if data is None:
        # JSON 解析失败 → 正则兜底
        m = re.search(r'"agent"\s*:\s*"(\w+)"', text)
        if m:
            return m.group(1).upper()
        # 容错：有些 LLM 会用 assistant 代替 agent
        m = re.search(r'"assistant"\s*:\s*"(\w+)"', text)
        if m:
            return m.group(1).upper()
        # 最后手段：在文本中搜索已知 Agent 名称
        for name in ROUTING_ORDER:
            if name in text.lower():
                return name
        return None

    # JSON 解析成功 → 按优先级提取字段
    if "agent" in data:
        val = str(data["agent"]).upper()
        return val
    if "assistant" in data:
        val = str(data["assistant"]).upper()
        return val
    # 遍历所有值，匹配第一个合法的 Agent 名称
    for v in data.values():
        if isinstance(v, str) and (v.lower() in ROUTING_ORDER or v.upper() == "FINISH"):
            return v.upper()
    return None


def _ordered_fallback(state: dict) -> str:
    """按顺序返回第一个未完成的 Agent（最终兜底）。

    注意: phase="match" 时 parsed_spec/normalized_spec 已由外部注入，
    但 _attempted_agents 可能不含 parse/normalize。此时尝试走 alternatives。
    """
    attempted = state.get("_attempted_agents", [])

    # 如果 parse/normalize 未执行但 spec 已有值，说明外部注入的 → 跳至 alternatives
    has_spec = bool(state.get("parsed_spec")) and bool(state.get("normalized_spec"))
    if has_spec and "parse" not in attempted and "normalize" not in attempted:
        for a in ("alternatives", "match", "gen_rfq", "grade", "rag_enrich"):
            if a not in attempted:
                return a
        return "FINISH"

    for a in ROUTING_ORDER:
        if a not in attempted:
            return a
    return "FINISH"


# ── 路由入口 ──────────────────────────────────────────────────────────
async def route(state: dict) -> dict:
    """意图分类节点 — LangGraph 图中的路由函数。

    三级降级策略：
    1. 结构化输出（json_mode）→ 直接拿到 RouteDecision
    2. 结构化失败 → 普通 LLM 调用 + 正则兜底解析
    3. 兜底也失败 → 按顺序 fallback，保证系统不中断

    如果外部通过 next_agent 指定了非 "chat" 的路由目标，直接采纳不走 LLM
    （用于 phase="match" 时跳过 parse/normalize）。
    Parameters
    ----------
    state : dict
        LangGraph 状态，必须包含 "raw_query" 等业务字段。

    Returns
    -------
    dict
        {"next_agent": str, "route_reason": str}，供下游节点使用。
    """
    # ── 第 0 级：外部显式路由（跳过 LLM 决策）──
    forced = str(state.get("next_agent", "chat"))
    if forced not in ("chat", "FINISH") and forced in ROUTING_ORDER:
        attempted = state.get("_attempted_agents", [])
        if forced not in attempted:
            logger.info("Supervisor 采纳外部路由: %s", forced)
            return {"next_agent": forced, "route_reason": "外部显式路由（跳过 parse/normalize）"}

    # ── 第 0.5 级：spec 阶段 normalize 完成后直接 FINISH（避免绕过 gating）──
    if state.get("_phase") == "spec":
        attempted = state.get("_attempted_agents", [])
        if "normalize" in attempted:
            logger.info("Supervisor spec 阶段 normalize 已完成 -> FINISH")
            return {"next_agent": "FINISH", "route_reason": "spec 阶段 normalize 已完成"}

    # ── 第 0.6 级：顺序路由模式（phase="match" 时使用，避免 LLM 误决策）──
    if state.get("_use_ordered_fallback"):
        agent = _ordered_fallback(state)
        logger.info("Supervisor 顺序路由: %s", agent)
        return {"next_agent": agent, "route_reason": "顺序路由（_use_ordered_fallback 模式）"}

    chain = get_supervisor_chain()
    prompt = _build_supervisor_prompt(state)

    try:
        decision = await chain.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content=f"用户输入: \"{str(state.get('raw_query', ''))[:100]}\"\n下一步调用哪个 Agent？"),
        ])
        agent = decision.agent.lower() if decision.agent != "FINISH" else "FINISH"
        logger.info("Supervisor 结构化路由: %s → %s", decision.reason, agent)
        return {"next_agent": agent, "route_reason": decision.reason}
    except Exception as e:
        logger.warning("Supervisor 结构化解析失败: %s，尝试兜底...", e)

    # ── 第 2 级：原始文本 + 正则兜底 ──
    llm = get_supervisor_llm()
    try:
        raw = await llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content=f"用户输入: \"{str(state.get('raw_query', ''))[:100]}\"\n下一步调用哪个 Agent？"),
        ])
        text = raw.content
        agent_name = _fallback_extract(text)
        if agent_name and agent_name.lower() in [*ROUTING_ORDER, "FINISH"]:
            agent = agent_name.lower() if agent_name != "FINISH" else "FINISH"
            logger.info("Supervisor 兜底成功: %s → %s", text[:100], agent)
            return {"next_agent": agent, "route_reason": f"兜底解析: {text[:100]}"}
    except Exception as e2:
        logger.error("Supervisor 兜底也失败: %s", e2)

    # ── 第 3 级：最终兜底，确保系统不中断 ──
    fallback = _ordered_fallback(state)
    logger.warning("Supervisor 所有解析尝试失败，顺序 fallback → %s", fallback)
    return {"next_agent": fallback, "route_reason": "路由解析失败，走顺序兜底"}
