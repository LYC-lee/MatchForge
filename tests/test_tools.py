"""
测试 tools 层：regex_utils / neo4j_client / mysql_client / milvus_client
"""

import pytest
from unittest.mock import patch, MagicMock
from ai.tools import regex_utils


# ============================================================
# regex_utils
# ============================================================

class TestRegexUtils:
    def test_extract_taiyo_yuden(self):
        pn, brand = regex_utils.extract_part_number_with_brand("TMK212BJ105KG-T 缺货")
        assert pn == "TMK212BJ105KG-T"
        assert brand == "Taiyo Yuden"

    def test_extract_murata(self):
        pn, brand = regex_utils.extract_part_number_with_brand("寻找 GRM188R61A106KE69D 替代")
        assert pn == "GRM188R61A106KE69D"
        assert brand == "Murata"

    def test_extract_yageo(self):
        pn, brand = regex_utils.extract_part_number_with_brand("CC0805KKX7R9BB106")
        assert pn == "CC0805KKX7R9BB106"
        assert brand == "YAGEO"

    def test_extract_no_match(self):
        pn, brand = regex_utils.extract_part_number_with_brand("找 MLCC 替代")
        assert pn is None
        assert brand is None

    def test_validate_package_valid(self):
        assert regex_utils.validate_package("0805") is True
        assert regex_utils.validate_package("0603") is True
        assert regex_utils.validate_package("0402") is True

    def test_validate_package_invalid(self):
        assert regex_utils.validate_package("9999") is False
        assert regex_utils.validate_package("") is False

    def test_validate_temp_coeff(self):
        assert regex_utils.validate_temp_coeff("X7R") is True
        assert regex_utils.validate_temp_coeff("C0G") is True
        assert regex_utils.validate_temp_coeff("invalid") is False


# ============================================================
# neo4j_client
# ============================================================

class TestNeo4jClient:
    def test_query_all_alternatives_empty(self):
        """Neo4j 无结果时返回空列表"""
        from ai.tools.neo4j_client import query_all_alternatives
        with patch("ai.tools.neo4j_client.get_driver") as mock_driver:
            mock_session = MagicMock()
            mock_session.run.return_value = []
            mock_driver.return_value.session.return_value.__enter__.return_value = mock_session
            result = query_all_alternatives("NONEXISTENT")
            assert result == []


# ============================================================
# mysql_client
# ============================================================

class TestMysqlClient:
    def test_lookup_std_code_not_found(self):
        """字典未命中时返回 None"""
        from ai.tools.mysql_client import lookup_std_code
        with patch("ai.tools.mysql_client.get_engine") as mock_engine:
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = None
            mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn
            result = lookup_std_code({"category": "MLCC"})
            assert result is None


# ============================================================
# milvus_client
# ============================================================

class TestMilvusClient:
    def test_search_products(self):
        """Milvus 向量搜索接口可调用"""
        from ai.tools.milvus_client import connect_milvus, search_products
        with patch("ai.tools.milvus_client.connections.connect"):
            with patch("ai.tools.milvus_client.Collection") as MockCollection:
                mock_col = MagicMock()
                MockCollection.return_value = mock_col
                mock_search_result = MagicMock()
                mock_search_result.score = 0.95
                mock_search_result.entity.get.side_effect = lambda k: {
                    "product_id": "P001", "category": "MLCC",
                    "brand": "YAGEO", "part_number": "CC0805KKX7R9BB106",
                }[k]
                mock_col.search.return_value = [[mock_search_result]]

                results = search_products([0.1] * 1024, top_k=5)
                assert len(results) == 1
                assert results[0]["product_id"] == "P001"