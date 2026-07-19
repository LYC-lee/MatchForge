"""
知识库查询工具 — Agent → RAG 的单向桥梁。

让 Agent (ai/) 在 ReAct 循环中能自主调用 RAG 系统 (kb/)，
查询指定企业的产品知识、公司介绍、业务范围等信息。

设计原则：
- 单向依赖：ai → kb，kb 完全不依赖 ai（未引入任何 ai 模块）
- 懒加载：kb 模块只在首次调用时 import，避免模块级依赖
- 容错：kb 不可用或查询失败时返回清晰提示，不影响 Agent 整体流程
- 缓存：company_name → company_id 映射在进程内缓存，避免重复查库
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# 进程内缓存：company_name → company_id
# 避免同一 Agent 执行中多次查询同一公司时重复查数据库
_company_name_cache: dict[str, int] = {}


# ============================================================
# 公司名称 → company_id 解析
# ============================================================

def _resolve_company_id(company_name: str) -> int | None:
    """根据公司名称匹配到 kb_companies 中的 company_id。

    匹配策略（优先级递减）：
    1. 精确匹配 CompanyCache.name
    2. 模糊匹配（名称中包含查询串）
    3. 匹配别名 name_alias
    """
    # 缓存命中
    if company_name in _company_name_cache:
        return _company_name_cache[company_name]

    # 懒加载 kb 模块（避免模块级依赖）
    try:
        from kb.db import session_scope
        from kb.models import CompanyCache
    except ImportError as e:
        logger.warning("kb 模块不可用，无法解析公司 ID: %s", e)
        return None

    try:
        with session_scope() as s:
            c = None
            # 1. 精确匹配中文名
            c = s.query(CompanyCache).filter(CompanyCache.name == company_name).first()
            if not c:
                # 1b. 精确匹配英文名
                c = s.query(CompanyCache).filter(CompanyCache.name_en == company_name).first()
            if not c:
                # 2. 模糊匹配（处理供应商名称不完全一致的情况）
                c = s.query(CompanyCache).filter(
                    CompanyCache.name.like(f"%{company_name}%")
                ).first()
            if not c:
                # 3. 别名匹配
                c = s.query(CompanyCache).filter(
                    CompanyCache.name_alias.like(f"%{company_name}%")
                ).first()

            if c:
                _company_name_cache[company_name] = c.id
                return c.id
    except Exception as e:
        logger.warning("解析公司 ID 异常: %s", str(e)[:200])

    return None


# ============================================================
# 知识库查询工具（@tool 装饰，LLM 可自主调用）
# ============================================================

@tool
def search_knowledge_base(company_name: str, query: str) -> str:
    """查询指定企业的知识库，获取产品规格、公司介绍、业务范围等信息。

    当你需要了解某家企业的详细信息时使用此工具，例如：
    - 查询供应商的主营产品系列和型号
    - 了解企业的业务范围和能力
    - 获取产品参数、规格说明
    - 查看企业资质和认证信息

    用法示例：
      search_knowledge_base(company_name="深圳华强电子", query="主营产品有哪些")
      search_knowledge_base(company_name="Murata", query="MLCC 产品线有哪些系列")

    Args:
        company_name: 企业名称，如 "深圳华强电子"、"Murata"
        query: 查询问题，如 "主营产品是什么"、"有哪些产品型号"

    Returns:
        企业知识库中与查询相关的信息文本。
        若知识库中无相关信息，返回明确提示。
    """
    # 懒加载 RAG 模块
    try:
        from kb.rag import answer
    except ImportError as e:
        logger.warning("kb.rag 模块不可用: %s", e)
        return "知识库系统当前不可用，无法查询企业信息"

    # 解析 company_id
    cid = _resolve_company_id(company_name)
    if cid is None:
        return (
            f"未在知识库中找到企业「{company_name}」的相关记录。\n"
            f"可能原因：该企业尚未录入知识库，或企业名称与知识库中的名称不一致。"
        )

    # 调用 RAG 系统查询
    try:
        result = answer(query, company_id=cid, manual_type="product")
        if result and result.get("answer"):
            answer_text = result["answer"]
            # 对过长的回答做截断保护（LLM 上下文有限）
            if len(answer_text) > 2000:
                answer_text = answer_text[:2000] + "\n\n...（知识内容较长，已截断）"
            return answer_text
        return f"企业「{company_name}」的知识库中暂未收录与「{query}」相关的信息"
    except Exception as e:
        logger.warning("查询知识库时出错: %s", str(e)[:200])
        return f"查询「{company_name}」知识库时遇到错误，请稍后重试"
