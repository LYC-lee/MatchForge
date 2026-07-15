"""
MatchForge API 主入口 (FastAPI)
寻源 Agent + 知识库 + 企业驾驶舱上下文 + 上下游协同

路由:
  /api/v1/procure/*              - SSE 流式多 Agent 寻源 / 解析 / 匹配
  /api/v1/auth/*                 - 登录 / 当前用户
  /api/v1/companies/*            - 公司 / 知识 / 产品 / 上下游关系 / 协同问答
  /api/v1/chat/*                 - 单公司 RAG / 多公司比较 / Trace
  /api/v1/admin/kb/*             - 知识库管理 (生成 / 增量 / 重建 / 任务 / 统计)
  /api/v1/enterprise-context/*   - 当前企业驾驶舱上下文
  /api/v1/health                 - 健康检查
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

    # 确保知识库表 (含 kb_company_relationships) 已创建 (幂等)。
    # SQLite 自动建表; MySQL 需先执行 database/migrations/02_kb_schema.sql。
    from kb.db import init_db

    init_db()

    from api.routers import (
        auth,
        chat,
        companies,
        enterprise_context,
        kb_admin,
        relationships,
    )

    api_prefix = "/api/v1"
    # procure 依赖 langgraph; 未安装时优雅降级, 其余路由不受影响。
    # 生产环境安装 langgraph 后 procure 自动恢复 (保留现有寻源接口)。
    try:
        from api.routers import procure as _procure_mod

        app.include_router(_procure_mod.router, prefix=api_prefix)
    except ImportError as e:
        logger.warning("procure 路由不可用 (缺少依赖 langgraph?): %s", e)

    app.include_router(auth.router, prefix=api_prefix)
    app.include_router(companies.router, prefix=api_prefix)
    app.include_router(relationships.router, prefix=api_prefix)
    app.include_router(chat.router, prefix=api_prefix)
    app.include_router(kb_admin.router, prefix=api_prefix)
    app.include_router(enterprise_context.router, prefix=api_prefix)

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
