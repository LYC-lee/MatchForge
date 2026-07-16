"""
企业驾驶舱 Phase2 种子数据 (产品 / BOM / 订单 / 预测 / 库存 / 缺件)。

围绕 Phase1 的 6 家企业构造真实演示场景, 重点:
  - 9003 鼎云整机制造: 2 个整机产品
  - 9002 创捷主板模组: 2 个主板/模组产品

构造 3 个缺件场景 (均在 9003 鼎云):
  1. 严重缺件, 影响高优先级订单:
     CPU-I7-13700 (关键件, 首选供应商=9001华芯, 与9003无直接关系 -> relationship_missing)
     需求 800, 可用 20, 缺口 780, severity=critical
  2. 有缺口但可联系直接上游:
     PCBA-DY-DT-Z690 (关键件, 首选供应商=9002创捷, 是9003直接上游)
     需求 800, 可用 40, 缺口 760, relationship_missing=false
  3. 库存低于安全库存但尚未真正缺货:
     DDR5-16GB-4800 (非关键件, 无首选供应商)
     需求 1600, 可用 1700 (未缺货), 安全库存 2000 -> warning

9002 创捷额外 1 个缺件 (丰富其驾驶舱):
  - CHIPSET-Z690 (关键件, 首选供应商=9001华芯, 是9002直接上游)
    需求 2700, 可用 200, 缺口 2500, severity=critical

幂等: 重复执行只更新不重复插入 (按稳定键 delete + re-insert)。
运行: python scripts/seed_enterprise_phase2.py
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from kb.db import init_db, session_scope  # noqa: E402
from kb.models import (  # noqa: E402
    CompanyProduct,
    DemandForecast,
    InventoryItem,
    ProductBomItem,
    ProductionOrder,
    Shortage,
)
from kb import dashboard_calc as dc  # noqa: E402

# 复用 Phase1 种子: 公司 + 关系 (保证自包含)
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
import seed_enterprise_chain as p1_seed  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("seed_enterprise_phase2")

PHASE2_COMPANIES = (9002, 9003)
PRODUCT_IDS = (9101, 9102, 9103, 9104)


def _date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d")


# ============================================================
# 产品 (9003: 2 整机; 9002: 2 主板/模组)
# ============================================================
PRODUCTS = [
    {"id": 9101, "company_id": 9003, "product_name": "鼎云商用台式机 DY-Desktop-Pro",
     "product_model": "DY-DT-Pro", "product_type": "整机",
     "description": "商用办公台式机, 13代酷睿平台", "monthly_capacity": 5000,
     "unit": "台", "status": "active"},
    {"id": 9102, "company_id": 9003, "product_name": "鼎云商用笔记本 DY-Notebook-Air",
     "product_model": "DY-NB-Air", "product_type": "整机",
     "description": "14寸轻薄商用笔记本", "monthly_capacity": 3000,
     "unit": "台", "status": "active"},
    {"id": 9103, "company_id": 9002, "product_name": "商用主板 CJ-MB-Z690",
     "product_model": "CJ-MB-Z690", "product_type": "主板",
     "description": "Z690芯片组商用主板", "monthly_capacity": 2000,
     "unit": "片", "status": "active"},
    {"id": 9104, "company_id": 9002, "product_name": "工控模组 CJ-IMM-COM",
     "product_model": "CJ-IMM-COM", "product_type": "模组",
     "description": "工控核心模组, N5105平台", "monthly_capacity": 3000,
     "unit": "片", "status": "active"},
]


# ============================================================
# BOM (每个产品 5-8 条)
# ============================================================
BOM_ITEMS = [
    # 9101 鼎云台式机 (7 条)
    {"product_id": 9101, "part_number": "CPU-I7-13700", "part_name": "Intel酷睿i7-13700处理器",
     "category_name": "半导体芯片", "qty_per_unit": 1, "unit": "颗",
     "is_critical": True, "preferred_supplier_company_id": 9001},
    {"product_id": 9101, "part_number": "PCBA-DY-DT-Z690", "part_name": "台式机主板PCBA",
     "category_name": "PCBA", "qty_per_unit": 1, "unit": "片",
     "is_critical": True, "preferred_supplier_company_id": 9002},
    {"product_id": 9101, "part_number": "DDR5-16GB-4800", "part_name": "DDR5 16GB 内存条",
     "category_name": "内存", "qty_per_unit": 2, "unit": "条",
     "is_critical": False, "preferred_supplier_company_id": None},
    {"product_id": 9101, "part_number": "SSD-NVMe-512G", "part_name": "NVMe SSD 512GB",
     "category_name": "存储", "qty_per_unit": 1, "unit": "块",
     "is_critical": False, "preferred_supplier_company_id": 9001},
    {"product_id": 9101, "part_number": "PSU-500W", "part_name": "500W电源",
     "category_name": "电源", "qty_per_unit": 1, "unit": "个",
     "is_critical": False, "preferred_supplier_company_id": None},
    {"product_id": 9101, "part_number": "CASE-ATX-01", "part_name": "ATX机箱",
     "category_name": "结构件", "qty_per_unit": 1, "unit": "个",
     "is_critical": False, "preferred_supplier_company_id": None},
    {"product_id": 9101, "part_number": "COOLER-01", "part_name": "CPU散热器",
     "category_name": "散热", "qty_per_unit": 1, "unit": "个",
     "is_critical": False, "preferred_supplier_company_id": None},
    # 9102 鼎云笔记本 (7 条)
    {"product_id": 9102, "part_number": "CPU-I5-1340P", "part_name": "Intel酷睿i5-1340P处理器",
     "category_name": "半导体芯片", "qty_per_unit": 1, "unit": "颗",
     "is_critical": True, "preferred_supplier_company_id": 9001},
    {"product_id": 9102, "part_number": "PCBA-DY-NB-01", "part_name": "笔记本主板PCBA",
     "category_name": "PCBA", "qty_per_unit": 1, "unit": "片",
     "is_critical": True, "preferred_supplier_company_id": 9002},
    {"product_id": 9102, "part_number": "DDR5-8GB-4800", "part_name": "DDR5 8GB 内存条",
     "category_name": "内存", "qty_per_unit": 2, "unit": "条",
     "is_critical": False, "preferred_supplier_company_id": 9006},
    {"product_id": 9102, "part_number": "SSD-NVMe-256G", "part_name": "NVMe SSD 256GB",
     "category_name": "存储", "qty_per_unit": 1, "unit": "块",
     "is_critical": False, "preferred_supplier_company_id": 9001},
    {"product_id": 9102, "part_number": "BAT-NB-56WH", "part_name": "56Wh笔记本电池",
     "category_name": "电池", "qty_per_unit": 1, "unit": "块",
     "is_critical": True, "preferred_supplier_company_id": None},
    {"product_id": 9102, "part_number": "LCD-14-FHD", "part_name": "14寸FHD屏幕模组",
     "category_name": "显示", "qty_per_unit": 1, "unit": "片",
     "is_critical": False, "preferred_supplier_company_id": None},
    {"product_id": 9102, "part_number": "KB-NB-01", "part_name": "笔记本键盘模组",
     "category_name": "输入", "qty_per_unit": 1, "unit": "个",
     "is_critical": False, "preferred_supplier_company_id": None},
    # 9103 创捷主板 (6 条)
    {"product_id": 9103, "part_number": "PCB-Z690-FR4", "part_name": "Z690 PCB基板",
     "category_name": "PCB", "qty_per_unit": 1, "unit": "片",
     "is_critical": True, "preferred_supplier_company_id": None},
    {"product_id": 9103, "part_number": "MLCC-0805-X7R-105", "part_name": "MLCC电容 0805 1uF",
     "category_name": "被动元件", "qty_per_unit": 120, "unit": "颗",
     "is_critical": False, "preferred_supplier_company_id": 9006},
    {"product_id": 9103, "part_number": "RES-0402-10K", "part_name": "贴片电阻 0402 10K",
     "category_name": "被动元件", "qty_per_unit": 80, "unit": "颗",
     "is_critical": False, "preferred_supplier_company_id": 9006},
    {"product_id": 9103, "part_number": "CHIPSET-Z690", "part_name": "Z690芯片组",
     "category_name": "半导体芯片", "qty_per_unit": 1, "unit": "颗",
     "is_critical": True, "preferred_supplier_company_id": 9001},
    {"product_id": 9103, "part_number": "PMIC-VR12", "part_name": "电源管理IC",
     "category_name": "半导体芯片", "qty_per_unit": 1, "unit": "颗",
     "is_critical": True, "preferred_supplier_company_id": 9001},
    {"product_id": 9103, "part_number": "CONN-USB-C-01", "part_name": "USB-C连接器",
     "category_name": "连接器", "qty_per_unit": 4, "unit": "个",
     "is_critical": False, "preferred_supplier_company_id": None},
    # 9104 创捷模组 (5 条)
    {"product_id": 9104, "part_number": "PCB-HDI-IMM", "part_name": "HDI PCB基板",
     "category_name": "PCB", "qty_per_unit": 1, "unit": "片",
     "is_critical": True, "preferred_supplier_company_id": None},
    {"product_id": 9104, "part_number": "SOC-IMM-N5105", "part_name": "N5105 SoC",
     "category_name": "半导体芯片", "qty_per_unit": 1, "unit": "颗",
     "is_critical": True, "preferred_supplier_company_id": 9001},
    {"product_id": 9104, "part_number": "MLCC-0603-X5R-106", "part_name": "MLCC电容 0603 10uF",
     "category_name": "被动元件", "qty_per_unit": 60, "unit": "颗",
     "is_critical": False, "preferred_supplier_company_id": 9006},
    {"product_id": 9104, "part_number": "IND-0805-2R2", "part_name": "电感 0805 2.2uH",
     "category_name": "被动元件", "qty_per_unit": 20, "unit": "颗",
     "is_critical": False, "preferred_supplier_company_id": 9006},
    {"product_id": 9104, "part_number": "CONN-BTB-60P", "part_name": "板对板连接器 60P",
     "category_name": "连接器", "qty_per_unit": 2, "unit": "个",
     "is_critical": False, "preferred_supplier_company_id": None},
]


# ============================================================
# 生产订单 (9003: 5; 9002: 3)  -- status=completed 不计入需求
# ============================================================
ORDERS = [
    # 9003 鼎云
    {"company_id": 9003, "product_id": 9101, "order_number": "DY-ORD-2026-001",
     "customer_company_id": 9005, "quantity": 500, "due_date": _date("2026-08-15"),
     "priority": "urgent", "status": "confirmed"},
    {"company_id": 9003, "product_id": 9101, "order_number": "DY-ORD-2026-002",
     "customer_company_id": 9005, "quantity": 300, "due_date": _date("2026-09-01"),
     "priority": "normal", "status": "open"},
    {"company_id": 9003, "product_id": 9102, "order_number": "DY-ORD-2026-003",
     "customer_company_id": 9005, "quantity": 300, "due_date": _date("2026-08-20"),
     "priority": "high", "status": "confirmed"},
    {"company_id": 9003, "product_id": 9102, "order_number": "DY-ORD-2026-004",
     "customer_company_id": 9005, "quantity": 200, "due_date": _date("2026-09-15"),
     "priority": "normal", "status": "open"},
    {"company_id": 9003, "product_id": 9101, "order_number": "DY-ORD-2026-005",
     "customer_company_id": 9005, "quantity": 150, "due_date": _date("2026-07-01"),
     "priority": "low", "status": "completed"},
    # 9002 创捷
    {"company_id": 9002, "product_id": 9103, "order_number": "CJ-ORD-2026-001",
     "customer_company_id": 9003, "quantity": 1000, "due_date": _date("2026-08-10"),
     "priority": "high", "status": "confirmed"},
    {"company_id": 9002, "product_id": 9103, "order_number": "CJ-ORD-2026-002",
     "customer_company_id": 9003, "quantity": 500, "due_date": _date("2026-09-01"),
     "priority": "normal", "status": "open"},
    {"company_id": 9002, "product_id": 9104, "order_number": "CJ-ORD-2026-003",
     "customer_company_id": 9003, "quantity": 300, "due_date": _date("2026-09-10"),
     "priority": "normal", "status": "open"},
]


# ============================================================
# 预测需求 (4 条)
# ============================================================
FORECASTS = [
    {"company_id": 9003, "product_id": 9102, "forecast_period": "2026-10",
     "forecast_quantity": 400, "confidence": 0.7, "source_type": "manual"},
    {"company_id": 9003, "product_id": 9102, "forecast_period": "2026-11",
     "forecast_quantity": 300, "confidence": 0.65, "source_type": "manual"},
    {"company_id": 9002, "product_id": 9103, "forecast_period": "2026-10",
     "forecast_quantity": 1200, "confidence": 0.7, "source_type": "manual"},
    {"company_id": 9002, "product_id": 9104, "forecast_period": "2026-10",
     "forecast_quantity": 500, "confidence": 0.6, "source_type": "manual"},
]


# ============================================================
# 库存 (9003: 14; 9002: 11)
#   可用库存 = on_hand - reserved; 安全库存用于预警
# ============================================================
INVENTORY = [
    # 9003 P_9101 台式机零件 (需求 800)
    {"company_id": 9003, "part_number": "CPU-I7-13700", "part_name": "Intel酷睿i7-13700处理器",
     "category_name": "半导体芯片", "on_hand_qty": 20, "reserved_qty": 0, "safety_stock_qty": 100},
    {"company_id": 9003, "part_number": "PCBA-DY-DT-Z690", "part_name": "台式机主板PCBA",
     "category_name": "PCBA", "on_hand_qty": 50, "reserved_qty": 10, "safety_stock_qty": 200},
    {"company_id": 9003, "part_number": "DDR5-16GB-4800", "part_name": "DDR5 16GB 内存条",
     "category_name": "内存", "on_hand_qty": 1700, "reserved_qty": 0, "safety_stock_qty": 2000},
    {"company_id": 9003, "part_number": "SSD-NVMe-512G", "part_name": "NVMe SSD 512GB",
     "category_name": "存储", "on_hand_qty": 1000, "reserved_qty": 0, "safety_stock_qty": 600},
    {"company_id": 9003, "part_number": "PSU-500W", "part_name": "500W电源",
     "category_name": "电源", "on_hand_qty": 1000, "reserved_qty": 0, "safety_stock_qty": 600},
    {"company_id": 9003, "part_number": "CASE-ATX-01", "part_name": "ATX机箱",
     "category_name": "结构件", "on_hand_qty": 1000, "reserved_qty": 0, "safety_stock_qty": 600},
    {"company_id": 9003, "part_number": "COOLER-01", "part_name": "CPU散热器",
     "category_name": "散热", "on_hand_qty": 900, "reserved_qty": 0, "safety_stock_qty": 600},
    # 9003 P_9102 笔记本零件 (需求 1200)
    {"company_id": 9003, "part_number": "CPU-I5-1340P", "part_name": "Intel酷睿i5-1340P处理器",
     "category_name": "半导体芯片", "on_hand_qty": 1500, "reserved_qty": 0, "safety_stock_qty": 900},
    {"company_id": 9003, "part_number": "PCBA-DY-NB-01", "part_name": "笔记本主板PCBA",
     "category_name": "PCBA", "on_hand_qty": 1500, "reserved_qty": 0, "safety_stock_qty": 900},
    {"company_id": 9003, "part_number": "DDR5-8GB-4800", "part_name": "DDR5 8GB 内存条",
     "category_name": "内存", "on_hand_qty": 3000, "reserved_qty": 0, "safety_stock_qty": 1500},
    {"company_id": 9003, "part_number": "SSD-NVMe-256G", "part_name": "NVMe SSD 256GB",
     "category_name": "存储", "on_hand_qty": 1500, "reserved_qty": 0, "safety_stock_qty": 900},
    {"company_id": 9003, "part_number": "BAT-NB-56WH", "part_name": "56Wh笔记本电池",
     "category_name": "电池", "on_hand_qty": 1500, "reserved_qty": 0, "safety_stock_qty": 900},
    {"company_id": 9003, "part_number": "LCD-14-FHD", "part_name": "14寸FHD屏幕模组",
     "category_name": "显示", "on_hand_qty": 1500, "reserved_qty": 0, "safety_stock_qty": 900},
    {"company_id": 9003, "part_number": "KB-NB-01", "part_name": "笔记本键盘模组",
     "category_name": "输入", "on_hand_qty": 1500, "reserved_qty": 0, "safety_stock_qty": 900},
    # 9002 P_9103 主板零件 (需求 2700)
    {"company_id": 9002, "part_number": "PCB-Z690-FR4", "part_name": "Z690 PCB基板",
     "category_name": "PCB", "on_hand_qty": 3000, "reserved_qty": 0, "safety_stock_qty": 2000},
    {"company_id": 9002, "part_number": "MLCC-0805-X7R-105", "part_name": "MLCC电容 0805 1uF",
     "category_name": "被动元件", "on_hand_qty": 350000, "reserved_qty": 0, "safety_stock_qty": 300000},
    {"company_id": 9002, "part_number": "RES-0402-10K", "part_name": "贴片电阻 0402 10K",
     "category_name": "被动元件", "on_hand_qty": 250000, "reserved_qty": 0, "safety_stock_qty": 150000},
    {"company_id": 9002, "part_number": "CHIPSET-Z690", "part_name": "Z690芯片组",
     "category_name": "半导体芯片", "on_hand_qty": 200, "reserved_qty": 0, "safety_stock_qty": 500},
    {"company_id": 9002, "part_number": "PMIC-VR12", "part_name": "电源管理IC",
     "category_name": "半导体芯片", "on_hand_qty": 3000, "reserved_qty": 0, "safety_stock_qty": 2000},
    {"company_id": 9002, "part_number": "CONN-USB-C-01", "part_name": "USB-C连接器",
     "category_name": "连接器", "on_hand_qty": 12000, "reserved_qty": 0, "safety_stock_qty": 8000},
    # 9002 P_9104 模组零件 (需求 800)
    {"company_id": 9002, "part_number": "PCB-HDI-IMM", "part_name": "HDI PCB基板",
     "category_name": "PCB", "on_hand_qty": 1000, "reserved_qty": 0, "safety_stock_qty": 600},
    {"company_id": 9002, "part_number": "SOC-IMM-N5105", "part_name": "N5105 SoC",
     "category_name": "半导体芯片", "on_hand_qty": 1000, "reserved_qty": 0, "safety_stock_qty": 600},
    {"company_id": 9002, "part_number": "MLCC-0603-X5R-106", "part_name": "MLCC电容 0603 10uF",
     "category_name": "被动元件", "on_hand_qty": 50000, "reserved_qty": 0, "safety_stock_qty": 40000},
    {"company_id": 9002, "part_number": "IND-0805-2R2", "part_name": "电感 0805 2.2uH",
     "category_name": "被动元件", "on_hand_qty": 20000, "reserved_qty": 0, "safety_stock_qty": 12000},
    {"company_id": 9002, "part_number": "CONN-BTB-60P", "part_name": "板对板连接器 60P",
     "category_name": "连接器", "on_hand_qty": 2000, "reserved_qty": 0, "safety_stock_qty": 1200},
]


# ============================================================
# Upsert (按稳定键 delete + re-insert, 保证幂等且与定义一致)
# ============================================================
def upsert_products() -> None:
    with session_scope() as s:
        s.query(CompanyProduct).filter(CompanyProduct.id.in_(PRODUCT_IDS)).delete(
            synchronize_session=False
        )
        for p in PRODUCTS:
            s.add(CompanyProduct(**p))
        logger.info("产品种子 upsert 完成: %d 个", len(PRODUCTS))


def upsert_bom_items() -> None:
    with session_scope() as s:
        s.query(ProductBomItem).filter(ProductBomItem.product_id.in_(PRODUCT_IDS)).delete(
            synchronize_session=False
        )
        for b in BOM_ITEMS:
            s.add(ProductBomItem(**b))
        logger.info("BOM 种子 upsert 完成: %d 条", len(BOM_ITEMS))


def upsert_orders() -> None:
    with session_scope() as s:
        s.query(ProductionOrder).filter(
            ProductionOrder.company_id.in_(PHASE2_COMPANIES)
        ).delete(synchronize_session=False)
        for o in ORDERS:
            s.add(ProductionOrder(**o))
        logger.info("订单种子 upsert 完成: %d 条", len(ORDERS))


def upsert_forecasts() -> None:
    with session_scope() as s:
        s.query(DemandForecast).filter(
            DemandForecast.company_id.in_(PHASE2_COMPANIES)
        ).delete(synchronize_session=False)
        for f in FORECASTS:
            s.add(DemandForecast(**f))
        logger.info("预测种子 upsert 完成: %d 条", len(FORECASTS))


def upsert_inventory() -> None:
    with session_scope() as s:
        s.query(InventoryItem).filter(
            InventoryItem.company_id.in_(PHASE2_COMPANIES)
        ).delete(synchronize_session=False)
        for i in INVENTORY:
            s.add(InventoryItem(**i))
        logger.info("库存种子 upsert 完成: %d 条", len(INVENTORY))


def recalculate_all_shortages() -> None:
    """重算 9002/9003 缺件 (物化到 kb_shortages)。"""
    with session_scope() as s:
        s.query(Shortage).filter(Shortage.company_id.in_(PHASE2_COMPANIES)).delete(
            synchronize_session=False
        )
        for cid in PHASE2_COMPANIES:
            items = dc.recalculate_shortages(s, cid)
            logger.info("企业 %d 缺件重算: %d 条", cid, len(items))


def upsert_all() -> None:
    """Phase2 全量种子 (自包含: 含 Phase1 公司/关系)。"""
    init_db()
    p1_seed.upsert_companies()
    p1_seed.upsert_relationships()
    upsert_products()
    upsert_bom_items()
    upsert_orders()
    upsert_forecasts()
    upsert_inventory()
    recalculate_all_shortages()


def main() -> None:
    upsert_all()
    logger.info("企业驾驶舱 Phase2 种子完成")


if __name__ == "__main__":
    main()
