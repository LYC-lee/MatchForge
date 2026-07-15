"""
测试 supervisor.py — SSE 流式推送
"""

import pytest
from unittest.mock import patch, AsyncMock
from ai.supervisor import run_procure_stream


@pytest.mark.asyncio
async def test_run_procure_stream_spec_phase(sample_raw_query):
    """spec 阶段：发送 parse + normalize → result → end"""
    events = []
    async for event in run_procure_stream(raw_query=sample_raw_query, phase="spec"):
        events.append(event)

    event_types = []
    for e in events:
        import json
        data = json.loads(e.replace("data: ", "").replace("\n\n", ""))
        event_types.append(data["type"])

    assert "start" in event_types
    assert "result" in event_types
    assert "end" in event_types


@pytest.mark.asyncio
async def test_run_procure_stream_match_phase(sample_normalized_spec):
    """match 阶段：发送 alternatives + match + gen_rfq + grade → result → end"""
    events = []
    async for event in run_procure_stream(
        phase="match",
        confirmed_spec=sample_normalized_spec,
        thread_id="test-match-001",
    ):
        events.append(event)

    event_types = []
    for e in events:
        import json
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
        import json
        if 'data: ' in e:
            data = json.loads(e.replace("data: ", "").replace("\n\n", ""))
            if data["type"] == "result":
                final_data = data

    assert final_data is not None
    # 空 query 应该触发 error，但 result 仍然返回且不崩溃