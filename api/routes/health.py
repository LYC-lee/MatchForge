from fastapi import APIRouter

router = APIRouter(tags=["健康检查"])


@router.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "MatchForge API",
        "version": "0.2.0",
    }
