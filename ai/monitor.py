"""
MatchForge Agent 监控与日志系统

监控每个 Agent 的工作状态:
  - 开始/结束时间
  - 执行耗时
  - 状态 (running/done/error)
  - 输入/输出摘要
  - 错误信息
"""

import time
import json
import logging
import os
from datetime import datetime
from typing import Optional
from ai.state import ProcureState

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "agents.jsonl")
ERROR_LOG_FILE = os.path.join(LOG_DIR, "errors.jsonl")
TRACE_LOG_FILE = os.path.join(LOG_DIR, "trace.jsonl")
MAX_LOG_SIZE = 50 * 1024 * 1024  # 50MB 轮转

logger = logging.getLogger("matchforge.agents")
logger.setLevel(logging.INFO)
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(h)


def _rotate(path: str):
    if os.path.exists(path) and os.path.getsize(path) > MAX_LOG_SIZE:
        bak = path + ".1"
        if os.path.exists(bak):
            os.remove(bak)
        os.rename(path, bak)


class AgentLogEntry:
    def __init__(self, agent_name: str, thread_id: str, phase: str):
        self.agent_name = agent_name
        self.thread_id = thread_id
        self.phase = phase
        self.started_at: Optional[float] = None
        self.ended_at: Optional[float] = None
        self.duration_ms: Optional[float] = None
        self.status: str = "pending"
        self.input_summary: str = ""
        self.output_summary: str = ""
        self.error: Optional[str] = None
        self.alt_count: int = 0
        self.sup_count: int = 0

    def start(self):
        self.started_at = time.time()
        self.status = "running"

    def end(self, output=None):
        self.ended_at = time.time()
        self.duration_ms = round((self.ended_at - self.started_at) * 1000) if self.started_at else 0
        self.status = "done"
        self._summarize_output(output)

    def fail(self, error: str):
        self.ended_at = time.time()
        self.duration_ms = round((self.ended_at - self.started_at) * 1000) if self.started_at else 0
        self.status = "error"
        self.error = str(error)[:500]

    def set_input_summary(self, state: ProcureState):
        self.input_summary = _summarize_state(state, self.agent_name)

    def _summarize_output(self, output):
        if isinstance(output, dict):
            a = output.get("alternatives")
            if isinstance(a, list):
                self.alt_count = len(a)
            s = output.get("matched_suppliers")
            if isinstance(s, list):
                self.sup_count = len(s)
        self.output_summary = _summarize_state(output, self.agent_name) if isinstance(output, dict) else str(output)[:200]

    def to_dict(self) -> dict:
        return {
            "agent": self.agent_name, "thread_id": self.thread_id, "phase": self.phase,
            "status": self.status, "duration_ms": self.duration_ms,
            "input": self.input_summary[:300], "output": self.output_summary[:300],
            "alt_count": self.alt_count, "sup_count": self.sup_count,
            "error": self.error[:500] if self.error else None,
            "started_at": datetime.fromtimestamp(self.started_at).isoformat() if self.started_at else None,
            "ended_at": datetime.fromtimestamp(self.ended_at).isoformat() if self.ended_at else None,
        }

    def log_to_console(self):
        if self.status == "done":
            extra = ""
            if self.alt_count: extra += f" [替代: {self.alt_count}]"
            if self.sup_count: extra += f" [供应商: {self.sup_count}]"
            logger.info(f"✅ {self.agent_name:>12}  {self.duration_ms or 0:>8}ms{extra}")
        elif self.status == "error":
            logger.error(f"❌ {self.agent_name:>12}  {self.error[:100]}")
        elif self.status == "running":
            logger.info(f"▶️  {self.agent_name:>12}  开始执行...")

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


def _summarize_state(state: dict, agent_name: str = "") -> str:
    parts = []
    if state.get("raw_query"):
        parts.append(f"query={state['raw_query'][:60]}")
    if state.get("parsed_spec"): parts.append("parsed=✓")
    if state.get("normalized_spec"): parts.append("normalized=✓")
    if agent_name in ("alternatives", "") and state.get("alternatives"):
        parts.append(f"alternatives={len(state['alternatives'])}")
    if agent_name in ("match", "") and state.get("matched_suppliers"):
        parts.append(f"suppliers={len(state['matched_suppliers'])}")
    if state.get("rfq_doc"): parts.append(f"rfq=✓({len(state['rfq_doc'])}ch)")
    if state.get("lead_grade"): parts.append(f"grade={state['lead_grade'].get('grade')}")
    if state.get("errors"): parts.append(f"errors={len(state['errors'])}")
    return " | ".join(parts) if parts else "-"


class AgentLogger:
    def __init__(self, agent_name: str, thread_id: str = "", phase: str = ""):
        self.entry = AgentLogEntry(agent_name, thread_id, phase)

    def start(self, state: ProcureState, phase: str = ""):
        self.entry.phase = phase or self.entry.phase
        self.entry.start()
        self.entry.set_input_summary(state)
        self.entry.log_to_console()

    def end(self, output=None):
        self.entry.end(output)
        self.entry.log_to_console()
        _write_log(self.entry)

    def fail(self, error: str):
        self.entry.fail(error)
        self.entry.log_to_console()
        _write_log(self.entry)
        _write_error_log(self.entry)


def _write_log(entry: AgentLogEntry):
    try:
        _rotate(LOG_FILE)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry.to_json() + "\n")
    except Exception:
        pass


def _write_error_log(entry: AgentLogEntry):
    if entry.status == "error":
        try:
            _rotate(ERROR_LOG_FILE)
            with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(entry.to_json() + "\n")
        except Exception:
            pass


class TraceLogger:
    def __init__(self, thread_id: str, phase: str = ""):
        self.thread_id = thread_id
        self.phase = phase
        self.agents: list[AgentLogEntry] = []
        self.started_at = time.time()
        self.raw_query = ""

    def begin(self, raw_query: str = ""):
        self.raw_query = raw_query
        logger.info(f"━━━ [{self.thread_id[:8]}] 寻源开始 ━━━  {raw_query[:60]}")

    def agent_done(self, log: AgentLogEntry):
        self.agents.append(log)

    def end(self, state: ProcureState):
        total_ms = round((time.time() - self.started_at) * 1000)
        errs = [a for a in self.agents if a.status == "error"]
        trace = {
            "thread_id": self.thread_id, "phase": self.phase,
            "raw_query": self.raw_query[:100], "total_duration_ms": total_ms,
            "agents_done": len(self.agents), "agents_error": len(errs),
            "agents": [a.to_dict() for a in self.agents],
            "final": _summarize_state(state), "timestamp": datetime.now().isoformat(),
        }
        if errs:
            logger.warning(f"━━━ [{self.thread_id[:8]}] 完成 ({len(self.agents)} agent, {len(errs)} error) {total_ms}ms")
        else:
            logger.info(f"━━━ [{self.thread_id[:8]}] 完成 ({len(self.agents)} agent) {total_ms}ms")
        try:
            _rotate(TRACE_LOG_FILE)
            with open(TRACE_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(trace, ensure_ascii=False) + "\n")
        except Exception:
            pass


def get_recent_logs(n: int = 10) -> list[dict]:
    logs = []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    logs.append(json.loads(line))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return logs[-n:]


def print_agent_summary(n: int = 20):
    logs = get_recent_logs(n)
    if not logs:
        print("暂无 Agent 日志"); return
    print(f"\n{'Agent':<14} {'状态':<8} {'耗时':<10} {'输入/输出摘要'}")
    print("-" * 70)
    for log in reversed(logs):
        dur = f"{log['duration_ms']}ms" if log.get("duration_ms") else "-"
        icon = "✅" if log["status"] == "done" else "❌" if log["status"] == "error" else "⏳"
        s = log.get("input", "")[:40]
        if log.get("output"): s += f" → {log['output'][:30]}"
        print(f"{icon} {log['agent']:<12} {log['status']:<8} {dur:<10} {s}")
    print()