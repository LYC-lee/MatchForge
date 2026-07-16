"""
MatchForge 工具层

模块:
  - regex_utils:      型号正则提取
  - mysql_client:     MySQL 字典/供应商查询 (已 @tool 装饰，LLM 可自主调用)
  - neo4j_client:     Neo4j 替代料图查询 (已 @tool 装饰，LLM 可自主调用)
  - milvus_client:    Milvus 向量检索
  - kb_client:        企业知识库查询 (已 @tool 装饰，LLM 可自主调用，内部调用 kb/rag 实现)
"""

from ai.tools.regex_utils import (
    extract_part_number,
    extract_part_number_with_brand,
    validate_package,
    validate_temp_coeff,
)
from ai.tools.mysql_client import (
    lookup_std_code,           # @tool 装饰版，LLM 可自主调用
    lookup_std_code_raw,       # 原始 dict 参数版，兼容旧代码
    filter_suppliers,          # @tool 装饰版，LLM 可自主调用
    filter_suppliers_raw,      # 原始 list 参数版，兼容旧代码
    get_engine,
)
from ai.tools.neo4j_client import (
    query_all_alternatives,        # @tool 装饰，LLM 可自主调用（主入口）
    query_direct_equivalents,      # @tool 装饰，LLM 可自主调用
    query_transitive_equivalents,  # @tool 装饰，LLM 可自主调用
    query_cross_refs,              # @tool 装饰，LLM 可自主调用
    get_driver,
)
from ai.tools.milvus_client import (
    search_products,
    connect_milvus,
)
from ai.tools.kb_client import (
    search_knowledge_base,     # @tool 装饰版，LLM 可自主调用
)

__all__ = [
    # regex_utils
    "extract_part_number", "extract_part_number_with_brand",
    "validate_package", "validate_temp_coeff",
    # mysql_client
    "lookup_std_code", "lookup_std_code_raw",
    "filter_suppliers", "filter_suppliers_raw", "get_engine",
    # neo4j_client
    "query_all_alternatives",
    "query_direct_equivalents", "query_transitive_equivalents", "query_cross_refs",
    "get_driver",
    # milvus_client
    "search_products", "connect_milvus",
    # kb_client
    "search_knowledge_base",
]