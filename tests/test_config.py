"""
测试 config.py — 配置加载与连接检查
"""

import os
from unittest.mock import patch
from ai import config


def test_config_has_defaults():
    """config 有合理的默认值"""
    assert config.LLM_MODEL == "qwen-max"
    assert config.LLM_MODEL_LIGHT == "qwen-plus"
    assert config.MYSQL_HOST == "localhost"
    assert config.MYSQL_PORT == 3306
    assert config.MILVUS_HOST == "localhost"
    assert config.NEO4J_URI == "bolt://localhost:7687"
    assert config.REDIS_HOST == "localhost"


def test_config_print(capsys):
    """print_config 不报错"""
    config.print_config()
    captured = capsys.readouterr()
    assert "MatchForge AI 配置" in captured.out


def test_check_connections_all_fail():
    """所有服务不可用时返回 False（不抛异常）"""
    with patch("sqlalchemy.create_engine") as mock_engine:
        mock_engine.side_effect = Exception("Connection refused")
        with patch("redis.Redis") as mock_redis:
            mock_redis.side_effect = Exception("Connection refused")
            with patch("neo4j.GraphDatabase.driver") as mock_driver:
                mock_driver.side_effect = Exception("Connection refused")
                with patch("pymilvus.connections.connect") as mock_milvus:
                    mock_milvus.side_effect = Exception("Connection refused")
                    with patch("minio.Minio") as mock_minio:
                        mock_minio.side_effect = Exception("Connection refused")
                        results = config.check_connections()

    assert results["mysql"] is False
    assert results["redis"] is False
    assert results["neo4j"] is False
    assert results["milvus"] is False
    assert results["minio"] is False