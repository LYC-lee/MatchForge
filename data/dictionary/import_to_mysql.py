#!/usr/bin/env python3
"""
MatchForge - 标准字典 JSON → MySQL 导入脚本
读取 data/dictionary/dictionary.json 并导入 material_dictionary 表

用法:
    python3 data/dictionary/import_to_mysql.py

环境变量（从 .env 读取或手动设置）:
    MYSQL_HOST=127.0.0.1
    MYSQL_PORT=3306
    MYSQL_USER=root
    MYSQL_PASSWORD=
    MYSQL_DATABASE=matchforge
"""

import json
import os
import sys
from pathlib import Path

try:
    import pymysql
except ImportError:
    print("❌ 缺少依赖: pymysql")
    print("   安装: pip install pymysql")
    sys.exit(1)


# ── 路径配置 ──
SCRIPT_DIR = Path(__file__).resolve().parent
JSON_PATH = SCRIPT_DIR / "dictionary.json"
ENV_PATH = SCRIPT_DIR.parent.parent / ".env"


def load_env():
    """从 .env 文件加载环境变量（如果存在）"""
    if not ENV_PATH.exists():
        return
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # 仅设置未在环境中已有的变量
                if key not in os.environ:
                    os.environ[key] = value


def get_mysql_config():
    """获取 MySQL 连接配置"""
    return {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "matchforge"),
        "charset": "utf8mb4",
    }


def load_dictionary():
    """读取 dictionary.json"""
    if not JSON_PATH.exists():
        print(f"❌ 字典文件不存在: {JSON_PATH}")
        sys.exit(1)

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("items", [])
    if not items:
        print("❌ 字典文件中没有数据项 (items 为空)")
        sys.exit(1)

    return items


def import_to_mysql(items, config):
    """将字典数据导入 MySQL material_dictionary 表"""
    print(f"🔗 连接 MySQL: {config['user']}@{config['host']}:{config['port']}/{config['database']}")

    try:
        conn = pymysql.connect(**config)
    except pymysql.err.OperationalError as e:
        print(f"❌ MySQL 连接失败: {e}")
        print("   请检查 MySQL 是否已启动，以及 .env 中的连接配置是否正确")
        sys.exit(1)

    cursor = conn.cursor()

    # 确保表存在（幂等，与 mysql_schema.sql 保持一致）
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS material_dictionary (
        std_code VARCHAR(100) PRIMARY KEY COMMENT '标准编码 如 MLCC-0805-X7R-50V-103',
        category VARCHAR(50) NOT NULL COMMENT '品类（中文）',
        params JSON COMMENT '参数（中文键名）',
        standard VARCHAR(100) COMMENT '标准 GB/IEC/EIA/JIS',
        description TEXT COMMENT '中文描述',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='标准物料字典表';
    """
    cursor.execute(create_table_sql)
    print("✅ 表 material_dictionary 已就绪")

    # 使用 REPLACE INTO 实现幂等导入（重复运行不会报错，会覆盖已有记录）
    insert_sql = """
        REPLACE INTO material_dictionary (std_code, category, params, standard, description)
        VALUES (%s, %s, %s, %s, %s)
    """

    inserted = 0
    errors = 0

    for item in items:
        std_code = item.get("std_code", "")
        category = item.get("category", "")
        params = json.dumps(item.get("params", {}), ensure_ascii=False)
        standard = item.get("standard", "")
        description = item.get("description", "")

        if not std_code or not category:
            print(f"  ⚠️ 跳过无效记录（缺少 std_code 或 category）: {item}")
            errors += 1
            continue

        try:
            cursor.execute(insert_sql, (std_code, category, params, standard, description))
            inserted += 1
        except pymysql.Error as e:
            print(f"  ❌ 导入失败 [{std_code}]: {e}")
            errors += 1

    conn.commit()

    # 统计各品类数量
    cursor.execute(
        "SELECT category, COUNT(*) as cnt FROM material_dictionary GROUP BY category ORDER BY cnt DESC"
    )
    stats = cursor.fetchall()

    cursor.close()
    conn.close()

    # 输出结果
    print(f"\n{'='*50}")
    print(f"✅ 导入完成!")
    print(f"   成功: {inserted} 条")
    if errors:
        print(f"   失败: {errors} 条")
    print(f"{'='*50}")
    print(f"\n📊 各品类统计:")
    for cat, cnt in stats:
        print(f"   {cat}: {cnt} 条")


def main():
    print("╔══════════════════════════════════════════════╗")
    print("║  MatchForge 标准字典导入工具                 ║")
    print("║  dictionary.json → MySQL                    ║")
    print("╚══════════════════════════════════════════════╝\n")

    # 1. 加载环境变量
    load_env()

    # 2. 读取 JSON
    print(f"📄 读取字典文件: {JSON_PATH}")
    items = load_dictionary()
    print(f"   共 {len(items)} 条记录\n")

    # 3. 获取 MySQL 配置
    config = get_mysql_config()

    # 4. 导入
    import_to_mysql(items, config)


if __name__ == "__main__":
    main()
