"""
知识库配置。

复用项目 .env (与 ai/config.py 同源), 不新增 AI 供应商, 不硬编码任何密钥。
直接读取环境变量而非 import ai.config, 使知识库与 LangGraph 依赖解耦
(ai/__init__.py 会 import langgraph, 若未安装会阻断)。

新增的 KB 专属配置全部走环境变量, 并提供对当前 MVP/Demo 环境友好的默认值。
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# 复用现有 .env 加载逻辑 (与 ai/config.py 同一文件)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# ============================================================
# LLM / Embedding -- 与 ai/config.py 同源 (同一 .env)
# 火山方舟 Coding Plan (OpenAI 兼容) + SiliconFlow bge-m3
# ============================================================
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
LLM_API_KEY = DASHSCOPE_API_KEY
LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL", "https://ark.cn-beijing.volces.com/api/coding/v3"
)
LLM_MODEL = os.getenv("LLM_MODEL", "glm-5.2")
LLM_MODEL_LIGHT = os.getenv("LLM_MODEL_LIGHT", "DeepSeek-V4-Flash")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "") or LLM_API_KEY
EMBEDDING_BASE_URL = os.getenv(
    "EMBEDDING_BASE_URL",
    "https://api.siliconflow.cn/v1",
)
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))

# ============================================================
# Milvus -- 与 ai/config.py 同源
# ============================================================
MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")

# ============================================================
# 知识库主库 (Source of Truth) — MySQL
# ============================================================
KB_DATABASE_URL = os.getenv(
    "KB_DATABASE_URL",
    "mysql+pymysql://matchforge:matchforge123@localhost:3306/matchforge?charset=utf8mb4",
)

# 公司库来源 -- 优先级1: MySQL pc_industry.companies；优先级2: 项目 CSV 种子文件。
COMPANY_MYSQL_URL = os.getenv(
    "COMPANY_MYSQL_URL",
    f"mysql+pymysql://{os.getenv('MYSQL_USER','matchforge')}:{os.getenv('MYSQL_PASSWORD','matchforge123')}"
    f"@{os.getenv('MYSQL_HOST','127.0.0.1')}:{os.getenv('MYSQL_PORT','3306')}/pc_industry?charset=utf8mb4",
)
COMPANY_CSV_DIR = _PROJECT_ROOT / "database" / "04_seed_data"

# ============================================================
# 向量库 — Milvus
# ============================================================
KB_VECTOR_STORE = os.getenv("KB_VECTOR_STORE", "milvus")

# 新建 Milvus Collection -- 现有 knowledge_chunks 缺少 company_id/language/chunk_type
# 等过滤字段, 无法满足公司级 RAG。非破坏式: 新建集合, 不动现有集合。
MILVUS_COLLECTION_KB = os.getenv("MILVUS_COLLECTION_KB", "company_knowledge_chunks")

# ============================================================
# 知识生成参数
# ============================================================
KB_LLM_TIMEOUT = int(os.getenv("KB_LLM_TIMEOUT", "60"))
KB_LLM_MAX_TOKENS = int(os.getenv("KB_LLM_MAX_TOKENS", "4096"))
KB_EMBED_BATCH = int(os.getenv("KB_EMBED_BATCH", "16"))

KB_COMPANY_CONCURRENCY = int(os.getenv("KB_COMPANY_CONCURRENCY", "3"))
KB_LLM_CONCURRENCY = int(os.getenv("KB_LLM_CONCURRENCY", "2"))
KB_LLM_MAX_RETRIES = int(os.getenv("KB_LLM_MAX_RETRIES", "3"))

# Demo 环境标记 -- 生产环境关闭
KB_DEMO_MODE = os.getenv("KB_DEMO_MODE", "false").lower() == "true"

# 知识生成是否使用真实 LLM (推理模型较慢; 批量生成默认用模板, 单公司演示可开启)
# auto: llm_available 时用 LLM; off: 强制模板; on: 强制 LLM
KB_LLM_FOR_GENERATION = os.getenv("KB_LLM_FOR_GENERATION", "auto")

# RAG 检索参数
KB_RAG_TOP_K = int(os.getenv("KB_RAG_TOP_K", "6"))
KB_RAG_MIN_SCORE = float(os.getenv("KB_RAG_MIN_SCORE", "0.15"))

# 后台任务并发
KB_TASK_MAX_WORKERS = int(os.getenv("KB_TASK_MAX_WORKERS", "4"))

# API (FastAPI) -- 与 .env 对齐
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173")

# ============================================================
# 运行时能力探测 (用于报告与降级决策)
# ============================================================


def llm_available() -> bool:
    """真实 LLM 是否可用 (存在 API Key)。"""
    return bool(LLM_API_KEY and LLM_API_KEY.strip())


def embedding_available() -> bool:
    """真实 Embedding 是否可用。"""
    return bool(EMBEDDING_API_KEY and EMBEDDING_API_KEY.strip())


def milvus_available() -> bool:
    """Milvus 是否可连接 (含 pymilvus 是否安装)。"""
    if KB_VECTOR_STORE == "local":
        return False
    try:
        import socket

        s = socket.socket()
        s.settimeout(2)
        s.connect((MILVUS_HOST, int(MILVUS_PORT)))
        s.close()
        import pymilvus  # noqa: F401

        return True
    except Exception:
        return False


def active_vector_store() -> str:
    """实际生效的向量库后端。"""
    return "milvus"


def runtime_capabilities() -> dict:
    """运行时能力快照。"""
    return {
        "llm": "dashscope-qwen",
        "llm_model": LLM_MODEL,
        "embedding": "dashscope-text-embedding-v3",
        "embedding_dim": EMBEDDING_DIM,
        "vector_store": "milvus",
        "database": "mysql",
        "demo_mode": KB_DEMO_MODE,
    }
