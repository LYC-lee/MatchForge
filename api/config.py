"""
MatchForge API 配置
从 .env 加载，与 ai/config.py 共享同一来源
"""

import os
from pathlib import Path
from dotenv import load_dotenv

_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")

# ── 应用 ──
APP_NAME = "MatchForge API"
APP_VERSION = "0.2.0"
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# ── HTTP ──
HOST = os.getenv("API_HOST", "0.0.0.0")
PORT = int(os.getenv("API_PORT", "8000"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:5174").split(",")

# ── 数据库 (默认 SQLite，可切换 MySQL) ──
DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite+aiosqlite:///{_project_root / 'data' / 'app.db'}"
# 打印实际路径方便调试
import logging as _lg
_lg.getLogger(__name__).info(f"Database: {DATABASE_URL}")

# ── JWT ──
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "matchforge-dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24h
REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7d

# ── Mock 模式 ──
# 无 DASHSCOPE_API_KEY 时自动启用 mock
import ai.config as ai_config
MOCK_MODE = not bool(ai_config.DASHSCOPE_API_KEY)
