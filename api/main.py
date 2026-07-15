"""
MatchForge 知识库 API 主入口 (FastAPI)。

路由:
  /api/v1/auth         - 登录 / 当前用户
  /api/v1/companies    - 公司列表 / 详情 / 知识状态 / 产品
  /api/v1/chat         - 单公司问答 / 多公司比较 / Trace
  /api/v1/admin/kb     - 知识生成 / 增量 / 重建 / 任务 / 统计
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from kb.config import CORS_ORIGINS
from kb.db import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("api")


def create_app() -> FastAPI:
    init_db()
    app = FastAPI(title="MatchForge Knowledge Base API", version="1.0.0")

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

    from api.routers import auth, chat, companies, kb_admin

    api_prefix = "/api/v1"
    app.include_router(auth.router, prefix=api_prefix)
    app.include_router(companies.router, prefix=api_prefix)
    app.include_router(chat.router, prefix=api_prefix)
    app.include_router(kb_admin.router, prefix=api_prefix)

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
