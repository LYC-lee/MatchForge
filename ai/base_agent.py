"""
Agent 统一基类：LLM 工厂 + 可复用执行引擎。

本模块为 MatchForge 中所有 Agent 提供统一的基础设施，包括：
1. LLM 实例工厂函数 —— 按统一配置创建 ChatOpenAI 实例
2. run_tool_agent() —— 工具型 Agent 多轮 ReAct 流程（LLM 自主决策 → 工具执行 → 循环 → 最终回复）
3. run_direct_agent() —— 纯 LLM Agent 流程（无工具调用，直接生成回复）

使用方式：
    各业务 Agent 模块（如 parse、alternatives 等）通过调用 run_tool_agent()
    或 run_direct_agent() 并传入各自的 system_prompt 和 tools 列表来复用此流程。
"""

from __future__ import annotations

import json
import logging
from typing import Any, TYPE_CHECKING

from langchain_core.messages import SystemMessage, ToolMessage

if TYPE_CHECKING:
    # langchain_openai 会拉起 transformers (~25s); 延迟到工厂函数内首次调用再 import,
    # 避免 api.main 启动被阻塞 (QA 09:06 报后端启动慢即此因)。
    from langchain_openai import ChatOpenAI

from ai.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_MODEL_LIGHT
from ai.config import LLM_TEMPERATURE, LLM_MAX_TOKENS, LLM_TIMEOUT

logger = logging.getLogger(__name__)


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

    from langchain_openai import ChatOpenAI  # 延迟导入: 避免 api.main 启动加载 transformers

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


def get_supervisor_llm() -> "ChatOpenAI":
    """获取 Supervisor 专用的 LLM 实例 (委托给 ai.supervisor.get_supervisor_llm)。

    历史上本模块与 ai.supervisor 各有一份 get_supervisor_llm 定义, 参数漂移
    (本模块 max_tokens=64/timeout=10, supervisor max_tokens=1024/timeout=20)。
    现统一收敛为 ai.supervisor 中的单一实现 (参数更合理: glm-5.2 是推理模型,
    需要思考+输出预算), 此处仅保留薄委托以兼容旧的 `from ai.base_agent import
    get_supervisor_llm` 调用方。
    """
    # 延迟导入避免循环依赖
    from ai.supervisor import get_supervisor_llm as _impl
    return _impl()


async def run_tool_agent(
    state: dict,
    system_prompt: str,
    tools: list,
    user_id: str = "",
    max_tool_rounds: int = 5,
    heavy: bool = True,
    tool_call_sink=None,
) -> dict:
    """
    执行工具型 Agent 的多轮 ReAct 流程：LLM 自主决策 → 工具执行 → 循环 → 最终回复。

    这是工具型 Agent 体系的核心执行引擎。与旧版单轮不同，新版支持：
    - LLM 自主决定调用哪些工具、传入什么参数
    - 多轮工具调用：LLM 拿到工具结果后可继续调用其他工具
    - 最多 max_tool_rounds 轮，防止无限循环

    参数:
        state: 当前 Agent 状态字典，必须包含 "messages" 键。
        system_prompt: 系统提示词字符串，定义 Agent 的角色、能力边界。
        tools: LangChain BaseTool 实例列表。
        user_id: 当前用户的唯一标识。
        max_tool_rounds: 最大工具调用轮数，默认 5。
        heavy: 是否使用重模型。
        tool_call_sink: 可选回调 callable(tool_name, tool_args, output),
            每次工具执行成功后调用一次, 供调用方收集工具返回的事实集合
            (用于事后校验 LLM 输出是否幻觉)。默认 None, 行为不变。

    返回:
        dict: 状态更新字典，包含 "messages" 和 "next_agent"。
    """
    messages = state.get("messages", [])

    agent_messages = [
        SystemMessage(content=system_prompt),
        *messages[-10:],
    ]

    # 绑定工具的 LLM（用于决策轮）
    tool_llm = get_agent_llm(streaming=False, heavy=heavy).bind_tools(tools)
    # 纯 LLM（用于最终回复）
    final_llm = get_agent_llm(streaming=False, heavy=heavy)

    tool_map = {t.name: t for t in tools}

    for _round in range(max_tool_rounds):
        ai_msg = await tool_llm.ainvoke(agent_messages)

        if not ai_msg.tool_calls:
            # LLM 决定不再调用工具，直接返回回复
            return {"messages": [ai_msg], "next_agent": None}

        # 收集并执行本轮所有工具调用
        tool_results: list[ToolMessage] = []
        for tc in ai_msg.tool_calls:
            fn_name = tc["name"]
            fn_args = tc["args"]
            tool = tool_map.get(fn_name)

            if tool:
                try:
                    import asyncio
                    output = await asyncio.to_thread(tool.invoke, fn_args)
                    # 回传工具调用事实, 供调用方做幻觉校验
                    if tool_call_sink is not None:
                        try:
                            tool_call_sink(fn_name, fn_args, output)
                        except Exception:
                            logger.warning('tool_call_sink 回调异常, 已忽略', exc_info=True)
                except Exception as e:
                    output = f"工具执行出错: {e}"
                    logger.warning(f"Tool {fn_name} failed: {e}")
            else:
                output = f"未知工具: {fn_name}"

            tool_results.append(
                ToolMessage(content=str(output), tool_call_id=tc["id"])
            )

        # 将本轮决策 + 工具结果追加到对话历史
        agent_messages.extend([ai_msg, *tool_results])

    # 达到最大轮数仍要调用工具 → 强制生成最终回复
    final_msg = await final_llm.ainvoke([
        *agent_messages,
        SystemMessage(content="已超过最大工具调用轮数，请基于已有信息直接给出最终回复。"),
    ])
    return {"messages": [final_msg], "next_agent": None}


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


def parse_json_from_llm(content: str) -> Any:
    """
    从 LLM 的文本回复中提取 JSON。

    自动处理 markdown 代码块包裹、尾部逗号等常见格式问题。
    解析失败返回 None。
    """
    import re

    text = content.strip()
    # 去掉 markdown 代码块包裹
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试提取第一个 JSON 数组/对象
        m = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        return None