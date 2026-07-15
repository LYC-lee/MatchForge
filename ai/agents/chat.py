"""
Agent 💬 — 聊天对话

当用户输入不是寻源需求（如打招呼、问功能、闲聊），
由 Supervisor 路由到本 Agent 直接回复。

使用轻量模型 qwen-plus，回复简洁专业。
"""

from langchain_openai import ChatOpenAI
from ai.state import ProcureState
from ai.config import LLM_BASE_URL, DASHSCOPE_API_KEY, LLM_MODEL_LIGHT
from ai.monitor import AgentLogger

CHAT_SYSTEM_PROMPT = """你是 MatchForge 智配的 AI 助手，一个电子元器件采购寻源工具。

## 你能干什么
- 输入元器件型号或需求 → 解析规格、推荐替代料、匹配供应商、生成询价单
- 例如: "TMK212BJ105KG-T 缺货找替代"、"0805 10uF X7R 50V MLCC"

## 回复风格
- 简洁专业，2-3 句话
- 如果是闲聊，友好回应并引导使用寻源功能
- 如果是寻源需求，引导用户到首页输入
- 不要编造元器件信息
"""


_llm: ChatOpenAI | None = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            base_url=LLM_BASE_URL,
            api_key=DASHSCOPE_API_KEY,
            model=LLM_MODEL_LIGHT,
            temperature=0.7,
            max_tokens=512,
            timeout=15,
        )
    return _llm


async def chat_agent(state: ProcureState) -> ProcureState:
    """
    聊天 Agent

    读取: state.raw_query
    写入: state.chat_response
    """
    log = AgentLogger("chat", thread_id=state.get("thread_id", ""))
    raw_query = state.get("raw_query", "")
    log.start(state)

    try:
        llm = _get_llm()
        messages = [
            ("system", CHAT_SYSTEM_PROMPT),
            ("human", raw_query),
        ]
        resp = await llm.ainvoke(messages)
        state["chat_response"] = resp.content.strip()
        log.end(state)

    except Exception as e:
        state.setdefault("errors", []).append(f"[chat] {str(e)[:200]}")
        state["chat_response"] = "抱歉，我现在无法回复，请稍后再试。"
        log.fail(str(e)[:200])

    return state