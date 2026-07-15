"""
测试 supervisor 高级功能 — memory_inject / memory_save / fallback routing
"""

from __future__ import annotations

from collections import namedtuple
import pytest

from ai.graph import (
    build_graph, init_state, run_procure_stream,
    memory_inject_node, memory_save_node,
)
from ai.supervisor import _check_done, _ordered_fallback


class FakeStore:
    def __init__(self):
        self._data = {}

    def get(self, namespace, key):
        Item = namedtuple("Item", ["value"])
        val = self._data.get((namespace, key))
        return Item(val) if val else None

    def put(self, namespace, key, value):
        self._data[(namespace, key)] = value


class FakeRuntime:
    def __init__(self):
        self.store = FakeStore()


@pytest.mark.asyncio
async def test_memory_inject_with_brands():
    state = {"user_id": "test-user"}
    runtime = FakeRuntime()
    runtime.store.put(("test-user", "preferences"), "brand_pref", ["YAGEO", "Murata"])
    result = await memory_inject_node(state, runtime)
    assert result.get("user_brand_pref") == ["YAGEO", "Murata"]


@pytest.mark.asyncio
async def test_memory_inject_no_user():
    result = await memory_inject_node({"user_id": None}, FakeRuntime())
    assert result == {}


@pytest.mark.asyncio
async def test_memory_save_brand():
    state = {"user_id": "test-user", "parsed_spec": {"part_number": "TMK212BJ105KG-T", "brand": "YAGEO"}}
    runtime = FakeRuntime()
    await memory_save_node(state, runtime)
    item = runtime.store.get(("test-user", "preferences"), "brand_pref")
    assert item is not None
    assert "YAGEO" in item.value


@pytest.mark.asyncio
async def test_memory_save_part_history():
    state = {"user_id": "test-user", "parsed_spec": {"part_number": "GRM188R61A106KE69D", "brand": "Murata"}}
    runtime = FakeRuntime()
    await memory_save_node(state, runtime)
    item = runtime.store.get(("test-user", "preferences"), "part_history")
    assert item is not None
    assert len(item.value) == 1
    assert item.value[0]["part_number"] == "GRM188R61A106KE69D"


def test_fallback_routing():
    """fallback 路由：chat 优先，完成后才到 parse"""
    state = {"chat_response": None, "parsed_spec": None, "normalized_spec": None,
             "alternatives": [], "matched_suppliers": [],
             "rfq_doc": None, "lead_grade": None}
    assert _ordered_fallback(state) == "chat"
    state["chat_response"] = "hello"
    state["parsed_spec"] = None
    assert _ordered_fallback(state) == "parse"
    state["parsed_spec"] = {}
    assert _ordered_fallback(state) == "normalize"


def test_fallback_finish():
    """全部完成 -> FINISH"""
    state = {"chat_response": "hi", "parsed_spec": {}, "normalized_spec": {},
             "alternatives": [{}], "matched_suppliers": [{}],
             "rfq_doc": "", "lead_grade": {}}
    assert _ordered_fallback(state) == "FINISH"


def test_check_done():
    """_check_done 识别各字段"""
    state = {"chat_response": "hi", "parsed_spec": {}, "normalized_spec": None,
             "alternatives": [], "matched_suppliers": [],
             "rfq_doc": None, "lead_grade": None}
    assert _check_done(state, "chat") is True
    assert _check_done(state, "parse") is True
    assert _check_done(state, "normalize") is False


def test_build_graph():
    graph = build_graph()
    assert graph is not None


def test_init_state():
    state = init_state("test query", "user-001", "thread-001")
    assert state["raw_query"] == "test query"
    assert state["thread_id"] == "thread-001"
    assert state["user_id"] == "user-001"
    assert state["errors"] == []
    assert state["next_agent"] == "chat"