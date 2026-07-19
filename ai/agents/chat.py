"""
Agent 💬 - 聊天对话

当用户输入不是寻源需求（如打招呼、问功能、闲聊），
由 Supervisor 路由到本 Agent 直接回复。

使用轻量模型 qwen-plus，回复简洁专业。

#24 真流式: 用 astream 逐 token 产出 (而非 ainvoke 一次性)。
graph.py 通过 astream_events 捕获 on_chat_model_stream 事件逐 token 发 SSE。
"""

from __future__ import annotations

from ai.state import ProcureState
from ai import base_agent as agent_engine
from ai.monitor import AgentLogger

CHAT_SYSTEM_PROMPT = """你是 MatchForge 智配的 AI 助手，一个电子元器件采购寻源工具。

## 你能干什么
- 输入元器件型号或需求 -> 解析规格、推荐替代料、匹配供应商、生成询价单
- 例如: "TMK212BJ105KG-T 缺货找替代"、"0805 10uF X7R 50V MLCC"

## 回复风格
- 简洁专业，2-3 句话
- 如果是闲聊，友好回应并引导使用寻源功能
- 如果是寻源需求，引导用户到首页输入
- 不要编造元器件信息
"""


async def chat_agent(state: ProcureState) -> ProcureState:
    """
    聊天 Agent

    读取: state.raw_query
    写入: state.chat_response

    #24 真流式: 用 astream 逐 token 产出。graph.py 通过 astream_events
    捕获 on_chat_model_stream 事件, 实时发 SSE token 事件。
    """
    log = AgentLogger("chat", thread_id=state.get("thread_id", ""))
    raw_query = state.get("raw_query", "")
    log.start(state)

    try:
        llm = agent_engine.get_agent_llm(
            heavy=False, temperature=0.7, max_tokens=512, timeout=15,
            streaming=True,  # 启用流式, 供 graph.py astream_events 捕获
        )
        messages = [
            ("system", CHAT_SYSTEM_PROMPT),
            ("human", raw_query),
        ]
        # astream 逐 token 产出; graph.py 在 astream_events 中捕获 token 事件
        full_text = ""
        async for chunk in llm.astream(messages):
            if hasattr(chunk, "content") and chunk.content:
                full_text += chunk.content
        state["chat_response"] = full_text.strip() or "你好！我是 MatchForge AI 助手，有什么可以帮你的？"
        log.end(state)

    except Exception as e:
        state.setdefault("errors", []).append(f"[chat] {str(e)[:200]}")
        state["chat_response"] = "抱歉，我现在无法回复，请稍后再试。"
        log.fail(str(e)[:200])

    return state


# ecs_assistant 风格别名
process = chat_agent