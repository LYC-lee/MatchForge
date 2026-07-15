"""
MatchForge API — FastAPI 应用入口
启动: uvicorn api.main:app --reload --port 8000
"""

import sys
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.config import APP_NAME, APP_VERSION, CORS_ORIGINS, MOCK_MODE
from api.database import init_db, engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", stream=sys.stdout)
logger = logging.getLogger(__name__)

app = FastAPI(title=APP_NAME, version=APP_VERSION, docs_url="/docs", redoc_url="/redoc")

app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def on_startup():
    logger.info(f"Starting {APP_NAME} v{APP_VERSION}, mock={MOCK_MODE}")
    try:
        await init_db()
        logger.info("DB initialized")
    except Exception as e:
        logger.error(f"DB init error: {e}")


@app.on_event("shutdown")
async def on_shutdown():
    await engine.dispose()
    logger.info("Shutdown")


@app.exception_handler(Exception)
async def global_handler(request: Request, exc: Exception):
    logger.error(f"Error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": str(exc)})


from api.routes.health import router as health_router
from api.routes.procure import router as procure_router
from api.routes.agents import router as agents_router
from api.routes.auth import router as auth_router
from api.routes.suppliers import router as suppliers_router
from api.routes.rfq import router as rfq_router
from api.routes.leads import router as leads_router
from api.routes.admin import router as admin_router

app.include_router(health_router)
app.include_router(procure_router)
app.include_router(agents_router)
app.include_router(auth_router)
app.include_router(suppliers_router)
app.include_router(rfq_router)
app.include_router(leads_router)
app.include_router(admin_router)


@app.get("/")
async def root():
    return {"name": APP_NAME, "version": APP_VERSION, "mock_mode": MOCK_MODE}
