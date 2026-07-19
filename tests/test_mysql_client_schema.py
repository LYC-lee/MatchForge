"""
测试 mysql_client.py 的 filter_suppliers_raw 函数。

验证:
1. 查询不包含死字段 (s.category, s.brand_coverage, s.moq, s.lead_time_weeks, s.data_source)
2. 查询使用 JOIN supplier_capabilities 获取品类/品牌信息
3. filter_suppliers_raw('MLCC') 能正常执行 (不要求有数据, 只要不报列不存在错误)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, MagicMock
from ai.tools.mysql_client import filter_suppliers_raw, lookup_std_code_raw


def test_filter_suppliers_no_dead_fields():
    """验证 SQL 中不包含死字段。"""
    # 捕获实际执行的 SQL
    captured_sql = []

    class FakeResult:
        def __iter__(self):
            return iter([])
        def fetchall(self):
            return []
        def fetchone(self):
            return None

    class FakeConn:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def execute(self, query, params=None):
            captured_sql.append(str(query))
            return FakeResult()

    class FakeEngine:
        def connect(self):
            return FakeConn()

    with patch("ai.tools.mysql_client.get_engine", return_value=FakeEngine()):
        filter_suppliers_raw("MLCC")

    assert len(captured_sql) > 0
    sql_text = captured_sql[0].lower()

    # 死字段不应出现在 SQL 中
    dead_fields = [
        "s.category",           # 应该用 sc.category_name
        "s.brand_coverage",     # 应该用 sc.brand_names
        "s.moq",                # 应该用 sc.moq
        "s.lead_time_weeks",    # 应该用 sc.lead_time_days
        "s.data_source",        # 应该用 sc.source_name 或不查
    ]
    for field in dead_fields:
        assert field not in sql_text, f"死字段 {field} 仍在 SQL 中: {sql_text}"

    # 应该 JOIN supplier_capabilities
    assert "supplier_capabilities" in sql_text, "SQL 应该 JOIN supplier_capabilities 表"


def test_filter_suppliers_raw_with_brands():
    """验证品牌过滤参数化 SQL。"""
    captured_params = []

    class FakeResult:
        def __iter__(self):
            return iter([])
        def fetchall(self):
            return []
        def fetchone(self):
            return None

    class FakeConn:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def execute(self, query, params=None):
            captured_params.append(params)
            return FakeResult()

    class FakeEngine:
        def connect(self):
            return FakeConn()

    with patch("ai.tools.mysql_client.get_engine", return_value=FakeEngine()):
        filter_suppliers_raw("MLCC", brands=["Murata", "YAGEO"])

    assert len(captured_params) > 0
    params = captured_params[0]
    assert "brand_0" in params, "品牌参数应使用 brand_0, brand_1 等"
    assert "Murata" in str(params.values())
    assert "YAGEO" in str(params.values())


def test_filter_suppliers_raw_returns_list():
    """验证返回类型是 list[dict]。"""
    class FakeResult:
        def __iter__(self):
            return iter([])
        def fetchall(self):
            return []
        def fetchone(self):
            return None

    class FakeConn:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def execute(self, query, params=None):
            return FakeResult()

    class FakeEngine:
        def connect(self):
            return FakeConn()

    with patch("ai.tools.mysql_client.get_engine", return_value=FakeEngine()):
        result = filter_suppliers_raw("MLCC")

    assert isinstance(result, list)


if __name__ == "__main__":
    # 简单测试运行器 (无 pytest 依赖)
    import traceback
    tests = [
        test_filter_suppliers_no_dead_fields,
        test_filter_suppliers_raw_with_brands,
        test_filter_suppliers_raw_returns_list,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*40}")
    print(f"结果: {passed} 通过, {failed} 失败")
    exit(0 if failed == 0 else 1)
