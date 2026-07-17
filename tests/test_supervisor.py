"""
测试 graph.py - SSE 流式推送
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import patch
from ai.graph import run_procure_stream


class _FakeGraph:
    """没有 astream_events 的 fake graph, 强制走 astream 降级路径 (#24)。"""
    def __init__(self, astream_fn):
        self._astream = astream_fn

    async def astream(self, *a, **kw):
        async for x in self._astream(*a, **kw):
            yield x


@pytest.mark.asyncio
async def test_citation_event_emitted_when_rag_enrich_has_citations(sample_normalized_spec):
    """#22: rag_enrich 产出 citations 时, SSE 流应发 citation 事件 (契约 C1)"""
    citations = [{"doc": "product", "chunk_id": "1", "chunk_uid": "u1",
                  "score": 0.9, "excerpt": "...", "company_id": 1, "language": "zh"}]

    async def fake_astream(*a, **kw):
        yield {"rag_enrich": {"rag_enrichment": {"supplier_reports": [],
                                                  "citations": citations,
                                                  "summary": "ok"}}}

    fake_graph = _FakeGraph(fake_astream)

    with patch("ai.graph.get_graph", return_value=fake_graph):
        events = []
        async for event in run_procure_stream(
            phase="match", confirmed_spec=sample_normalized_spec, thread_id="t-cit"):
            events.append(event)

    cit_events = []
    for e in events:
        if e.startswith("data: "):
            data = json.loads(e.replace("data: ", "").replace("\n\n", ""))
            if data.get("type") == "citation":
                cit_events.append(data)
    assert len(cit_events) == 1
    assert cit_events[0]["agent"] == "rag_enrich"
    assert cit_events[0]["citations"] == citations


@pytest.mark.asyncio
async def test_no_citation_event_when_rag_enrich_empty(sample_normalized_spec):
    """#22: rag_enrich 无 citations 时不发 citation 事件"""
    async def fake_astream(*a, **kw):
        yield {"rag_enrich": {"rag_enrichment": {"supplier_reports": [],
                                                  "citations": [], "summary": "ok"}}}

    fake_graph = _FakeGraph(fake_astream)

    with patch("ai.graph.get_graph", return_value=fake_graph):
        events = []
        async for event in run_procure_stream(
            phase="match", confirmed_spec=sample_normalized_spec, thread_id="t-nocit"):
            events.append(event)

    cit_events = [e for e in events if e.startswith("data: ") and
                  json.loads(e.replace("data: ", "").replace("\n\n", "")).get("type") == "citation"]
    assert len(cit_events) == 0


@pytest.mark.asyncio
async def test_run_procure_stream_spec_phase(sample_raw_query):
    """spec 阶段：发送 parse + normalize -> result -> end"""
    events = []
    async for event in run_procure_stream(raw_query=sample_raw_query, phase="spec"):
        events.append(event)

    event_types = []
    for e in events:
        data = json.loads(e.replace("data: ", "").replace("\n\n", ""))
        event_types.append(data["type"])

    assert "start" in event_types
    assert "result" in event_types
    assert "end" in event_types


@pytest.mark.asyncio
async def test_run_procure_stream_match_phase(sample_normalized_spec):
    """match 阶段：发送 alternatives + match + gen_rfq + grade -> result -> end"""
    events = []
    async for event in run_procure_stream(
        phase="match",
        confirmed_spec=sample_normalized_spec,
        thread_id="test-match-001",
    ):
        events.append(event)

    event_types = []
    for e in events:
        data = json.loads(e.replace("data: ", "").replace("\n\n", ""))
        event_types.append(data["type"])

    assert "start" in event_types
    assert "result" in event_types
    assert "end" in event_types


@pytest.mark.asyncio
async def test_run_procure_stream_error_handling():
    """Agent 抛异常时不中断，写入 errors"""
    events = []
    async for event in run_procure_stream(raw_query="", phase="spec"):
        events.append(event)

    final_data = None
    for e in events:
        if 'data: ' in e:
            data = json.loads(e.replace("data: ", "").replace("\n\n", ""))
            if data["type"] == "result":
                final_data = data

    assert final_data is not None
    # 空 query 应该触发 error，但 result 仍然返回且不崩溃


# ============================================================
# #23 多轮引用解析 (C4)
# ============================================================
from ai.graph import _resolve_references


class TestReferenceResolution:
    def test_ordinal_reference(self):
        """'第二个的交期' -> 解析为第 2 个替代料的 part"""
        snapshot = {
            "current_spec": {"part_number": "TMK212BJ105KG-T"},
            "alternatives": [
                {"part": "ALT001", "brand": "A"},
                {"part": "ALT002", "brand": "B"},
            ],
        }
        resolved, log = _resolve_references("第二个的交期多久", snapshot)
        assert "ALT002" in resolved
        assert "第2个" in log

    def test_ordinal_reference_chinese(self):
        """'第三个' (中文数字) -> 解析"""
        snapshot = {
            "alternatives": [
                {"part": "ALT001"}, {"part": "ALT002"}, {"part": "ALT003"},
            ],
        }
        resolved, log = _resolve_references("第三个的价格", snapshot)
        assert "ALT003" in resolved

    def test_that_one_reference(self):
        """'刚才那个' -> 解析为 current_spec.part_number"""
        snapshot = {
            "current_spec": {"part_number": "GRM188R61A106KE69D"},
            "alternatives": [],
        }
        resolved, log = _resolve_references("刚才那个的替代料", snapshot)
        assert "GRM188R61A106KE69D" in resolved

    def test_it_reference(self):
        """'它' -> 解析为 current_spec.part_number"""
        snapshot = {"current_spec": {"part_number": "TMK212BJ105KG-T"}}
        resolved, log = _resolve_references("它的交期", snapshot)
        assert "TMK212BJ105KG-T" in resolved

    def test_no_snapshot(self):
        """无 snapshot -> 原样返回"""
        resolved, log = _resolve_references("第二个的交期", None)
        assert resolved == "第二个的交期"
        assert log is None

    def test_no_reference_in_query(self):
        """无指代词的 query -> 原样返回"""
        snapshot = {"alternatives": [{"part": "ALT001"}]}
        resolved, log = _resolve_references("查一下规格", snapshot)
        assert resolved == "查一下规格"
        assert log is None

    def test_ordinal_out_of_range(self):
        """'第10个' 但只有 2 个 alternatives -> 原样返回, 不解析"""
        snapshot = {"alternatives": [{"part": "A"}, {"part": "B"}]}
        resolved, log = _resolve_references("第10个的规格", snapshot)
        # 无法解析, 保持原样
        assert "第10个" in resolved