"""
测试 monitor.py — AgentLogger / TraceLogger / 日志轮转
"""

import os
import json
import time
from unittest.mock import patch, MagicMock
from ai.monitor import AgentLogger, TraceLogger, AgentLogEntry, _rotate, _summarize_state, print_agent_summary


def test_agent_log_entry_start():
    entry = AgentLogEntry("parse", "test-001", "spec")
    entry.start()
    assert entry.status == "running"
    assert entry.started_at is not None


def test_agent_log_entry_end():
    entry = AgentLogEntry("parse", "test-001", "spec")
    entry.start()
    entry.end({"parsed_spec": {"category": "MLCC"}})
    assert entry.status == "done"
    assert entry.duration_ms is not None
    assert entry.duration_ms >= 0


def test_agent_log_entry_fail():
    entry = AgentLogEntry("parse", "test-001", "spec")
    entry.start()
    entry.fail("Connection refused")
    assert entry.status == "error"
    assert "Connection refused" in entry.error


def test_agent_log_entry_alt_count():
    entry = AgentLogEntry("alternatives", "test-001", "match")
    entry.start()
    entry.end({"alternatives": [{"part": "A"}, {"part": "B"}], "matched_suppliers": [{"id": "S1"}]})
    assert entry.alt_count == 2
    assert entry.sup_count == 1


def test_agent_logger_lifecycle():
    log = AgentLogger("parse", "test-002")
    state = {"raw_query": "test query", "parsed_spec": None, "thread_id": "test-002"}
    log.start(state)
    time.sleep(0.01)
    log.end({"parsed_spec": {"category": "MLCC"}})
    assert log.entry.status == "done"
    assert log.entry.duration_ms > 0


def test_agent_logger_fail():
    log = AgentLogger("parse", "test-003")
    log.start({"raw_query": "test", "thread_id": "test-003"})
    log.fail("Something went wrong")
    assert log.entry.status == "error"


def test_summarize_state():
    s = _summarize_state({"raw_query": "TMK212BJ105KG-T", "parsed_spec": {"a": 1}})
    assert "query=" in s
    assert "parsed=✓" in s


def test_summarize_state_empty():
    s = _summarize_state({})
    assert s == "-"


def test_trace_logger_begin_end():
    trace = TraceLogger("trace-001", "spec")
    trace.begin("test query")
    assert trace.raw_query == "test query"
    trace.end({"parsed_spec": {"a": 1}})


def test_print_agent_summary(capsys):
    print_agent_summary(5)
    captured = capsys.readouterr()
    # 不报错即可


def test_rotate_noop(tmp_path):
    """文件小于阈值，不轮转"""
    f = tmp_path / "test.log"
    f.write_text("a" * 100)
    size_before = os.path.getsize(f)
    # 由于文件很小，_rotate 不应删除或改名
    _rotate(str(f))
    assert os.path.exists(f)


def test_to_dict():
    entry = AgentLogEntry("parse", "t1", "spec")
    entry.start()
    d = entry.to_dict()
    assert d["agent"] == "parse"
    assert d["status"] == "running"


def test_to_json():
    entry = AgentLogEntry("parse", "t1", "spec")
    entry.start()
    entry.end({})
    j = entry.to_json()
    data = json.loads(j)
    assert data["agent"] == "parse"
    assert data["status"] == "done"