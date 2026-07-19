"""
测试 Agent 💬 - 聊天对话

#24: chat agent 改用 astream 逐 token 产出 (streaming=True)。
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from ai.agents.chat import chat_agent


def _mock_astream_llm(content: str):
    """构造 astream 的 mock: yield 多个 chunk 拼成 content。"""
    mock_llm = MagicMock()
    # 把 content 切成 3 段模拟流式 chunk
    chunks = [content[i:i + 3] for i in range(0, len(content), 3)] or [content]

    async def _astream(messages):
        for c in chunks:
            m = MagicMock()
            m.content = c
            yield m

    mock_llm.astream = _astream
    return mock_llm


@pytest.mark.asyncio
async def test_chat_agent_normal_reply(sample_state):
    """正常聊天：返回欢迎回复 (astream 流式)"""
    mock_llm = _mock_astream_llm("您好！我是 MatchForge 智配助手，请告诉我您需要什么帮助。")

    with patch("ai.base_agent.get_agent_llm", return_value=mock_llm) as mock_get:
        sample_state["raw_query"] = "你好"
        result = await chat_agent(sample_state)

    assert result["chat_response"] is not None
    assert "MatchForge" in result["chat_response"] or "您好" in result["chat_response"]
    assert len(result.get("errors", [])) == 0
    # #24: streaming=True 参数
    mock_get.assert_called_once_with(
        heavy=False, temperature=0.7, max_tokens=512, timeout=15, streaming=True)


@pytest.mark.asyncio
async def test_chat_agent_greeting(sample_state):
    """问候语：返回友好回应"""
    mock_llm = _mock_astream_llm("嗨！有什么可以帮您的吗？")

    with patch("ai.base_agent.get_agent_llm", return_value=mock_llm):
        sample_state["raw_query"] = "在吗"
        result = await chat_agent(sample_state)

    assert result["chat_response"] is not None
    assert len(result.get("errors", [])) == 0


@pytest.mark.asyncio
async def test_chat_agent_function_intro(sample_state):
    """功能介绍：引导使用寻源功能"""
    mock_llm = _mock_astream_llm("我可以帮您查找元器件替代料、匹配供应商。您可以输入型号试试！")

    with patch("ai.base_agent.get_agent_llm", return_value=mock_llm):
        sample_state["raw_query"] = "你能做什么"
        result = await chat_agent(sample_state)

    assert result["chat_response"] is not None
    assert len(result.get("errors", [])) == 0


@pytest.mark.asyncio
async def test_chat_agent_llm_error(sample_state):
    """LLM 异常：返回兜底消息 + 记录 error"""
    mock_llm = MagicMock()

    async def _astream_err(messages):
        raise Exception("API 连接超时")
        yield  # noqa: unreachable, make it a generator

    mock_llm.astream = _astream_err

    with patch("ai.base_agent.get_agent_llm", return_value=mock_llm):
        sample_state["raw_query"] = "hello"
        result = await chat_agent(sample_state)

    assert result["chat_response"] == "抱歉，我现在无法回复，请稍后再试。"
    assert len(result.get("errors", [])) > 0
    assert "超时" in result["errors"][0]


@pytest.mark.asyncio
async def test_chat_agent_empty_input(sample_state):
    """空输入：astream 返回空 -> 兜底消息"""
    mock_llm = MagicMock()

    async def _astream_empty(messages):
        m = MagicMock()
        m.content = ""
        yield m

    mock_llm.astream = _astream_empty

    with patch("ai.base_agent.get_agent_llm", return_value=mock_llm):
        sample_state["raw_query"] = ""
        result = await chat_agent(sample_state)

    # astream 返回空 content -> 兜底欢迎语
    assert result["chat_response"] is not None
    assert "MatchForge" in result["chat_response"]


@pytest.mark.asyncio
async def test_chat_agent_long_input(sample_state):
    """长输入不截断"""
    mock_llm = _mock_astream_llm("已收到您的需求。")

    with patch("ai.base_agent.get_agent_llm", return_value=mock_llm):
        sample_state["raw_query"] = "我" * 500 + "想找替代"
        result = await chat_agent(sample_state)

    assert result["chat_response"] is not None
    assert len(result.get("errors", [])) == 0


@pytest.mark.asyncio
async def test_chat_agent_streaming_token_assembly(sample_state):
    """#24: astream 多 chunk 正确拼接为完整响应"""
    mock_llm = _mock_astream_llm("ABCDE")  # 会被切成 ABC + DE

    with patch("ai.base_agent.get_agent_llm", return_value=mock_llm):
        sample_state["raw_query"] = "test"
        result = await chat_agent(sample_state)

    # 多 chunk 应正确拼接
    assert result["chat_response"] == "ABCDE"
