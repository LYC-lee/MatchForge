"""
MatchForge Agent 监控与日志系统

监控每个 Agent 的工作状态:
  - 开始/结束时间
  - 执行耗时
  - 状态 (running/done/error)
  - 输入/输出摘要
  - 错误信息

用法:
  from ai.monitor import AgentLogger
  log = AgentLogger("parse")
  async with log.measure(state):
      result = await parse_agent(state)
"""

import time
import json
import logging
import os
from datetime import datetime
from typing import Optional
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from ai.state import ProcureState

# ============================================================
# 日志配置
# ============================================================
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "agents.jsonl")
ERROR_LOG_FILE = os.path.join(LOG_DIR, "errors.jsonl")
TRACE_LOG_FILE = os.path.join(LOG_DIR, "trace.jsonl")

# 标准 Python logger（控制台输出）
logger = logging.getLogger("matchforge.agents")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger.addHandler(_handler)


# ============================================================
# Agent 日志条目
# ============================================================
class AgentLogEntry:
    """单个 Agent 的运行记录"""

    def __init__(
        self,
        agent_name: str,
        thread_id: str,
        phase: str,
    ):
        self.agent_name = agent_name
        self.thread_id = thread_id
        self.phase = phase
        self.started_at: Optional[float] = None
        self.ended_at: Optional[float] = None
        self.duration_ms: Optional[float] = None
        self.status: str = "pending"       # pending / running / done / error
        self.input_summary: str = ""       # 输入摘要
        self.output_summary: str = ""      # 输出摘要
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
            alt = output.get("alternatives") or output.get("alternatives")
            if isinstance(alt, list):
                self.alt_count = len(alt)
            sup = output.get("matched_suppliers") or output.get("matched_suppliers")
            if isinstance(sup, list):
                self.sup_count = len(sup)

        self.output_summary = _summarize_state(output, self.agent_name) if isinstance(output, dict) else str(output)[:200]

    def to_dict(self) -> dict:
        return {
            "agent": self.agent_name,
            "thread_id": self.thread_id,
            "phase": self.phase,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "input": self.input_summary[:300],
            "output": self.output_summary[:300],
            "alt_count": self.alt_count,
            "sup_count": self.sup_count,
            "error": self.error[:500] if self.error else None,
            "started_at": datetime.fromtimestamp(self.started_at).isoformat() if self.started_at else None,
            "ended_at": datetime.fromtimestamp(self.ended_at).isoformat() if self.ended_at else None,
        }

    def log_to_console(self):
        if self.status == "done":
            dur = f"{self.duration_ms}ms" if self.duration_ms else ""
            extra = ""
            if self.alt_count:
                extra += f" [替代: {self.alt_count}]"
            if self.sup_count:
                extra += f" [供应商: {self.sup_count}]"
            logger.info(f"✅ {self.agent_name:>12}  {dur:>8}{extra}")
        elif self.status == "error":
            logger.error(f"❌ {self.agent_name:>12}  {self.error[:100]}")
        elif self.status == "running":
            logger.info(f"▶️  {self.agent_name:>12}  开始执行...")

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


# ============================================================
# 摘要辅助函数
# ============================================================
def _summarize_state(state: dict, agent_name: str = "") -> str:
    """对 State 做摘要，避免日志太大"""
    parts = []

    if state.get("raw_query"):
        q = state["raw_query"]
        parts.append(f"query={q[:60]}")
    if state.get("parsed_spec"):
        parts.append(f"parsed=✓")
    if state.get("normalized_spec"):
        parts.append(f"normalized=✓")
    if agent_name in ("alternatives", "") and state.get("alternatives"):
        parts.append(f"alternatives={len(state['alternatives'])}")
    if agent_name in ("match", "") and state.get("matched_suppliers"):
        parts.append(f"suppliers={len(state['matched_suppliers'])}")
    if state.get("rfq_doc"):
        parts.append(f"rfq=✓({len(state['rfq_doc'])}ch)")
    if state.get("lead_grade"):
        parts.append(f"grade={state['lead_grade'].get('grade')}")
    if state.get("errors"):
        parts.append(f"errors={len(state['errors'])}")

    return " | ".join(parts) if parts else "-"


# ============================================================
# AgentLogger — 每个 Agent 一个实例
# ============================================================
class AgentLogger:
    """
    Agent 日志记录器

    用法:
        log = AgentLogger("parse")
        log.start(state, phase)
        try:
            result = await agent_fn(state)
            log.end(result)
        except Exception as e:
            log.fail(e)
    """

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


# ============================================================
# 写日志文件
# ============================================================
def _write_log(entry: AgentLogEntry):
    """追加写到 agents.jsonl"""
    try:
        line = entry.to_json() + "\n"
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def _write_error_log(entry: AgentLogEntry):
    """错误单独写入 errors.jsonl"""
    if entry.status == "error":
        try:
            line = entry.to_json() + "\n"
            with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass


# ============================================================
# 追踪日志 (TraceID + 完整链路)
# ============================================================
class TraceLogger:
    """
    全链路追踪日志

    记录一次 procure 请求经过的所有 Agent 的执行链路。
    写入 trace.jsonl，每条记录包含完整的 thread 级别日志。

    用法:
        trace = TraceLogger(thread_id, phase)
        trace.begin(raw_query)
        trace.agent_done(agent_log)
        trace.end(state)
        trace.flush()
    """

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
        success = len(self.agents)
        errors = [a for a in self.agents if a.status == "error"]

        trace = {
            "thread_id": self.thread_id,
            "phase": self.phase,
            "raw_query": self.raw_query[:100],
            "total_duration_ms": total_ms,
            "agents_done": success,
            "agents_error": len(errors),
            "agents": [a.to_dict() for a in self.agents],
            "final": _summarize_state(state),
            "timestamp": datetime.now().isoformat(),
        }

        # 控制台输出
        if errors:
            logger.warning(f"━━━ [{self.thread_id[:8]}] 完成 ({success} agent, {len(errors)} error) {total_ms}ms")
        else:
            logger.info(f"━━━ [{self.thread_id[:8]}] 完成 ({success} agent) {total_ms}ms")

        # 写入 trace.jsonl
        try:
            line = json.dumps(trace, ensure_ascii=False) + "\n"
            with open(TRACE_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass


# ============================================================
# 查询日志 (调试用)
# ============================================================
def get_recent_logs(n: int = 10) -> list[dict]:
    """读取最近 n 条 Agent 日志"""
    logs = []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    logs.append(json.loads(line))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return logs[-n:]


def get_thread_trace(thread_id: str) -> list[dict]:
    """按 thread_id 查询完整追踪链路"""
    traces = []
    try:
        with open(TRACE_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    trace = json.loads(line)
                    if trace.get("thread_id") == thread_id:
                        traces.append(trace)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return traces


def print_agent_summary(n: int = 20):
    """打印最近 n 条 Agent 日志到控制台"""
    logs = get_recent_logs(n)
    if not logs:
        print("暂无 Agent 日志")
        return

    print(f"\n{'Agent':<14} {'状态':<8} {'耗时':<10} {'输入/输出摘要'}")
    print("-" * 70)
    for log in reversed(logs):
        dur = f"{log['duration_ms']}ms" if log.get("duration_ms") else "-"
        icon = "✅" if log["status"] == "done" else "❌" if log["status"] == "error" else "⏳"
        summary = log.get("input", "")[:40]
        if log.get("output"):
            summary += f" → {log['output'][:30]}"
        print(f"{icon} {log['agent']:<12} {log['status']:<8} {dur:<10} {summary}")
    print()