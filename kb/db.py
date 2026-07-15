"""
SQLAlchemy 引擎/会话工厂。

- 默认 SQLite (data/knowledge.db)，当前环境无 Docker/MySQL 仍可运行
- 设置 KB_DATABASE_URL=mysql+pymysql://... 即可切 MySQL (与 ai/config.py 对齐)
- 独立库/独立文件 -> 非破坏式，不触碰现有业务表
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker, declarative_base

from kb.config import KB_DATABASE_URL

Base = declarative_base()

_engine = None
_SessionLocal = None
_lock = threading.Lock()


def _build_engine():
    url = KB_DATABASE_URL
    is_sqlite = url.startswith("sqlite")
    kwargs = {"pool_pre_ping": True, "future": True}
    if is_sqlite:
        # SQLite 文件目录确保存在
        db_path = url.replace("sqlite:///", "")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        kwargs = {"future": True}
    eng = create_engine(url, **kwargs)

    # SQLite 开启外键约束
    if is_sqlite:

        @event.listens_for(eng, "connect")
        def _fk_on(dbapi_conn, _):  # pragma: no cover
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=5000")  # 写冲突时等待 5s 而非立即失败
            cur.close()

    return eng


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
