"""
MatchForge AI 编排层 — LangGraph 多 Agent 系统

架构:
  - base_agent: 集中式 LLM 工厂 + 可复用 Agent 执行引擎
  - config: 环境与路径配置
  - state: LangGraph 共享状态定义 (ProcureState)
  - supervisor: Supervisor 路由 Agent（结构化输出 + 三级降级）
  - graph: 图构建 + 流式执行入口
  - monitor: Agent 监控与日志系统

子 Agent:
  - chat:     闲聊/问候
  - parse:    需求解析（正则 + LLM 槽位提取）
  - normalize: 标准化（MySQL 字典映射）
  - alternatives: 替代料推荐（Neo4j + LLM 推理）
  - match:    供应商匹配（MySQL 查询 + 评分排序）
  - gen_rfq:  询价单生成（模板填充）
  - grade:    线索分级（规则评分）

工具:
  - regex_utils: 型号正则提取
  - mysql_client: MySQL 字典/供应商查询（@tool 装饰）
  - neo4j_client: Neo4j 替代料图查询（@tool 装饰）
  - milvus_client: Milvus 向量检索（@tool 装饰）
"""

from ai.base_agent import get_agent_llm, get_supervisor_llm, run_tool_agent, run_direct_agent
from ai.config import (
    LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_MODEL_LIGHT, SUPERVISOR_MODEL,
    DASHSCOPE_API_KEY, MYSQL_URL, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD,
    MILVUS_HOST, MILVUS_PORT, REDIS_URL,
)
from ai.state import ProcureState, Alternative, Supplier, LeadGrade
from ai.supervisor import route, RouteDecision, AGENT_META, ROUTING_ORDER
from ai.graph import get_graph, build_graph, init_state, run_procure_stream, _AGENT_MAP