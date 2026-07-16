"""
数据库引擎与会话管理
默认使用 SQLite（零依赖启动），配置 DATABASE_URL 可切 MySQL
"""

import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from api.config import DATABASE_URL

logger = logging.getLogger(__name__)

engine = create_async_engine(DATABASE_URL, echo=False)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    """FastAPI 依赖注入：获取数据库会话"""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """创建所有表并写入种子数据"""
    from api.base import Base
    # 必须先导入模型，让它们在 Base.metadata 上注册
    from api.models import User, Supplier, RFQ, Lead, AuditRecord  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 种子数据
    from sqlalchemy import select
    from api.auth import hash_password

    async with async_session_factory() as session:
        # 演示用户
        r = await session.execute(select(User).where(User.username == "demo@matchforge.ai"))
        if not r.scalar_one_or_none():
            session.add(User(
                username="demo@matchforge.ai",
                email="demo@matchforge.ai",
                password_hash=hash_password("demo12345"),
                name="Demo Buyer",
                company="MatchForge Demo", role="buyer",
            ))

        # 演示供应商
        r = await session.execute(select(Supplier).limit(1))
        if not r.scalar_one_or_none():
            for s_data in [
                ("深圳华强电子·恒达元器件", "深圳", 0.86),
                ("上海赛格集成电路", "上海", 0.82),
                ("苏州芯源微电子", "苏州", 0.74),
            ]:
                session.add(Supplier(name=s_data[0], location=s_data[1], region=f"华南·{s_data[1]}" if s_data[1]=="深圳" else f"华东·{s_data[1]}", match_score=s_data[2]))
        await session.commit()
    logger.info("[OK] 数据库初始化 + 种子数据完成")
