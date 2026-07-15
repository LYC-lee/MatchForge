"""
MatchForge 子 Agent 模块

每个 Agent 模块统一暴露:
  - async def xxx_agent(state) -> state  # 原始函数名
  - process = xxx_agent                   # ecs_assistant 风格别名

Agent 列表:
  ① parse        — 需求解析（正则前置 + LLM 槽位提取）
  ② normalize    — 标准化（MySQL 字典映射）
  ③ alternatives — 替代料推荐（Neo4j 图查询 + LLM 推理）
  ④ match        — 供应商匹配（MySQL 查询 + 评分排序）
  ⑤ gen_rfq      — 询价单生成（模板填充）
  ⑥ grade        — 线索分级（规则评分）
  💬 chat        — 聊天对话（轻量 LLM 直接回复）
"""

from ai.agents.chat import chat_agent, process as chat_process
from ai.agents.parse import parse_agent, process as parse_process
from ai.agents.normalize import normalize_agent, process as normalize_process
from ai.agents.alternatives import alternatives_agent, process as alternatives_process
from ai.agents.match import match_agent, process as match_process
from ai.agents.gen_rfq import gen_rfq_agent, process as gen_rfq_process
from ai.agents.grade import grade_agent, process as grade_process

__all__ = [
    "chat_agent", "chat_process",
    "parse_agent", "parse_process",
    "normalize_agent", "normalize_process",
    "alternatives_agent", "alternatives_process",
    "match_agent", "match_process",
    "gen_rfq_agent", "gen_rfq_process",
    "grade_agent", "grade_process",
]