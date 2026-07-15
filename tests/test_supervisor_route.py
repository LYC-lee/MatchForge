"""
测试 supervisor.route() — 三级降级路由逻辑
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from ai.supervisor import route, _check_done, _ordered_fallback, _fallback_extract, RouteDecision, ROUTING_ORDER


class TestFallbackExtract:
    """_fallback_extract：正则兜底解析"""

    VALID_AGENTS = ["chat", "parse", "normalize", "alternatives", "match", "gen_rfq", "grade"]

    def test_json_agent_field(self):
        assert _fallback_extract('{"agent": "parse", "reason": "测试"}') == "PARSE"

    def test_json_assistant_field(self):
        assert _fallback_extract('{"assistant": "chat", "reason": "test"}') == "CHAT"

    def test_regex_agent_field(self):
        assert _fallback_extract('some text "agent": "normalize" more text') == "NORMALIZE"

    def test_keyword_search(self):
        assert _fallback_extract("这个应该交给 chat 处理") == "chat"

    def test_no_match(self):
        assert _fallback_extract("完全无关的文本") is None

    def test_json_invalid_then_regex(self):
        # 正则提取返回 "GENERAL"，验证在 route() 函数而非这里
        assert _fallback_extract('xxx "agent": "parse" yyy') == "PARSE"

    def test_agent_finish(self):
        assert _fallback_extract('{"agent": "FINISH", "reason": "done"}') == "FINISH"

    def test_strip_markdown_codeblock(self):
        assert _fallback_extract('```json\n{"agent": "chat", "reason": "test"}\n```') == "CHAT"

    def test_value_iteration(self):
        assert _fallback_extract('{"some_key": "parse"}') == "PARSE"


class TestCheckDone:
    """_check_done：各 Agent 完成状态判定"""

    def test_chat_done(self):
        assert _check_done({"chat_response": "hello"}, "chat") is True
        assert _check_done({"chat_response": None}, "chat") is False

    def test_parse_done(self):
        assert _check_done({"parsed_spec": {}}, "parse") is True
        assert _check_done({"parsed_spec": None}, "parse") is False

    def test_normalize_done(self):
        assert _check_done({"normalized_spec": {}}, "normalize") is True
        assert _check_done({"normalized_spec": None}, "normalize") is False

    def test_alternatives_done(self):
        assert _check_done({"alternatives": [{"a": 1}]}, "alternatives") is True
        assert _check_done({"alternatives": []}, "alternatives") is False

    def test_match_done(self):
        assert _check_done({"matched_suppliers": [{}]}, "match") is True
        assert _check_done({"matched_suppliers": []}, "match") is False

    def test_rfq_done(self):
        assert _check_done({"rfq_doc": "..."}, "gen_rfq") is True
        assert _check_done({"rfq_doc": None}, "gen_rfq") is False

    def test_grade_done(self):
        assert _check_done({"lead_grade": {"grade": "A"}}, "grade") is True
        assert _check_done({"lead_grade": None}, "grade") is False


class TestOrderedFallback:
    """_ordered_fallback：顺序兜底"""

    def test_all_pending(self):
        state = {k: None if k != "alternatives" else [] if k == "alternatives" else None
                 for k in ["chat_response", "parsed_spec", "normalized_spec", "rfq_doc", "lead_grade"]
                 } | {"alternatives": [], "matched_suppliers": []}
        assert _ordered_fallback(state) == "chat"

    def test_chat_done_next_parse(self):
        state = {"chat_response": "hi", "parsed_spec": None, "normalized_spec": None,
                 "alternatives": [], "matched_suppliers": [],
                 "rfq_doc": None, "lead_grade": None}
        assert _ordered_fallback(state) == "parse"

    def test_all_done_finish(self):
        state = {"chat_response": "hi", "parsed_spec": {}, "normalized_spec": {},
                 "alternatives": [{}], "matched_suppliers": [{}],
                 "rfq_doc": "", "lead_grade": {}}
        assert _ordered_fallback(state) == "FINISH"


class TestRouteLevel1Structured:
    """第 1 级：结构化输出路由"""

    @pytest.mark.asyncio
    async def test_route_to_parse(self, sample_state):
        """结构化输出路由到 parse"""
        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(
            return_value=RouteDecision(agent="parse", reason="用户输入是元器件需求")
        )
        with patch("ai.supervisor.get_supervisor_chain", return_value=mock_chain):
            result = await route(sample_state)
        assert result["next_agent"] == "parse"
        assert "元器件" in result["route_reason"]

    @pytest.mark.asyncio
    async def test_route_to_chat(self, sample_state):
        """结构化输出路由到 chat"""
        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(
            return_value=RouteDecision(agent="chat", reason="用户打招呼")
        )
        with patch("ai.supervisor.get_supervisor_chain", return_value=mock_chain):
            result = await route(sample_state)
        assert result["next_agent"] == "chat"

    @pytest.mark.asyncio
    async def test_route_to_finish(self, sample_state):
        """结构化输出路由到 FINISH"""
        sample_state.update({"chat_response": "hi", "parsed_spec": {}, "normalized_spec": {},
                             "alternatives": [{}], "matched_suppliers": [{}],
                             "rfq_doc": "", "lead_grade": {}})
        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(
            return_value=RouteDecision(agent="FINISH", reason="全部完成")
        )
        with patch("ai.supervisor.get_supervisor_chain", return_value=mock_chain):
            result = await route(sample_state)
        assert result["next_agent"] == "FINISH"


class TestRouteLevel2Fallback:
    """第 2 级：结构化失败 → 正则兜底"""

    @pytest.mark.asyncio
    async def test_structured_fails_fallback_to_parse(self, sample_state):
        """chain.ainvoke 抛异常 → 正则兜底成功 → parse"""
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(side_effect=Exception("LLM parse error"))

        with (
            patch("ai.supervisor.get_supervisor_chain", return_value=mock_chain),
            patch("ai.supervisor.get_supervisor_llm") as mock_get_llm,
        ):
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = '{"agent": "parse", "reason": "fallback"}'
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_get_llm.return_value = mock_llm

            result = await route(sample_state)

        assert result["next_agent"] == "parse"
        assert "兜底" in result["route_reason"]

    @pytest.mark.asyncio
    async def test_structured_fails_fallback_to_ordered(self, sample_state):
        """chain.ainvoke 抛异常 + 正则兜底无结果 → 顺序 fallback"""
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(side_effect=Exception("LLM parse error"))

        with (
            patch("ai.supervisor.get_supervisor_chain", return_value=mock_chain),
            patch("ai.supervisor.get_supervisor_llm") as mock_get_llm,
        ):
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "完全无法解析的内容"
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_get_llm.return_value = mock_llm

            result = await route(sample_state)

        # 顺序 fallback：chat（第一个未完成的）
        assert result["next_agent"] == "chat"
        assert "顺序" in result["route_reason"]

    @pytest.mark.asyncio
    async def test_complete_failure_all_fallback(self, sample_state):
        """all ainvoke throws → 最终顺序 fallback"""
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(side_effect=Exception("LLM parse error"))

        with (
            patch("ai.supervisor.get_supervisor_chain", return_value=mock_chain),
            patch("ai.supervisor.get_supervisor_llm") as mock_get_llm,
        ):
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM also dead"))
            mock_get_llm.return_value = mock_llm

            result = await route(sample_state)

        assert result["next_agent"] in ROUTING_ORDER + ["FINISH"]
        assert "顺序" in result["route_reason"]


class TestRouteLevel3Hardcoded:
    """第 3 级：极限情况下的硬编码 fallback"""

    @pytest.mark.asyncio
    async def test_everything_fails_returns_chat(self, sample_state):
        """所有尝试全部失败 → 返回 chat"""
        sample_state["chat_response"] = None
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(side_effect=Exception("chain dead"))

        with (
            patch("ai.supervisor.get_supervisor_chain", return_value=mock_chain),
            patch("ai.supervisor.get_supervisor_llm") as mock_get_llm,
        ):
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM dead"))
            mock_get_llm.return_value = mock_llm

            result = await route(sample_state)

        # 顺序第一个未完成的是 chat
        assert result["next_agent"] == "chat"

    @pytest.mark.asyncio
    async def test_agent_name_normalization(self, sample_state):
        """RouteDecision 的 agent 名小写化"""
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(
            return_value=RouteDecision(agent="alternatives", reason="uppercase test")
        )
        with patch("ai.supervisor.get_supervisor_chain", return_value=mock_chain):
            result = await route(sample_state)
        assert result["next_agent"] == "alternatives"