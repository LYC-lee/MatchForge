#!/usr/bin/env python3
"""
MatchForge 种子供应商导入脚本
用途: 读取 suppliers.json，导入 MySQL suppliers 和 products 表

表结构 (mysql_schema.sql):
  suppliers(id, name, location, qualifications(JSON), rating, status,
           contact_phone, contact_email, main_category, created_at, updated_at)
  products(id, supplier_id, category, part_number, specs(JSON), datasheet_url,
           moq, lead_time_weeks, price, in_stock, updated_at)

使用方式:
  python data/suppliers/import_to_mysql.py

环境变量 (读取 .env 或系统环境变量):
  MYSQL_HOST      默认 127.0.0.1
  MYSQL_PORT      默认 3306
  MYSQL_USER      默认 root
  MYSQL_PASSWORD  默认 空
  MYSQL_DATABASE  默认 matchforge

依赖: pip install pymysql
"""

import json
import os
import sys
from pathlib import Path

# 项目根目录 (data/suppliers/ -> 上两级)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(__file__).resolve().parent
JSON_FILE = DATA_DIR / "suppliers.json"


def load_env():
    """加载 .env 文件到 os.environ"""
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value


def get_db_config():
    """从环境变量获取数据库连接配置"""
    return {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "matchforge"),
        "charset": "utf8mb4",
    }


def import_suppliers():
    """主导入逻辑"""
    # 加载环境变量
    load_env()

    # 读取 JSON
    if not JSON_FILE.exists():
        print(f"[错误] JSON 文件不存在: {JSON_FILE}")
        sys.exit(1)

    with open(JSON_FILE, "r", encoding="utf-8") as f:
        suppliers = json.load(f)

    print(f"[信息] 加载 {len(suppliers)} 家供应商数据")
    total_products = sum(len(s.get("products", [])) for s in suppliers)
    print(f"[信息] 共 {total_products} 个产品")

    # 连接 MySQL
    try:
        import pymysql
    except ImportError:
        print("[错误] 缺少 pymysql 模块，请安装: pip install pymysql")
        sys.exit(1)

    config = get_db_config()
    print(f"[信息] 连接 MySQL: {config['user']}@{config['host']}:{config['port']}/{config['database']}")

    try:
        conn = pymysql.connect(**config)
    except pymysql.Error as e:
        print(f"[错误] MySQL 连接失败: {e}")
        sys.exit(1)

    cursor = conn.cursor()

    # 清空旧数据 (保持 id 自增从头开始)
    try:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        cursor.execute("TRUNCATE TABLE products")
        cursor.execute("TRUNCATE TABLE qualifications")
        cursor.execute("TRUNCATE TABLE suppliers")
        cursor.execute("TRUNCATE TABLE enterprises")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        print("[信息] 已清空 suppliers / products / qualifications 旧数据")
    except pymysql.Error as e:
        print(f"[警告] 清空旧数据失败 (可忽略): {e}")
        conn.rollback()

    # ── 导入供应商 ──
    supplier_sql = """
        INSERT INTO suppliers
            (id, name, location, rating, status,
             contact_phone, contact_email, main_category)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s)
    """

    # ── 导入资质（独立表）──
    qual_sql = """
        INSERT INTO qualifications
            (supplier_id, type, status)
        VALUES
            (%s, %s, %s)
    """

    supplier_count = 0
    product_count = 0
    qual_count = 0

    for sup in suppliers:
        try:
            cursor.execute(supplier_sql, (
                sup["id"],
                sup["name"],
                sup.get("location"),
                sup.get("rating", 0),
                sup.get("status", "pending"),
                sup.get("contact_phone"),
                sup.get("contact_email"),
                sup.get("main_category"),
            ))
            supplier_count += 1
        except pymysql.Error as e:
            print(f"[错误] 导入供应商 #{sup['id']} {sup['name']} 失败: {e}")
            conn.rollback()
            sys.exit(1)

        # ── 导入该供应商的资质证照 ──
        for qual_type in sup.get("qualifications", []):
            try:
                cursor.execute(qual_sql, (
                    sup["id"],
                    qual_type,
                    "verified" if sup.get("status") == "approved" else "pending",
                ))
                qual_count += 1
            except pymysql.Error as e:
                print(f"[警告] 导入资质失败: {e}")

        # ── 导入该供应商的产品 ──
        product_sql = """
            INSERT INTO products
                (supplier_id, category, part_number, brand, specs, datasheet_url,
                 moq, lead_time_weeks, price, in_stock)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        for prod in sup.get("products", []):
            specs_json = json.dumps(prod.get("specs", {}), ensure_ascii=False)
            try:
                cursor.execute(product_sql, (
                    sup["id"],
                    prod["category"],
                    prod["part_number"],
                    prod.get("brand"),
                    specs_json,
                    prod.get("datasheet_url"),
                    prod.get("moq"),
                    prod.get("lead_time_weeks"),
                    prod.get("price"),
                    prod.get("in_stock", True),
                ))
                product_count += 1
            except pymysql.Error as e:
                print(f"[错误] 导入产品 {prod['part_number']} (供应商#{sup['id']}) 失败: {e}")
                conn.rollback()
                sys.exit(1)

    conn.commit()

    # ── 验证 ──
    cursor.execute("SELECT COUNT(*) FROM suppliers")
    db_supplier_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM products")
    db_product_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM qualifications")
    db_qual_count = cursor.fetchone()[0]

    # 品类分布
    cursor.execute("SELECT main_category, COUNT(*) FROM suppliers GROUP BY main_category ORDER BY COUNT(*) DESC")
    category_dist = cursor.fetchall()

    # 地区分布
    cursor.execute("SELECT location, COUNT(*) FROM suppliers GROUP BY location ORDER BY COUNT(*) DESC")
    location_dist = cursor.fetchall()

    cursor.close()
    conn.close()

    print()
    print("=" * 50)
    print("导入完成!")
    print("=" * 50)
    print(f"  供应商: {supplier_count} 条 (数据库验证: {db_supplier_count})")
    print(f"  产品:   {product_count} 条 (数据库验证: {db_product_count})")
    print(f"  资质:   {qual_count} 条 (数据库验证: {db_qual_count})")
    print()
    print("地区分布:")
    for loc, cnt in location_dist:
        print(f"  {loc}: {cnt} 家")
    print()
    print("品类分布:")
    for cat, cnt in category_dist:
        print(f"  {cat}: {cnt} 家")
    print()
    print("验证命令:")
    print(f"  mysql -u {config['user']} -p {config['database']} -e \"SELECT COUNT(*) FROM suppliers;\"")
    print(f"  mysql -u {config['user']} -p {config['database']} -e \"SELECT COUNT(*) FROM products;\"")


if __name__ == "__main__":
    import_suppliers()
