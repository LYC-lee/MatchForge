"""
数据库一键初始化脚本
运行: python api/db_init.py

MySQL matchforge:
  - material_dictionary  标准物料字典（lookup_std_code 工具查询）
  - suppliers            供应商数据（filter_suppliers 工具查询）

Neo4j:
  - Part 节点 + EQUIVALENT_TO 关系（query_all_alternatives 工具查询）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime

# 确保项目根目录在 path 中
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(_PROJECT_ROOT / ".env")

from sqlalchemy import create_engine, text, inspect
from neo4j import GraphDatabase

from ai.config import MYSQL_URL, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


# ============================================================
# MySQL 部分
# ============================================================

def init_mysql():
    """创建 material_dictionary 和 suppliers 表，并导入种子数据。"""
    engine = create_engine(MYSQL_URL, pool_pre_ping=True)

    with engine.connect() as conn:
        # ── 建表 ──
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS material_dictionary (
                id         BIGINT AUTO_INCREMENT PRIMARY KEY,
                std_code   VARCHAR(100) NOT NULL COMMENT '标准编码',
                category   VARCHAR(50)  NOT NULL COMMENT '品类',
                params     JSON         NOT NULL COMMENT '规格参数 JSON',
                standard   VARCHAR(200) NULL     COMMENT '参考标准',
                description TEXT         NULL     COMMENT '描述',
                created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uk_std_code (std_code),
                KEY idx_category (category)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            COMMENT='标准物料字典'
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS suppliers (
                id              BIGINT AUTO_INCREMENT PRIMARY KEY,
                name            VARCHAR(200) NOT NULL COMMENT '供应商名称',
                category        VARCHAR(50)  NOT NULL COMMENT '主营品类',
                brand_coverage  JSON         NULL     COMMENT '覆盖品牌 JSON 数组',
                location        VARCHAR(100) NULL     COMMENT '所在地',
                qualifications  JSON         NULL     COMMENT '资质 JSON 数组',
                moq             INT          NULL     COMMENT '最小起订量',
                lead_time_weeks INT          NULL     COMMENT '交期（周）',
                rating          DECIMAL(3,2) NOT NULL DEFAULT 0.00 COMMENT '评分 0-5',
                status          VARCHAR(20)  NOT NULL DEFAULT 'pending' COMMENT '审核状态',
                data_source     VARCHAR(200) NULL     COMMENT '数据来源',
                contact_phone   VARCHAR(50)  NULL,
                contact_email   VARCHAR(100) NULL,
                updated_at      DATE         NULL     COMMENT '数据更新日期',
                created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                KEY idx_suppliers_category (category),
                KEY idx_suppliers_status (status),
                KEY idx_suppliers_location (location)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            COMMENT='供应商表'
        """))
        conn.commit()

    # ── 导入字典数据 ──
    # 中文 key → 英文 key 映射（与 lookup_std_code 工具查询字段对齐）
    _PARAM_KEY_MAP = {
        "封装": "package", "介质类型": "temp_coeff", "容值": "capacitance",
        "精度": "tolerance", "额定电压": "rated_voltage", "温度范围": "temp_range",
        "阻值": "resistance", "额定功率": "rated_power", "温度系数": "temp_coeff",
        "类型": "type", "型号": "part_number", "间距": "pitch", "芯数": "pins",
        "额定电流": "rated_current", "正向电流": "forward_current",
        "反向电压": "reverse_voltage", "正向压降": "forward_voltage_drop",
        "稳压值": "zener_voltage", "功耗": "power_dissipation",
        "稳压精度": "zener_tolerance", "系列": "series", "内核": "core",
        "主频": "frequency", "Flash": "flash", "RAM": "ram",
        "工作电压": "operating_voltage", "IO数量": "io_count",
        "漏源电压": "drain_source_voltage", "漏源电流": "drain_source_current",
        "导通电阻": "on_resistance", "栅极阈值电压": "gate_threshold_voltage",
        "感值": "inductance", "直流电阻": "dc_resistance",
        "自谐振频率": "self_resonant_freq", "品质因数": "quality_factor",
        "安装方式": "mounting", "工作温度": "operating_temp",
        "反向耐压": "reverse_voltage", "平均电流": "avg_current",
        "集射极电压": "collector_emitter_voltage", "集电极电流": "collector_current",
        "放大倍数": "gain", "通道数": "channels", "输入电压": "input_voltage",
        "输出电流": "output_current", "峰值功率": "peak_power",
        "钳位电压": "clamping_voltage",
    }

    dict_path = _PROJECT_ROOT / "data" / "dictionary" / "dictionary.json"
    if dict_path.exists():
        with open(dict_path, "r", encoding="utf-8") as f:
            dict_data = json.load(f)
        items = dict_data.get("items", [])
        with engine.connect() as conn:
            for item in items:
                raw_params = item.get("params", {})
                # 中文 key → 英文 key
                params = {_PARAM_KEY_MAP.get(k, k): v for k, v in raw_params.items()}
                # 品类名去后缀（"MLCC电容"→"MLCC", "贴片电阻"→"电阻" 等）
                category = item.get("category", "")
                for suffix in ["电容", "电阻", "电感", "单片机"]:
                    category = category.replace(suffix, "")
                conn.execute(text("""
                    INSERT INTO material_dictionary (std_code, category, params, standard, description)
                    VALUES (:std_code, :category, :params, :standard, :description)
                    ON DUPLICATE KEY UPDATE
                        params = VALUES(params),
                        standard = VALUES(standard),
                        description = VALUES(description)
                """), {
                    "std_code": item["std_code"],
                    "category": category,
                    "params": json.dumps(params, ensure_ascii=False),
                    "standard": item.get("standard", ""),
                    "description": item.get("description", ""),
                })
            conn.commit()
        print(f"  [MySQL] material_dictionary: {len(items)} 条")

    # ── 导入供应商数据 ──
    supp_path = _PROJECT_ROOT / "data" / "suppliers" / "suppliers.json"
    if supp_path.exists():
        with open(supp_path, "r", encoding="utf-8") as f:
            suppliers_data = json.load(f)
        with engine.connect() as conn:
            count = 0
            for sup in suppliers_data:
                # 汇总所有产品的品牌（提取英文简称）
                brands = []
                min_moq = None
                min_lead = None
                for p in sup.get("products", []):
                    b = p.get("brand", "")
                    if b:
                        # 提取英文品牌名: "国巨(YAGEO)" → "YAGEO"
                        import re
                        m = re.search(r'\(([^)]+)\)', b)
                        brand_name = m.group(1) if m else b
                        if brand_name not in brands:
                            brands.append(brand_name)
                    moq = p.get("moq")
                    if moq is not None and (min_moq is None or moq < min_moq):
                        min_moq = moq
                    lt = p.get("lead_time_weeks")
                    if lt is not None and (min_lead is None or lt < min_lead):
                        min_lead = lt

                # 品类名简化: "MLCC电容" → "MLCC", "MCU单片机" → "MCU"
                category = sup.get("main_category", "")
                category = category.replace("电容", "").replace("单片机", "").replace("电子", "")

                conn.execute(text("""
                    INSERT INTO suppliers
                        (id, name, category, brand_coverage, location, qualifications,
                         moq, lead_time_weeks, rating, status, data_source,
                         contact_phone, contact_email, updated_at)
                    VALUES
                        (:id, :name, :category, :brand_coverage, :location, :qualifications,
                         :moq, :lead_time_weeks, :rating, :status, :data_source,
                         :contact_phone, :contact_email, :updated_at)
                    ON DUPLICATE KEY UPDATE
                        name = VALUES(name),
                        category = VALUES(category),
                        brand_coverage = VALUES(brand_coverage),
                        location = VALUES(location),
                        qualifications = VALUES(qualifications),
                        moq = VALUES(moq),
                        lead_time_weeks = VALUES(lead_time_weeks),
                        rating = VALUES(rating),
                        status = VALUES(status),
                        data_source = VALUES(data_source),
                        contact_phone = VALUES(contact_phone),
                        contact_email = VALUES(contact_email),
                        updated_at = VALUES(updated_at)
                """), {
                    "id": sup["id"],
                    "name": sup["name"],
                    "category": category,
                    "brand_coverage": json.dumps(brands, ensure_ascii=False),
                    "location": sup.get("location", ""),
                    "qualifications": json.dumps(sup.get("qualifications", []), ensure_ascii=False),
                    "moq": min_moq,
                    "lead_time_weeks": min_lead,
                    "rating": sup.get("rating", 0),
                    "status": sup.get("status", "pending"),
                    "data_source": "平台数据",
                    "contact_phone": sup.get("contact_phone", ""),
                    "contact_email": sup.get("contact_email", ""),
                    "updated_at": datetime.now().strftime("%Y-%m-%d"),
                })
                count += 1
            conn.commit()
        print(f"  [MySQL] suppliers: {count} 条")

    engine.dispose()


# ============================================================
# Neo4j 部分
# ============================================================

def init_neo4j():
    """导入替代料交叉引用图数据。"""
    alt_path = _PROJECT_ROOT / "data" / "alternatives" / "alternatives.json"
    if not alt_path.exists():
        print("  [Neo4j] alternatives.json 不存在，跳过")
        return

    with open(alt_path, "r", encoding="utf-8") as f:
        alt_data = json.load(f)

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    # 创建约束（幂等）
    with driver.session() as session:
        try:
            session.run("CREATE CONSTRAINT part_pn IF NOT EXISTS FOR (p:Part) REQUIRE p.part_number IS UNIQUE")
        except Exception:
            pass  # Neo4j 5.x 语法可能不同

    groups = alt_data.get("groups", [])
    part_count = 0
    rel_count = 0

    with driver.session() as session:
        for group in groups:
            parts = group.get("parts", [])
            confidence = group.get("confidence", 0.80)

            # 为组内每对零件创建 EQUIVALENT_TO 关系
            for i, p1 in enumerate(parts):
                pn1 = p1["part_number"]

                # 创建 Part 节点
                session.run("""
                    MERGE (p:Part {part_number: $pn})
                    SET p.brand = $brand, p.specs = $specs, p.category = $category
                """, pn=pn1, brand=p1.get("brand", ""),
                   specs=json.dumps(p1.get("specs", {}), ensure_ascii=False),
                   category=group.get("category", ""))
                part_count += 1

                # 与后续零件建立关系
                for j in range(i + 1, len(parts)):
                    pn2 = parts[j]["part_number"]
                    session.run("""
                        MERGE (a:Part {part_number: $pn1})
                        MERGE (b:Part {part_number: $pn2})
                        MERGE (a)-[r:EQUIVALENT_TO]->(b)
                        SET r.confidence = $confidence,
                            r.source = $source,
                            r.verified = true
                    """, pn1=pn1, pn2=pn2, confidence=confidence,
                       source="Datasheet交叉引用")
                    rel_count += 1

        # 统计
        result = session.run("MATCH (p:Part) RETURN count(p) AS cnt")
        node_total = result.single()["cnt"]
        result2 = session.run("MATCH ()-[r:EQUIVALENT_TO]->() RETURN count(r) AS cnt")
        rel_total = result2.single()["cnt"]

    driver.close()
    print(f"  [Neo4j] Part 节点: {node_total}, EQUIVALENT_TO 关系: {rel_total}")


# ============================================================
# 主入口
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("MatchForge 数据库初始化")
    print("=" * 60)

    print("\n[MySQL] 连接", MYSQL_URL.split("@")[1].split("?")[0] if "@" in MYSQL_URL else MYSQL_URL)
    try:
        init_mysql()
        print("  [MySQL] [OK] 完成")
    except Exception as e:
        print(f"  [MySQL] [FAIL] 失败: {e}")

    print(f"\n[Neo4j] 连接 {NEO4J_URI}")
    try:
        init_neo4j()
        print("  [Neo4j] [OK] 完成")
    except Exception as e:
        print(f"  [Neo4j] [FAIL] 失败: {e}")

    print("\n" + "=" * 60)
    print("初始化完成")
    print("=" * 60)