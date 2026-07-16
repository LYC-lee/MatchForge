"""
SQLAlchemy 引擎/会话工厂 — MySQL。
"""

from __future__ import annotations

import threading
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker, declarative_base

from kb.config import KB_DATABASE_URL

Base = declarative_base()

_engine = None
_SessionLocal = None
_lock = threading.Lock()


def _build_engine():
    return create_engine(KB_DATABASE_URL, pool_pre_ping=True, future=True)


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        with _lock:
            if _engine is None:
                _engine = _build_engine()
                _SessionLocal = sessionmaker(
                    bind=_engine, autoflush=False, autocommit=False,
                    future=True, expire_on_commit=False,
                )
    return _engine


def get_session() -> Session:
    return get_session_local()()


def get_session_local():
    if _SessionLocal is None:
        get_engine()
    return _SessionLocal


@contextmanager
def session_scope() -> Session:
    """事务作用域: 自动 commit/rollback/close。"""
    session = get_session_local()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """创建所有知识库表 (幂等)。"""
    from kb import models  # noqa: F401  确保模型已注册

    Base.metadata.create_all(get_engine())
