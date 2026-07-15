"""
MatchForge 工具层

模块:
  - regex_utils:    型号正则提取
  - mysql_client:    MySQL 字典/供应商查询
  - neo4j_client:    Neo4j 替代料图查询
  - milvus_client:   Milvus 向量检索
"""

from ai.tools.regex_utils import (
    extract_part_number,
    extract_part_number_with_brand,
    validate_package,
    validate_temp_coeff,
)
from ai.tools.mysql_client import (
    lookup_std_code,
    lookup_std_code_raw,
    filter_suppliers,
    filter_suppliers_raw,
    get_engine,
)
from ai.tools.neo4j_client import (
    query_all_alternatives,
    query_direct_equivalents,
    query_transitive_equivalents,
    query_cross_refs,
    get_driver,
)
from ai.tools.milvus_client import (
    search_products,
    connect_milvus,
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
]