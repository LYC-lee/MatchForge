"""
Agent 统一基类：LLM 工厂 + 可复用执行引擎。

本模块为 MatchForge 中所有 Agent 提供统一的基础设施，包括：
1. LLM 实例工厂函数 —— 按统一配置创建 ChatOpenAI 实例
2. run_tool_agent() —— 工具型 Agent 标准 ReAct 流程（LLM 决策 → 工具执行 → 最终回复）
3. run_direct_agent() —— 纯 LLM Agent 流程（无工具调用，直接生成回复）

使用方式：
    各业务 Agent 模块（如 parse、alternatives 等）通过调用 run_tool_agent()
    或 run_direct_agent() 并传入各自的 system_prompt 和 tools 列表来复用此流程。
"""

from __future__ import annotations

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from ai.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_MODEL_LIGHT
from ai.config import LLM_TEMPERATURE, LLM_MAX_TOKENS, LLM_TIMEOUT


def get_agent_llm(
    streaming: bool = False,
    heavy: bool = True,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout: int | None = None,
) -> ChatOpenAI:
    """
    创建并返回一个配置好的 ChatOpenAI 实例，作为 Agent 的"大脑"。

    所有 Agent 共享同一套 LLM 配置（模型名、API 地址、超时等），
    通过此工厂函数统一管理，避免各模块分散创建导致配置不一致。

    参数:
        streaming: 是否启用流式输出。
                   - True:  LLM 以 SSE 方式逐 token 返回
                   - False: 一次性返回完整响应（默认）
        heavy: True 使用 LLM_MODEL（高推理），False 使用 LLM_MODEL_LIGHT（轻量）
        temperature: 采样温度，None 则从配置读取 LLM_TEMPERATURE
        max_tokens: 最大输出 token 数，None 则从配置读取 LLM_MAX_TOKENS
        timeout: 请求超时秒数，None 则从配置读取 LLM_TIMEOUT

    返回:
        ChatOpenAI: 配置完成的 LangChain ChatOpenAI 实例
    """
    model = LLM_MODEL if heavy else LLM_MODEL_LIGHT

    if temperature is None:
        temperature = LLM_TEMPERATURE if heavy else 0.7
    if max_tokens is None:
        max_tokens = LLM_MAX_TOKENS if heavy else 512
    if timeout is None:
        timeout = LLM_TIMEOUT

    return ChatOpenAI(
        model=model,
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=streaming,
        timeout=timeout,
        max_retries=2,
    )


def get_supervisor_llm() -> ChatOpenAI:
    """
    获取 Supervisor 专用的 LLM 实例。

    使用轻量快速模型（SUPERVISOR_MODEL），temperature 设为 0 保证路由稳定性，
    短超时 + 2 次重试应对网络抖动。
    """
    from ai.config import SUPERVISOR_MODEL

    return ChatOpenAI(
        model=SUPERVISOR_MODEL,
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
        temperature=0,
        max_tokens=64,
        timeout=10,
        max_retries=2,
    )


async def run_tool_agent(
    state: dict,
    system_prompt: str,
    tools: list,
    user_id: str = "",
) -> dict:
    """
    执行工具型 Agent 的标准 ReAct 流程：LLM 决策 → 工具执行 → 生成最终回复。

    这是工具型 Agent 体系的核心执行引擎。它实现了一个简化但完整的 ReAct 循环：
    1. 将系统提示词 + 最近对话历史组装为消息列表
    2. 让 LLM（绑定工具后）分析消息并决定：直接回复文本，还是调用工具
    3. 如果 LLM 决定调用工具，执行工具并收集结果，再次调用 LLM 生成最终回复
    4. 如果 LLM 直接回复文本，则跳过工具执行步骤

    参数:
        state: 当前 Agent 状态字典，必须包含 "messages" 键。
        system_prompt: 系统提示词字符串，定义 Agent 的角色、能力边界。
        tools: LangChain BaseTool 实例列表。
        user_id: 当前用户的唯一标识。

    返回:
        dict: 状态更新字典，包含 "messages" 和 "next_agent"。
    """
    messages = state.get("messages", [])

    agent_messages = [
        SystemMessage(content=system_prompt),
        *messages[-10:],
    ]

    # 第一阶段：LLM 决策（绑定工具）
    llm = get_agent_llm(streaming=False).bind_tools(tools)
    ai_msg = await llm.ainvoke(agent_messages)

    if ai_msg.tool_calls:
        # 构建工具名称 → 工具实例的映射表
        tool_map = {t.name: t for t in tools}

        from langchain_core.messages import ToolMessage

        tool_results = []

        for tc in ai_msg.tool_calls:
            fn_name = tc["name"]
            fn_args = tc["args"]
            tool = tool_map.get(fn_name)

            if tool:
                try:
                    import asyncio
                    output = await asyncio.to_thread(tool.invoke, fn_args)
                except Exception as e:
                    output = f"工具执行出错: {e}"
            else:
                output = f"未知工具: {fn_name}"

            tool_results.append(
                ToolMessage(
                    content=str(output),
                    tool_call_id=tc["id"],
                )
            )

        # 第二阶段：基于工具结果生成最终回复
        agent_messages.extend([ai_msg, *tool_results])
        final_llm = get_agent_llm(streaming=False)
        response = await final_llm.ainvoke(agent_messages)
    else:
        response = ai_msg

    return {"messages": [response], "next_agent": None}


async def run_direct_agent(
    state: dict,
    system_prompt: str,
    heavy: bool = False,
    temperature: float | None = None,
    max_tokens: int | None = None,
    history_limit: int = 10,
) -> dict:
    """
    执行纯 LLM Agent（无工具调用），直接生成回复。

    适用于不需要工具调用的 Agent（如闲聊、纯推理等）。

    参数:
        state: 当前 Agent 状态字典。
        system_prompt: 系统提示词。
        heavy: 是否使用重模型。
        temperature: 采样温度。
        max_tokens: 最大输出 token。
        history_limit: 保留的历史消息条数。

    返回:
        dict: 状态更新字典。
    """
    messages = state.get("messages", [])

    agent_messages = [
        SystemMessage(content=system_prompt),
        *messages[-history_limit:],
    ]

    llm = get_agent_llm(
        streaming=False,
        heavy=heavy,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    response = await llm.ainvoke(agent_messages)

    return {"messages": [response], "next_agent": None}