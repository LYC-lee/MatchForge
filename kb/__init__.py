"""
MatchForge 企业私域知识库 (Company-Level RAG) 系统

在现有 MatchForge 项目基础上非破坏式扩展，为每家企业建设：
  - 产品知识库 (product)
  - 业务知识库 (business)
  - 中/英双语独立切片与向量索引
  - 严格 company_id 隔离的 RAG 问答

模块:
  config     - 配置 (复用 ai/config.py + KB 专属)
  db         - SQLAlchemy 引擎/会话 (SQLite 默认, 可切 MySQL)
  models     - ORM 模型 (KnowledgeManual / Product / KnowledgeChunk / KbTask / RagTrace)
  companies  - 公司源数据采集 (CSV 优先级2 / MySQL 优先级1)
  boundary   - 企业业务边界模型
  llm_client - OpenAI 兼容 LLM 客户端 (真实 + 降级)
  embedder   - Embedding 客户端 (真实 + 确定性降级)
  generator  - 双语知识生成 (产品 + 业务)
  chunker    - 语义切片
  vectorstore- 向量库抽象 (Milvus + Local)
  quality    - 质量校验
  tasks      - 轻量后台任务 (持久化/断点续跑/重试)
  rag        - RAG 管线 (语言检测/意图/检索/回答/Trace)
  pipeline   - 全流程编排
"""

__all__ = [
    "config",
    "db",
    "models",
]
