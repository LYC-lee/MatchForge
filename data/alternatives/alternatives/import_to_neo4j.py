#!/usr/bin/env python3
"""
MatchForge — 替代料交叉引用数据导入 Neo4j 脚本
================================================
读取 alternatives.json，导入 Neo4j 图数据库。

图谱结构:
  节点:
    (:Part {part_number, brand, category, specs})
    (:Category {name})
  关系:
    (:Part)-[:EQUIVALENT_TO {confidence, source, verified, note, level, level_desc}]->(:Part)
    (:Part)-[:BELONGS_TO]->(:Category)

用法:
    python data/alternatives/import_to_neo4j.py            # 导入数据
    python data/alternatives/import_to_neo4j.py --dry-run   # 仅打印不执行
    python data/alternatives/import_to_neo4j.py --clear     # 先清除旧数据再导入

环境变量 (从 .env 读取):
    NEO4J_URI       — Neo4j Bolt 连接地址 (默认 bolt://127.0.0.1:7687)
    NEO4J_USER      — 用户名 (默认 neo4j)
    NEO4J_PASSWORD  — 密码
    NEO4J_DATABASE  — 数据库名 (默认 matchforge)
"""

import argparse
import json
import os
import sys
from pathlib import Path

# ── 路径 ──
SCRIPT_DIR = Path(__file__).resolve().parent
JSON_PATH = SCRIPT_DIR / "alternatives.json"
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # MatchForge/
ENV_PATH = PROJECT_ROOT / ".env"


def load_env(filepath=ENV_PATH):
    """从 .env 文件加载环境变量（不覆盖已有的）"""
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


def get_neo4j_config():
    """从环境变量获取 Neo4j 连接配置"""
    return {
        "uri": os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687"),
        "user": os.environ.get("NEO4J_USER", "neo4j"),
        "password": os.environ.get("NEO4J_PASSWORD", ""),
        "database": os.environ.get("NEO4J_DATABASE", "matchforge"),
    }


def load_json():
    """读取 alternatives.json"""
    if not JSON_PATH.exists():
        print(f"❌ 找不到数据文件: {JSON_PATH}")
        sys.exit(1)
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def import_to_neo4j(dry_run=False, clear_first=False):
    """将 JSON 数据导入 Neo4j"""
    data = load_json()
    groups = data.get("groups", [])
    print(f"📋 加载数据: {len(groups)} 组替代料")

    # 统计
    all_parts = {}        # part_number -> {brand, category, specs}
    all_equivalences = []  # [{from, to, ...}]
    all_categories = set()

    for g in groups:
        cat = g["category"]
        all_categories.add(cat)
        for p in g["parts"]:
            pn = p["part_number"]
            if pn not in all_parts:
                all_parts[pn] = {
                    "part_number": pn,
                    "brand": p["brand"],
                    "category": cat,
                    "specs": json.dumps(p["specs"], ensure_ascii=False),
                    "group_id": g["group_id"],
                }
        for eq in g["equivalences"]:
            all_equivalences.append(eq)

    print(f"   唯一料号: {len(all_parts)}")
    print(f"   等效关系: {len(all_equivalences)}")
    print(f"   品类数:   {len(all_categories)}")

    if dry_run:
        print("\n🔍 [Dry-Run] 以下是将执行的 Cypher 语句预览:\n")
        print("-- 1. 创建品类节点")
        for c in sorted(all_categories):
            print(f"  MERGE (:Category {{name: '{c}'}});")
        print(f"\n-- 2. 创建 {len(all_parts)} 个 Part 节点")
        for pn, p in list(all_parts.items())[:5]:
            print(f"  MERGE (:Part {{part_number: '{pn}', brand: '{p['brand']}', category: '{p['category']}'}});")
        print(f"  ... (共 {len(all_parts)} 个)")
        print(f"\n-- 3. 创建 {len(all_equivalences)} 条 EQUIVALENT_TO 关系")
        for eq in all_equivalences[:5]:
            print(f"  MATCH (a:Part {{part_number: '{eq['from']}'}}), (b:Part {{part_number: '{eq['to']}'}})")
            print(f"  MERGE (a)-[:EQUIVALENT_TO {{confidence: {eq['confidence']}}}]->(b);")
        print(f"  ... (共 {len(all_equivalences)} 条)")
        print(f"\n-- 4. 创建 {len(all_parts)} 条 BELONGS_TO 关系")
        print(f"\n✅ Dry-Run 完成，未写入数据库。")
        return

    # ── 连接 Neo4j ──
    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("❌ 未安装 neo4j 驱动，正在安装...")
        os.system(f"{sys.executable} -m pip install neo4j")
        from neo4j import GraphDatabase

    config = get_neo4j_config()
    print(f"\n🔗 连接 Neo4j: {config['uri']} (数据库: {config['database']})")

    try:
        driver = GraphDatabase.driver(
            config["uri"],
            auth=(config["user"], config["password"]),
        )
        driver.verify_connectivity()
        print("✅ Neo4j 连接成功")
    except Exception as e:
        print(f"❌ Neo4j 连接失败: {e}")
        print(f"   请检查 .env 中的 NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD")
        sys.exit(1)

    database = config["database"]

    def run_query(query, **params):
        with driver.session(database=database) as session:
            result = session.run(query, **params)
            return result.consume()

    # ── 清除旧数据 ──
    if clear_first:
        print("\n🧹 清除旧的替代料数据...")
        run_query("MATCH (p:Part) DETACH DELETE p")
        run_query("MATCH (c:Category) DETACH DELETE c")
        print("   已清除 Part 和 Category 节点")

    # ── 1. 创建约束与索引 ──
    print("\n📏 创建约束与索引...")
    try:
        run_query("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Part) REQUIRE p.part_number IS UNIQUE")
        print("   ✓ Part.part_number 唯一约束")
    except Exception:
        # 兼容旧版 Neo4j 语法
        try:
            run_query("CREATE CONSTRAINT IF NOT EXISTS ON (p:Part) ASSERT p.part_number IS UNIQUE")
            print("   ✓ Part.part_number 唯一约束 (legacy)")
        except Exception as e:
            print(f"   ⚠ 约束创建跳过: {e}")

    try:
        run_query("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Category) REQUIRE c.name IS UNIQUE")
        print("   ✓ Category.name 唯一约束")
    except Exception:
        try:
            run_query("CREATE CONSTRAINT IF NOT EXISTS ON (c:Category) ASSERT c.name IS UNIQUE")
            print("   ✓ Category.name 唯一约束 (legacy)")
        except Exception as e:
            print(f"   ⚠ 约束创建跳过: {e}")

    # ── 2. 创建品类节点 ──
    print(f"\n📦 创建 {len(all_categories)} 个品类节点...")
    for cat in sorted(all_categories):
        run_query("MERGE (:Category {name: $name})", name=cat)
    print("   ✓ 品类节点创建完成")

    # ── 3. 创建 Part 节点 ──
    print(f"\n🔧 创建 {len(all_parts)} 个 Part 节点...")
    part_list = list(all_parts.values())
    # 批量写入（每批 50 个）
    BATCH_SIZE = 50
    for i in range(0, len(part_list), BATCH_SIZE):
        batch = part_list[i:i + BATCH_SIZE]
        run_query(
            """
            UNWIND $batch AS row
            MERGE (p:Part {part_number: row.part_number})
              SET p.brand = row.brand,
                  p.category = row.category,
                  p.specs = row.specs
            """,
            batch=batch,
        )
    print("   ✓ Part 节点创建完成")

    # ── 4. 创建 BELONGS_TO 关系 ──
    print(f"\n🔗 创建 {len(all_parts)} 条 BELONGS_TO 关系...")
    relation_batch = [
        {"part_number": p["part_number"], "category": p["category"]}
        for p in part_list
    ]
    for i in range(0, len(relation_batch), BATCH_SIZE):
        batch = relation_batch[i:i + BATCH_SIZE]
        run_query(
            """
            UNWIND $batch AS row
            MATCH (p:Part {part_number: row.part_number}),
                  (c:Category {name: row.category})
            MERGE (p)-[:BELONGS_TO]->(c)
            """,
            batch=batch,
        )
    print("   ✓ BELONGS_TO 关系创建完成")

    # ── 5. 创建 EQUIVALENT_TO 关系 ──
    print(f"\n⚡ 创建 {len(all_equivalences)} 条 EQUIVALENT_TO 关系...")
    for i in range(0, len(all_equivalences), BATCH_SIZE):
        batch = all_equivalences[i:i + BATCH_SIZE]
        run_query(
            """
            UNWIND $batch AS row
            MATCH (a:Part {part_number: row.from}),
                  (b:Part {part_number: row.to})
            MERGE (a)-[r:EQUIVALENT_TO]->(b)
              SET r.confidence = row.confidence,
                  r.source = row.source,
                  r.verified = row.verified,
                  r.note = row.note,
                  r.level = row.level,
                  r.level_desc = row.level_desc
            """,
            batch=batch,
        )
    print("   ✓ EQUIVALENT_TO 关系创建完成")

    # ── 验证 ──
    print("\n📊 导入结果验证:")
    with driver.session(database=database) as session:
        part_count = session.run("MATCH (p:Part) RETURN count(p) AS c").single()["c"]
        cat_count = session.run("MATCH (c:Category) RETURN count(c) AS c").single()["c"]
        eq_count = session.run(
            "MATCH ()-[r:EQUIVALENT_TO]->() RETURN count(r) AS c"
        ).single()["c"]
        bt_count = session.run(
            "MATCH ()-[r:BELONGS_TO]->() RETURN count(r) AS c"
        ).single()["c"]

        print(f"   Part 节点:          {part_count}")
        print(f"   Category 节点:      {cat_count}")
        print(f"   EQUIVALENT_TO 关系: {eq_count}")
        print(f"   BELONGS_TO 关系:    {bt_count}")

        # 按品类统计
        print("\n   按品类分布:")
        result = session.run(
            """
            MATCH (p:Part)-[:BELONGS_TO]->(c:Category)
            RETURN c.name AS category, count(p) AS count
            ORDER BY count DESC
            """
        )
        for record in result:
            print(f"     {record['category']}: {record['count']} 个料号")

        # 等效关系按来源统计
        print("\n   按数据来源分布:")
        result = session.run(
            """
            MATCH ()-[r:EQUIVALENT_TO]->()
            RETURN r.source AS source, count(r) AS count, avg(r.confidence) AS avg_conf
            ORDER BY count DESC
            """
        )
        for record in result:
            print(f"     {record['source']}: {record['count']} 条 (平均置信度: {record['avg_conf']:.3f})")

        # 等效关系按等级统计
        print("\n   按 L1-L5 等级分布:")
        result = session.run(
            """
            MATCH ()-[r:EQUIVALENT_TO]->()
            RETURN r.level AS level, r.level_desc AS desc, count(r) AS count
            ORDER BY level
            """
        )
        for record in result:
            print(f"     {record['level']} {record['desc']}: {record['count']} 条")

    driver.close()
    print("\n✅ 导入完成!")


def main():
    parser = argparse.ArgumentParser(
        description="将 alternatives.json 导入 Neo4j 图数据库"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅预览 Cypher 语句，不实际写入数据库",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="导入前清除已有的 Part 和 Category 节点",
    )
    args = parser.parse_args()

    load_env()
    import_to_neo4j(dry_run=args.dry_run, clear_first=args.clear)


if __name__ == "__main__":
    main()
