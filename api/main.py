"""
MatchForge API 主入口 (FastAPI)
寻源 Agent 接口

路由:
  /api/v1/procure/stream  — SSE 流式多 Agent 寻源
  /api/v1/procure/spec    — 解析 + 标准化
  /api/v1/procure/match   — 替代料 + 供应商匹配
  /api/v1/procure/health  — Agent 状态检查
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("api")

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173")


def create_app() -> FastAPI:
    app = FastAPI(title="MatchForge Procurement API", version="1.0.0")

    origins = [o.strip() for o in (CORS_ORIGINS or "").split(",") if o.strip()]
    if not origins:
        origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from api.routers import procure

    api_prefix = "/api/v1"
    app.include_router(procure.router, prefix=api_prefix)

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok"}

    return app


main = create_app()


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run("api.main:main", host=host, port=port, reload=False)