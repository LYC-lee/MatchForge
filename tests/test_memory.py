"""
测试 memory.py — 用户记忆工具
"""

from unittest.mock import patch, MagicMock
from ai.memory import get_user_memory_snapshot


def test_get_user_memory_snapshot_no_user():
    """无记忆时返回空 dict"""
    with patch("ai.memory._get_engine") as mock_engine:
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn
        result = get_user_memory_snapshot("nonexistent")
        assert result == {}


def test_get_user_memory_snapshot_with_data():
    """有记忆时返回正确数据"""
    with patch("ai.memory._get_engine") as mock_engine:
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = [
            ("brand_pref", '["YAGEO", "Murata"]'),
            ("settings", '{"region": "深圳"}'),
        ]
        mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn
        result = get_user_memory_snapshot("user-001")
        assert result.get("brand_pref") == ["YAGEO", "Murata"]
        assert result.get("settings") == {"region": "深圳"}


def test_get_user_memory_snapshot_engine_none():
    """引擎创建失败返回空"""
    with patch("ai.memory._get_engine", return_value=None):
        result = get_user_memory_snapshot("user-001")
        assert result == {}


def test_get_user_memory_snapshot_db_error():
    """数据库错误时返回空"""
    with patch("ai.memory._get_engine") as mock_engine:
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = Exception("DB error")
        mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn
        result = get_user_memory_snapshot("user-001")
        assert result == {}