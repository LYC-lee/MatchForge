"""
MatchForge AI 配置
从 .env 加载，所有默认值与 deploy/docker-compose.yml 严格对齐

LLM 提供商: 火山方舟 Coding Plan (OpenAI 兼容)
Embedding:  SiliconFlow BAAI/bge-m3
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 从项目根目录加载 .env
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")

# ============================================================
# LLM 配置 (OpenAI 兼容接口)
# ============================================================
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
LLM_API_KEY = DASHSCOPE_API_KEY  # 统一命名别名
LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL",
    "https://ark.cn-beijing.volces.com/api/coding/v3",
)
LLM_MODEL = os.getenv("LLM_MODEL", "glm-5.2")
LLM_MODEL_LIGHT = os.getenv("LLM_MODEL_LIGHT", "glm-5.2")
SUPERVISOR_MODEL = os.getenv("SUPERVISOR_MODEL", "glm-5.2")

# 兼容 OpenAI SDK 自动读取 OPENAI_API_KEY
if LLM_API_KEY and not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = LLM_API_KEY

# Embedding 配置
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "https://api.siliconflow.cn/v1")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))

# LLM 调用参数
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2048"))
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "120"))

# ============================================================
# MySQL 8.0 — 业务主库
# docker-compose: mysql:3306, user=matchforge, password=matchforge123, db=matchforge
# ============================================================
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "matchforge")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "matchforge123")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", os.getenv("MYSQL_DB", "matchforge"))
MYSQL_URL = (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
    f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
    f"?charset=utf8mb4"
)

# ============================================================
# PostgreSQL 16 — 长期记忆库 (AgentMemory)
# docker-compose: postgres:5432, user=matchforge, password=matchforge123, db=matchforge_memory
# ============================================================
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "matchforge")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "matchforge123")
POSTGRES_DATABASE = os.getenv("POSTGRES_DATABASE", "matchforge_memory")
POSTGRESQL_URL = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DATABASE}"
)

# ============================================================
# Milvus 2.4 — 向量数据库 (Standalone)
# docker-compose: milvus:19530 (gRPC) / 9091 (health)
# 依赖: etcd:2379 + minio:9000
# ============================================================
MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))
MILVUS_COLLECTION_PRODUCTS = "product_embeddings"
MILVUS_COLLECTION_KNOWLEDGE = "knowledge_chunks"

# ============================================================
# Neo4j 5.20 — 知识图谱 (替代料交叉引用)
# docker-compose: neo4j:7474 (HTTP) / 7687 (Bolt)
#   NEO4J_AUTH=neo4j/matchforge123
# ============================================================
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "matchforge123")

# ============================================================
# Redis 7 — 缓存 / 会话 / 限流
# docker-compose: redis:6379, password=matchforge123
# ============================================================
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "matchforge123")
REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0"