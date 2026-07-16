"""
测试 Agent 💬 — 聊天对话
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from ai.agents.chat import chat_agent


@pytest.mark.asyncio
async def test_chat_agent_normal_reply(sample_state):
    """正常聊天：返回欢迎回复"""
    mock_response = MagicMock()
    mock_response.content = "您好！我是 MatchForge 智配助手，请告诉我您需要什么帮助。"
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("ai.base_agent.get_agent_llm", return_value=mock_llm) as mock_get:
        sample_state["raw_query"] = "你好"
        result = await chat_agent(sample_state)

    assert result["chat_response"] is not None
    assert "MatchForge" in result["chat_response"] or "您好" in result["chat_response"]
    assert len(result.get("errors", [])) == 0
    mock_get.assert_called_once_with(heavy=False, temperature=0.7, max_tokens=512, timeout=15)


@pytest.mark.asyncio
async def test_chat_agent_greeting(sample_state):
    """问候语：返回友好回应"""
    mock_response = MagicMock()
    mock_response.content = "嗨！有什么可以帮您的吗？"
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("ai.base_agent.get_agent_llm", return_value=mock_llm):
        sample_state["raw_query"] = "在吗"
        result = await chat_agent(sample_state)

    assert result["chat_response"] is not None
    assert len(result.get("errors", [])) == 0


@pytest.mark.asyncio
async def test_chat_agent_function_intro(sample_state):
    """功能介绍：引导使用寻源功能"""
    mock_response = MagicMock()
    mock_response.content = "我可以帮您查找元器件替代料、匹配供应商。您可以输入型号试试！"
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("ai.base_agent.get_agent_llm", return_value=mock_llm):
        sample_state["raw_query"] = "你能做什么"
        result = await chat_agent(sample_state)

    assert result["chat_response"] is not None
    assert len(result.get("errors", [])) == 0


@pytest.mark.asyncio
async def test_chat_agent_llm_error(sample_state):
    """LLM 异常：返回兜底消息 + 记录 error"""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=Exception("API 连接超时"))

    with patch("ai.base_agent.get_agent_llm", return_value=mock_llm):
        sample_state["raw_query"] = "hello"
        result = await chat_agent(sample_state)

    assert result["chat_response"] == "抱歉，我现在无法回复，请稍后再试。"
    assert len(result.get("errors", [])) > 0
    assert "超时" in result["errors"][0]


@pytest.mark.asyncio
async def test_chat_agent_empty_input(sample_state):
    """空输入：返回兜底"""
    mock_response = MagicMock()
    mock_response.content = "请输入您的问题。"
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("ai.base_agent.get_agent_llm", return_value=mock_llm):
        sample_state["raw_query"] = ""
        result = await chat_agent(sample_state)

    assert result["chat_response"] is not None


@pytest.mark.asyncio
async def test_chat_agent_long_input(sample_state):
    """长输入不截断"""
    mock_response = MagicMock()
    mock_response.content = "已收到您的需求。"
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("ai.base_agent.get_agent_llm", return_value=mock_llm):
        sample_state["raw_query"] = "我" * 500 + "想找替代"
        result = await chat_agent(sample_state)

    assert result["chat_response"] is not None
    assert len(result.get("errors", [])) == 0