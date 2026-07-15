#!/usr/bin/env python3
"""
MatchForge - pc_industry 种子数据导入脚本
============================================
按 FK 顺序导入 database/04_seed_data/*.csv 到 pc_industry 数据库。

导入顺序（按外键依赖）:
  1. industry_segments  2. categories  3. companies  4. company_segments
  5. spec_definitions   6. parts       7. part_alternatives  8. suppliers
  9. supplier_capabilities  10. rfqs   11. rfq_suppliers  12. quotations
  13. data_sources

使用方式:
  python scripts/import_pc_industry_seed.py                     # 导入全部
  python scripts/import_pc_industry_seed.py --dry-run           # 仅预览不执行
  python scripts/import_pc_industry_seed.py --table parts       # 仅导入指定表
  python scripts/import_pc_industry_seed.py --clear             # 先清空再导入

环境变量（从 .env 读取）:
  PC_INDUSTRY_DATABASE_URL 或 MYSQL_HOST/MYSQL_PORT/MYSQL_USER/MYSQL_PASSWORD/MYSQL_DATABASE
"""

import argparse
import csv
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_DIR = PROJECT_ROOT / "database" / "04_seed_data"
ENV_PATH = PROJECT_ROOT / ".env"

# 导入顺序（按外键依赖）
IMPORT_ORDER = [
    ("01_industry_segments_seed.csv", "industry_segments"),
    ("03_categories_seed.csv", "categories"),
    ("02_companies_seed.csv", "companies"),
    ("09_company_segments_seed.csv", "company_segments"),
    ("08_spec_definitions_seed.csv", "spec_definitions"),
    ("04_parts_seed.csv", "parts"),
    ("06_part_alternatives_seed.csv", "part_alternatives"),
    ("05_suppliers_seed.csv", "suppliers"),
    ("10_supplier_capabilities_seed.csv", "supplier_capabilities"),
    ("07_rfqs_seed.csv", "rfqs"),
    ("12_rfq_suppliers_seed.csv", "rfq_suppliers"),
    ("13_quotations_seed.csv", "quotations"),
    ("11_data_sources_seed.csv", "data_sources"),
]


def load_env(filepath=ENV_PATH):
    """从 .env 文件加载环境变量"""
    if not filepath.exists():
        return
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip()
            if key and key not in os.environ:
                os.environ[key] = val


def get_db_config():
    """获取数据库连接配置"""
    db_url = os.environ.get("PC_INDUSTRY_DATABASE_URL", "")
    if db_url:
        # 解析 mysql+pymysql://user:pass@host:port/db
        parsed = urlparse(db_url)
        return {
            "host": parsed.hostname or "127.0.0.1",
            "port": parsed.port or 3306,
            "user": parsed.username or "root",
            "password": parsed.password or "",
            "database": parsed.path.lstrip("/") or "pc_industry",
        }
    return {
        "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.environ.get("MYSQL_PORT", "3306")),
        "user": os.environ.get("MYSQL_USER", "matchforge"),
        "password": os.environ.get("MYSQL_PASSWORD", "matchforge123"),
        "database": os.environ.get("PC_INDUSTRY_DATABASE", "pc_industry"),
    }


def read_csv(csv_path):
    """读取 CSV 文件，返回 (headers, rows)"""
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        headers = next(reader)
        rows = list(reader)
    return headers, rows


def get_connection(config):
    """获取 MySQL 连接"""
    try:
        import pymysql
    except ImportError:
        print("[错误] 请先安装 pymysql: pip install pymysql")
        sys.exit(1)

    try:
        conn = pymysql.connect(
            host=config["host"],
            port=config["port"],
            user=config["user"],
            password=config["password"],
            database=config["database"],
            charset="utf8mb4",
            autocommit=False,
        )
        return conn
    except Exception as e:
        print(f"[错误] MySQL 连接失败: {e}")
        print(f"  主机: {config['host']}:{config['port']}")
        print(f"  用户: {config['user']}")
        print(f"  数据库: {config['database']}")
        sys.exit(1)


def clear_table(cursor, table_name):
    """清空表数据（保留结构）"""
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    cursor.execute(f"TRUNCATE TABLE {table_name}")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")


def import_table(conn, cursor, csv_path, table_name, dry_run=False):
    """导入单个 CSV 到指定表"""
    if not csv_path.exists():
        print(f"  [跳过] CSV 不存在: {csv_path.name}")
        return 0

    headers, rows = read_csv(csv_path)
    if not rows:
        print(f"  [跳过] CSV 无数据: {csv_path.name}")
        return 0

    if dry_run:
        print(f"  [预览] {table_name}: {len(rows)} 行, 列: {', '.join(headers[:5])}...")
        return len(rows)

    # 构建 INSERT 语句
    columns = ", ".join(f"`{h}`" for h in headers)
    placeholders = ", ".join("%s" for _ in headers)
    sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"

    try:
        cursor.executemany(sql, rows)
        print(f"  [成功] {table_name}: {len(rows)} 行")
        return len(rows)
    except Exception as e:
        print(f"  [失败] {table_name}: {e}")
        conn.rollback()
        return 0


def main():
    parser = argparse.ArgumentParser(description="导入 pc_industry 种子数据")
    parser.add_argument("--dry-run", action="store_true", help="仅预览不执行")
    parser.add_argument("--table", type=str, help="仅导入指定表")
    parser.add_argument("--clear", action="store_true", help="导入前清空表数据")
    args = parser.parse_args()

    load_env()
    config = get_db_config()

    print("=" * 60)
    print("  pc_industry 种子数据导入工具")
    print("=" * 60)
    print(f"  数据库: {config['host']}:{config['port']}/{config['database']}")
    print(f"  CSV目录: {CSV_DIR}")
    print(f"  模式: {'预览' if args.dry_run else '执行'}")
    print()

    if args.table:
        # 仅导入指定表
        import_list = [
            (csv_name, tbl) for csv_name, tbl in IMPORT_ORDER if tbl == args.table
        ]
        if not import_list:
            print(f"[错误] 未找到表: {args.table}")
            sys.exit(1)
    else:
        import_list = IMPORT_ORDER

    if args.dry_run:
        total = 0
        for csv_name, table_name in import_list:
            csv_path = CSV_DIR / csv_name
            if csv_path.exists():
                _, rows = read_csv(csv_path)
                total += len(rows)
                print(f"  {table_name}: {len(rows)} 行 <- {csv_name}")
            else:
                print(f"  {table_name}: [缺失] {csv_name}")
        print(f"\n  预计导入: {total} 行")
        return

    conn = get_connection(config)
    cursor = conn.cursor()

    if args.clear:
        print("[清空] 清空所有表数据...")
        # 逆序清空（先子表后父表）
        for _, table_name in reversed(import_list):
            clear_table(cursor, table_name)
        conn.commit()
        print("  已清空\n")

    print("[导入] 开始导入...\n")
    total_imported = 0

    for csv_name, table_name in import_list:
        csv_path = CSV_DIR / csv_name
        count = import_table(conn, cursor, csv_path, table_name)
        total_imported += count
        conn.commit()

    cursor.close()
    conn.close()

    print(f"\n{'=' * 60}")
    print(f"  导入完成! 共 {total_imported} 行")
    print(f"{'=' * 60}")
    print(f"\n验证命令:")
    print(f"  mysql -h {config['host']} -u {config['user']} -p {config['database']} -e \"SELECT COUNT(*) FROM parts;\"")
    print(f"  mysql -h {config['host']} -u {config['user']} -p {config['database']} -e \"SELECT COUNT(*) FROM part_alternatives;\"")


if __name__ == "__main__":
    main()
