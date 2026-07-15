#!/usr/bin/env python3
"""
MatchForge P4 数据层 - 一键初始化脚本
负责人: P4 (数据/知识库工程师)

目录架构:
  data/
  ├── mysql_schema.sql          # MySQL 建表脚本
  ├── suppliers/                # 种子供应商 (JSON -> MySQL + Milvus)
  │   ├── suppliers.json
  │   └── import_to_mysql.py
  ├── alternatives/             # 替代料交叉引用 (JSON -> Neo4j)
  │   ├── alternatives.json
  │   └── import_to_neo4j.py
  ├── dictionary/               # 标准字典 (JSON -> MySQL)
  │   ├── dictionary.json
  │   └── import_to_mysql.py
  ├── milvus_collections.py     # Milvus 集合创建
  ├── milvus_seed_data.py       # Milvus 向量种子数据
  ├── knowledge_base_docs.py    # 知识库文档分块
  └── init_all.py               # 本文件

执行顺序:
  1. MySQL 建表
  2. 种子供应商导入 (JSON -> MySQL)
  3. 标准字典导入 (JSON -> MySQL)
  4. Neo4j 替代料图构建 (JSON -> Neo4j)
  5. Milvus 集合创建 + 向量索引构建

使用方式:
  python data/init_all.py                    # 全部执行
  python data/init_all.py --step mysql       # 仅 MySQL
  python data/init_all.py --step neo4j       # 仅 Neo4j
  python data/init_all.py --step milvus      # 仅 Milvus
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(__file__).resolve().parent


def run_mysql_init():
    """MySQL: 建表 + 导入种子供应商 + 标准字典"""
    print("\n" + "=" * 60)
    print("Step 1: MySQL 初始化 (建表 + 种子数据)")
    print("=" * 60)

    # 1. 建表
    schema_file = DATA_DIR / "mysql_schema.sql"
    if schema_file.exists():
        print(f"  [执行] 建表: {schema_file.name} ...")
        result = subprocess.run(
            f"mysql -h{os.getenv('MYSQL_HOST','127.0.0.1')} -P{os.getenv('MYSQL_PORT','3306')} "
            f"-u{os.getenv('MYSQL_USER','root')} -p{os.getenv('MYSQL_PASSWORD','')} "
            f"{os.getenv('MYSQL_DATABASE','matchforge')} < {schema_file}",
            shell=True, capture_output=True, text=True
        )
        print(f"  [{'成功' if result.returncode == 0 else '失败'}] {schema_file.name}")
        if result.stderr:
            print(f"    {result.stderr[:200]}")

    # 2. 导入种子供应商
    import_suppliers = DATA_DIR / "suppliers" / "import_to_mysql.py"
    if import_suppliers.exists():
        print(f"  [执行] 种子供应商导入: {import_suppliers.name} ...")
        result = subprocess.run(
            [sys.executable, str(import_suppliers)],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT)
        )
        print(f"  [{'成功' if result.returncode == 0 else '失败'}] 种子供应商导入")
        if result.stdout:
            print(f"    {result.stdout[:300]}")
        if result.stderr:
            print(f"    {result.stderr[:300]}")

    # 3. 导入标准字典
    import_dict = DATA_DIR / "dictionary" / "import_to_mysql.py"
    if import_dict.exists():
        print(f"  [执行] 标准字典导入: {import_dict.name} ...")
        result = subprocess.run(
            [sys.executable, str(import_dict)],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT)
        )
        print(f"  [{'成功' if result.returncode == 0 else '失败'}] 标准字典导入")
        if result.stdout:
            print(f"    {result.stdout[:300]}")
        if result.stderr:
            print(f"    {result.stderr[:300]}")

    print("  MySQL 初始化完成!")


def run_neo4j_init():
    """Neo4j: 导入替代料交叉引用图"""
    print("\n" + "=" * 60)
    print("Step 2: Neo4j 替代料图构建")
    print("=" * 60)

    import_script = DATA_DIR / "alternatives" / "import_to_neo4j.py"
    if not import_script.exists():
        print(f"  [跳过] 文件不存在: {import_script}")
        return

    print(f"  [执行] {import_script.name} ...")
    result = subprocess.run(
        [sys.executable, str(import_script)],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT)
    )
    print(f"  [{'成功' if result.returncode == 0 else '失败'}] Neo4j 替代料图构建")
    if result.stdout:
        print(f"    {result.stdout[:500]}")
    if result.stderr:
        print(f"    {result.stderr[:300]}")

    print("  Neo4j 替代料图构建完成!")


def run_milvus_init():
    """Milvus: 创建集合 + 导入向量数据"""
    print("\n" + "=" * 60)
    print("Step 3: Milvus 向量索引构建")
    print("=" * 60)

    scripts = [
        DATA_DIR / "milvus_collections.py",
        DATA_DIR / "milvus_seed_data.py",
    ]

    for script in scripts:
        if not script.exists():
            print(f"  [跳过] 文件不存在: {script.name}")
            continue
        print(f"  [执行] {script.name} ...")
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT)
        )
        print(f"  [{'成功' if result.returncode == 0 else '失败'}] {script.name}")
        if result.stdout:
            print(f"    {result.stdout[:500]}")
        if result.stderr:
            print(f"    {result.stderr[:300]}")

    print("  Milvus 向量索引构建完成!")


def main():
    parser = argparse.ArgumentParser(description="MatchForge P4 数据层初始化")
    parser.add_argument('--step', choices=['mysql', 'neo4j', 'milvus', 'all'],
                        default='all', help='执行步骤 (默认全部)')
    args = parser.parse_args()

    # 加载 .env
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        print("[警告] python-dotenv 未安装，将使用系统环境变量")

    print("MatchForge P4 数据层初始化")
    print(f"  数据目录: {DATA_DIR}")
    print(f"  目录结构:")
    print(f"    data/suppliers/    种子供应商 -> MySQL+Milvus")
    print(f"    data/alternatives/ 替代料交叉引用 -> Neo4j")
    print(f"    data/dictionary/   标准字典 -> MySQL")

    if args.step in ('all', 'mysql'):
        run_mysql_init()
    if args.step in ('all', 'neo4j'):
        run_neo4j_init()
    if args.step in ('all', 'milvus'):
        run_milvus_init()

    print("\n" + "=" * 60)
    print("P4 数据层初始化完成!")
    print("=" * 60)
    print("""
验证命令:
  MySQL:   mysql -u root -p matchforge -e "SELECT COUNT(*) FROM suppliers;"
  Neo4j:   MATCH (n) RETURN labels(n), count(n)
  Milvus:  python -c "from pymilvus import connections, Collection; connections.connect(); print(Collection('product_embeddings').num_entities)"
    """)


if __name__ == "__main__":
    main()
