"""
MatchForge AI 配置
从 .env 加载，所有默认值与 deploy/docker-compose.yml 严格对齐

数据源优先级: .env 环境变量 > 默认值(与 docker-compose 一致)
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 从项目根目录加载 .env
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")

# ============================================================
# LLM 配置 (通义千问 DashScope / OpenAI 兼容)
# ============================================================
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
LLM_API_KEY = DASHSCOPE_API_KEY  # 统一命名别名，兼容 ecs_assistant 风格
LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)
LLM_MODEL = os.getenv("LLM_MODEL", "qwen-max")                # 高推理: parse / alternatives
LLM_MODEL_LIGHT = os.getenv("LLM_MODEL_LIGHT", "qwen-plus")   # 轻量: normalize / match / gen_rfq / grade
SUPERVISOR_MODEL = os.getenv("SUPERVISOR_MODEL", "qwen-plus") # 路由专用轻量模型
# 兼容 OpenAI SDK 自动读取 OPENAI_API_KEY
if LLM_API_KEY and not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = LLM_API_KEY

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-v3")

# LLM 调用参数
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2048"))
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "30"))

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

# ============================================================
# MinIO — 对象存储 (Datasheet PDF / 证照 / Milvus 内部存储)
# docker-compose: minio:9000 (API) / 9001 (Console)
#   MINIO_ROOT_USER=minioadmin, MINIO_ROOT_PASSWORD=minioadmin123
# ============================================================
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "matchforge")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

# ============================================================
# 可观测 (可选)
# ============================================================
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")


# ============================================================
# 连接状态检查 (开发调试用)
# ============================================================
def print_config():
    """打印当前配置 (隐藏敏感信息)"""
    print("=" * 50)
    print("MatchForge AI 配置")
    print("=" * 50)
    print(f"LLM:       {LLM_MODEL} (heavy) / {LLM_MODEL_LIGHT} (light)")
    print(f"LLM URL:   {LLM_BASE_URL}")
    print(f"MySQL:     {MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE} (user={MYSQL_USER})")
    print(f"Milvus:    {MILVUS_HOST}:{MILVUS_PORT}")
    print(f"Neo4j:     {NEO4J_URI} (user={NEO4J_USER})")
    print(f"Redis:     {REDIS_HOST}:{REDIS_PORT}")
    print(f"MinIO:     {MINIO_ENDPOINT} (bucket={MINIO_BUCKET})")
    print(f"LangFuse:  {'enabled' if LANGFUSE_PUBLIC_KEY else 'disabled'}")
    print("=" * 50)


def check_connections() -> dict[str, bool]:
    """
    快速检查各服务连接状态
    返回: {service_name: is_healthy}
    """
    results = {}

    # MySQL
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(MYSQL_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        results["mysql"] = True
    except Exception:
        results["mysql"] = False

    # Redis
    try:
        import redis
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD,
                        socket_connect_timeout=3)
        r.ping()
        results["redis"] = True
    except Exception:
        results["redis"] = False

    # Neo4j
    try:
        from neo4j import GraphDatabase
        with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
            driver.verify_connectivity()
        results["neo4j"] = True
    except Exception:
        results["neo4j"] = False

    # Milvus
    try:
        from pymilvus import connections
        connections.connect(host=MILVUS_HOST, port=MILVUS_PORT, timeout=5)
        connections.disconnect("default")
        results["milvus"] = True
    except Exception:
        results["milvus"] = False

    # MinIO
    try:
        from minio import Minio
        client = Minio(MINIO_ENDPOINT, access_key=MINIO_ACCESS_KEY,
                       secret_key=MINIO_SECRET_KEY, secure=MINIO_SECURE)
        client.list_buckets()
        results["minio"] = True
    except Exception:
        results["minio"] = False

    return results