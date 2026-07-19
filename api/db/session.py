"""
MatchForge 双库 SQLAlchemy Session 工厂
=======================================
matchforge 运营库: 用户、认证、RFQ运营状态、线索
pc_industry 事实库: 公司、物料、替代关系、供应商能力、RFQ、报价

环境变量:
  MATCHFORGE_DATABASE_URL  - matchforge 运营库连接串
  PC_INDUSTRY_DATABASE_URL - pc_industry 事实库连接串
  MYSQL_HOST/MYSQL_PORT/MYSQL_USER/MYSQL_PASSWORD - 兼容旧配置

使用方式:
  from api.db.session import get_matchforge_session, get_pc_industry_session

  with get_matchforge_session() as s:
      ...
  with get_pc_industry_session() as s:
      ...
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# ── matchforge 运营库 ──
_matchforge_engine = None
_MatchforgeSessionLocal = None

# ── pc_industry 事实库 ──
_pc_industry_engine = None
_PcIndustrySessionLocal = None

_lock = threading.Lock()


def _build_matchforge_url() -> str:
    """获取 matchforge 运营库连接 URL"""
    url = os.getenv("MATCHFORGE_DATABASE_URL", "")
    if url:
        return url
    host = os.getenv("MYSQL_HOST", "localhost")
    port = os.getenv("MYSQL_PORT", "3306")
    user = os.getenv("MYSQL_USER", "matchforge")
    password = os.getenv("MYSQL_PASSWORD", "matchforge123")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/matchforge?charset=utf8mb4"


def _build_pc_industry_url() -> str:
    """获取 pc_industry 事实库连接 URL"""
    url = os.getenv("PC_INDUSTRY_DATABASE_URL", "")
    if url:
        return url
    host = os.getenv("MYSQL_HOST", "localhost")
    port = os.getenv("MYSQL_PORT", "3306")
    user = os.getenv("MYSQL_USER", "matchforge")
    password = os.getenv("MYSQL_PASSWORD", "matchforge123")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/pc_industry?charset=utf8mb4"


def get_matchforge_engine():
    """获取 matchforge 运营库 engine（懒加载单例）"""
    global _matchforge_engine, _MatchforgeSessionLocal
    if _matchforge_engine is None:
        with _lock:
            if _matchforge_engine is None:
                _matchforge_engine = create_engine(
                    _build_matchforge_url(),
                    pool_pre_ping=True,
                    pool_size=10,
                    max_overflow=20,
                    future=True,
                )
                _MatchforgeSessionLocal = sessionmaker(
                    bind=_matchforge_engine,
                    autoflush=False,
                    autocommit=False,
                    future=True,
                    expire_on_commit=False,
                )
    return _matchforge_engine


def get_pc_industry_engine():
    """获取 pc_industry 事实库 engine（懒加载单例）"""
    global _pc_industry_engine, _PcIndustrySessionLocal
    if _pc_industry_engine is None:
        with _lock:
            if _pc_industry_engine is None:
                _pc_industry_engine = create_engine(
                    _build_pc_industry_url(),
                    pool_pre_ping=True,
                    pool_size=10,
                    max_overflow=20,
                    future=True,
                )
                _PcIndustrySessionLocal = sessionmaker(
                    bind=_pc_industry_engine,
                    autoflush=False,
                    autocommit=False,
                    future=True,
                    expire_on_commit=False,
                )
    return _pc_industry_engine


def get_matchforge_session() -> Session:
    """获取 matchforge 运营库 Session"""
    if _MatchforgeSessionLocal is None:
        get_matchforge_engine()
    return _MatchforgeSessionLocal()


def get_pc_industry_session() -> Session:
    """获取 pc_industry 事实库 Session"""
    if _PcIndustrySessionLocal is None:
        get_pc_industry_engine()
    return _PcIndustrySessionLocal()


@contextmanager
def matchforge_scope() -> Generator[Session, None, None]:
    """matchforge 运营库事务作用域: 自动 commit/rollback/close"""
    session = get_matchforge_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def pc_industry_scope() -> Generator[Session, None, None]:
    """pc_industry 事实库事务作用域: 自动 commit/rollback/close"""
    session = get_pc_industry_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ── FastAPI 依赖注入 ──
def get_matchforge_db():
    """FastAPI 依赖: matchforge 运营库 Session"""
    session = get_matchforge_session()
    try:
        yield session
    finally:
        session.close()


def get_pc_industry_db():
    """FastAPI 依赖: pc_industry 事实库 Session"""
    session = get_pc_industry_session()
    try:
        yield session
    finally:
        session.close()
