"""
企业驾驶舱 Phase2 种子数据 (产品 / BOM / 订单 / 预测 / 库存 / 缺件)。

围绕 Phase1 的 6 家企业构造真实演示场景, 每家都有可运营的最小数据包:
  - 9001 华芯微电子: 2 款芯片 (CPU/芯片组), BOM=晶圆/光刻胶/封装基板/测试资源
  - 9002 创捷主板模组: 2 款主板/模组, BOM=PCB/MLCC/电阻/芯片组/连接器
  - 9003 鼎云整机制造: 2 款整机 (台式机/笔记本), BOM=CPU/PCBA/内存/存储/电源...
  - 9004 远达供应链服务: 2 款物流服务 (仓储/干线配送), BOM=托盘位/叉车/车辆/司机 (服务资源结构)
  - 9005 星河数码渠道: 2 款分销整机, BOM=整机(采购自鼎云)/配件/包装
  - 9006 毅诚被动元件: 2 款被动元件 (MLCC/电阻), BOM=陶瓷粉料/电极浆料/基板

缺件场景按角色适配:
  - 9003 鼎云: CPU(无直接供应商)/PCBA(直接上游创捷)/DDR5(安全库存预警)
  - 9002 创捷: 芯片组(直接上游华芯)
  - 9001 华芯: 晶圆/封装基板/测试资源 (无在链直接供应商 -> 人工审核)
  - 9006 毅诚: 陶瓷粉料/银浆 (无在链直接供应商 -> 人工审核)
  - 9005 星河: 整机 (直接上游鼎云, 可发 RFQ+补货)
  - 9004 远达: 运力/履约资源 (托盘位/车辆/司机, 无在链直接供应商)

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

PHASE2_COMPANIES = (9001, 9002, 9003, 9004, 9005, 9006)
PRODUCT_IDS = (9101, 9102, 9103, 9104, 9201, 9202, 9301, 9302, 9401, 9402, 9501, 9502)


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
    # 9001 华芯微电子 (芯片设计商) - 2 款芯片产品
    {"id": 9201, "company_id": 9001, "product_name": "华芯 13代酷睿处理器 HX-CPU-13700",
     "product_model": "HX-CPU-13700", "product_type": "芯片",
     "description": "13代酷睿桌面级CPU, 服务主板/整机厂", "monthly_capacity": 2000,
     "unit": "颗", "status": "active"},
    {"id": 9202, "company_id": 9001, "product_name": "华芯 Z690芯片组 HX-CHIPSET-Z690",
     "product_model": "HX-CHIPSET-Z690", "product_type": "芯片组",
     "description": "Z690平台芯片组, 面向主板厂商", "monthly_capacity": 3000,
     "unit": "颗", "status": "active"},
    # 9006 毅诚被动元件 (元器件制造商) - 2 款被动元件 (单位: 批=万颗)
    {"id": 9301, "company_id": 9006, "product_name": "毅诚 MLCC电容 YC-MLCC-0805",
     "product_model": "YC-MLCC-0805", "product_type": "MLCC电容",
     "description": "0805 1uF X7R MLCC, 面向主板/EMS", "monthly_capacity": 50,
     "unit": "批", "status": "active"},
    {"id": 9302, "company_id": 9006, "product_name": "毅诚 贴片电阻 YC-RES-0402",
     "product_model": "YC-RES-0402", "product_type": "贴片电阻",
     "description": "0402 10K 1% 贴片电阻", "monthly_capacity": 80,
     "unit": "批", "status": "active"},
    # 9005 星河数码渠道 (渠道分销商) - 2 款分销整机
    {"id": 9401, "company_id": 9005, "product_name": "星河 商用台式机(分销) XH-DT-DIST",
     "product_model": "XH-DT-DIST", "product_type": "整机分销",
     "description": "商用台式机渠道分销, 采购自鼎云", "monthly_capacity": 800,
     "unit": "台", "status": "active"},
    {"id": 9402, "company_id": 9005, "product_name": "星河 商用笔记本(分销) XH-NB-DIST",
     "product_model": "XH-NB-DIST", "product_type": "整机分销",
     "description": "商用笔记本渠道分销, 采购自鼎云", "monthly_capacity": 600,
     "unit": "台", "status": "active"},
    # 9004 远达供应链服务 (物流服务商) - 2 款物流服务产品
    {"id": 9501, "company_id": 9004, "product_name": "远达 仓储服务 YD-WHS",
     "product_model": "YD-WHS", "product_type": "物流服务",
     "description": "电子元器件/整机仓储与库内操作, 按托计费", "monthly_capacity": 10000,
     "unit": "托", "status": "active"},
    {"id": 9502, "company_id": 9004, "product_name": "远达 干线配送 YD-TRUNK",
     "product_model": "YD-TRUNK", "product_type": "物流服务",
     "description": "厂际干线运输与末端配送, 按车次计费", "monthly_capacity": 500,
     "unit": "车次", "status": "active"},
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
    # 9201 华芯 CPU (4 条: 晶圆/光刻胶/封装基板/测试资源, 均无在链直接供应商 -> 演示 no_direct_supplier)
    {"product_id": 9201, "part_number": "WAFER-12-W", "part_name": "12寸晶圆",
     "category_name": "晶圆", "qty_per_unit": 1, "unit": "片",
     "is_critical": True, "preferred_supplier_company_id": None},
    {"product_id": 9201, "part_number": "PHOTORESIST-KR", "part_name": "KrF光刻胶",
     "category_name": "光刻材料", "qty_per_unit": 2, "unit": "瓶",
     "is_critical": False, "preferred_supplier_company_id": None},
    {"product_id": 9201, "part_number": "SUBSTRATE-FCCSP", "part_name": "FC-CSP封装基板",
     "category_name": "封装材料", "qty_per_unit": 1, "unit": "片",
     "is_critical": True, "preferred_supplier_company_id": None},
    {"product_id": 9201, "part_number": "TEST-FT-RESOURCE", "part_name": "成品测试资源(机时)",
     "category_name": "测试资源", "qty_per_unit": 1, "unit": "次",
     "is_critical": True, "preferred_supplier_company_id": None},
    # 9202 华芯 芯片组 (4 条)
    {"product_id": 9202, "part_number": "WAFER-12-W", "part_name": "12寸晶圆",
     "category_name": "晶圆", "qty_per_unit": 1, "unit": "片",
     "is_critical": True, "preferred_supplier_company_id": None},
    {"product_id": 9202, "part_number": "BONDING-WIRE-AU", "part_name": "金键合丝",
     "category_name": "封装材料", "qty_per_unit": 1, "unit": "卷",
     "is_critical": False, "preferred_supplier_company_id": None},
    {"product_id": 9202, "part_number": "SUBSTRATE-FCCSP", "part_name": "FC-CSP封装基板",
     "category_name": "封装材料", "qty_per_unit": 1, "unit": "片",
     "is_critical": True, "preferred_supplier_company_id": None},
    {"product_id": 9202, "part_number": "TEST-FT-RESOURCE", "part_name": "成品测试资源(机时)",
     "category_name": "测试资源", "qty_per_unit": 1, "unit": "次",
     "is_critical": True, "preferred_supplier_company_id": None},
    # 9301 毅诚 MLCC (3 条: 陶瓷粉料/镍浆/基板, 无在链供应商 -> 演示 no_direct_supplier)
    {"product_id": 9301, "part_number": "CERAMIC-POWDER-BT", "part_name": "钛酸钡陶瓷粉料",
     "category_name": "陶瓷粉料", "qty_per_unit": 5, "unit": "kg",
     "is_critical": True, "preferred_supplier_company_id": None},
    {"product_id": 9301, "part_number": "NI-PASTE-ELEC", "part_name": "镍电极浆料",
     "category_name": "电极浆料", "qty_per_unit": 2, "unit": "kg",
     "is_critical": True, "preferred_supplier_company_id": None},
    {"product_id": 9301, "part_number": "BASE-SUBSTRATE-MLCC", "part_name": "MLCC基板",
     "category_name": "基板", "qty_per_unit": 1, "unit": "片",
     "is_critical": False, "preferred_supplier_company_id": None},
    # 9302 毅诚 电阻 (3 条)
    {"product_id": 9302, "part_number": "CERAMIC-SUB-R", "part_name": "电阻陶瓷基板",
     "category_name": "陶瓷基板", "qty_per_unit": 1, "unit": "片",
     "is_critical": True, "preferred_supplier_company_id": None},
    {"product_id": 9302, "part_number": "AG-PASTE", "part_name": "导电银浆",
     "category_name": "电极浆料", "qty_per_unit": 3, "unit": "kg",
     "is_critical": True, "preferred_supplier_company_id": None},
    {"product_id": 9302, "part_number": "PROTECT-FILM-R", "part_name": "保护膜",
     "category_name": "辅材", "qty_per_unit": 2, "unit": "卷",
     "is_critical": False, "preferred_supplier_company_id": None},
    # 9401 星河 台式机分销 (3 条: 整机采购自鼎云 9003 直接上游 -> 可发 RFQ)
    {"product_id": 9401, "part_number": "PC-DT-DY-PRO", "part_name": "鼎云台式机整机",
     "category_name": "整机", "qty_per_unit": 1, "unit": "台",
     "is_critical": True, "preferred_supplier_company_id": 9003},
    {"product_id": 9401, "part_number": "ACC-MOUSE-KB", "part_name": "键鼠套装",
     "category_name": "配件", "qty_per_unit": 1, "unit": "套",
     "is_critical": False, "preferred_supplier_company_id": None},
    {"product_id": 9401, "part_number": "PACK-RETAIL-DT", "part_name": "台式机零售包装",
     "category_name": "包装", "qty_per_unit": 1, "unit": "个",
     "is_critical": False, "preferred_supplier_company_id": None},
    # 9402 星河 笔记本分销 (3 条: 整机采购自鼎云 9003 直接上游)
    {"product_id": 9402, "part_number": "PC-NB-DY-AIR", "part_name": "鼎云笔记本整机",
     "category_name": "整机", "qty_per_unit": 1, "unit": "台",
     "is_critical": True, "preferred_supplier_company_id": 9003},
    {"product_id": 9402, "part_number": "ACC-ADAPTER", "part_name": "电源适配器",
     "category_name": "配件", "qty_per_unit": 1, "unit": "个",
     "is_critical": False, "preferred_supplier_company_id": None},
    {"product_id": 9402, "part_number": "PACK-RETAIL-NB", "part_name": "笔记本零售包装",
     "category_name": "包装", "qty_per_unit": 1, "unit": "个",
     "is_critical": False, "preferred_supplier_company_id": None},
    # 9501 远达 仓储服务 (3 条服务资源: 托盘位/叉车/库管员 -> 运力/履约资源缺件)
    {"product_id": 9501, "part_number": "RES-WHS-PLT", "part_name": "仓储托盘位",
     "category_name": "仓储资源", "qty_per_unit": 100, "unit": "位",
     "is_critical": True, "preferred_supplier_company_id": None},
    {"product_id": 9501, "part_number": "RES-FORKLIFT", "part_name": "叉车",
     "category_name": "仓储设备", "qty_per_unit": 2, "unit": "台",
     "is_critical": False, "preferred_supplier_company_id": None},
    {"product_id": 9501, "part_number": "RES-WHS-STAFF", "part_name": "库管员",
     "category_name": "人力", "qty_per_unit": 3, "unit": "人",
     "is_critical": True, "preferred_supplier_company_id": None},
    # 9502 远达 干线配送 (3 条服务资源: 车辆/司机/燃油 -> 运力不足)
    {"product_id": 9502, "part_number": "RES-TRUCK", "part_name": "运输车辆",
     "category_name": "运输资源", "qty_per_unit": 10, "unit": "台",
     "is_critical": True, "preferred_supplier_company_id": None},
    {"product_id": 9502, "part_number": "RES-DRIVER", "part_name": "驾驶员",
     "category_name": "人力", "qty_per_unit": 10, "unit": "人",
     "is_critical": True, "preferred_supplier_company_id": None},
    {"product_id": 9502, "part_number": "RES-FUEL", "part_name": "燃油",
     "category_name": "耗材", "qty_per_unit": 200, "unit": "升",
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
    # 9001 华芯 (客户=创捷 9002, 采购CPU/芯片组)
    {"company_id": 9001, "product_id": 9201, "order_number": "HX-ORD-2026-001",
     "customer_company_id": 9002, "quantity": 800, "due_date": _date("2026-08-15"),
     "priority": "high", "status": "confirmed"},
    {"company_id": 9001, "product_id": 9202, "order_number": "HX-ORD-2026-002",
     "customer_company_id": 9002, "quantity": 1500, "due_date": _date("2026-08-10"),
     "priority": "urgent", "status": "confirmed"},
    {"company_id": 9001, "product_id": 9201, "order_number": "HX-ORD-2026-003",
     "customer_company_id": 9002, "quantity": 500, "due_date": _date("2026-09-20"),
     "priority": "normal", "status": "open"},
    # 9006 毅诚 (客户=创捷 9002, 采购MLCC/电阻; 单位=批)
    {"company_id": 9006, "product_id": 9301, "order_number": "YC-ORD-2026-001",
     "customer_company_id": 9002, "quantity": 30, "due_date": _date("2026-08-12"),
     "priority": "high", "status": "confirmed"},
    {"company_id": 9006, "product_id": 9302, "order_number": "YC-ORD-2026-002",
     "customer_company_id": 9002, "quantity": 40, "due_date": _date("2026-08-18"),
     "priority": "normal", "status": "confirmed"},
    {"company_id": 9006, "product_id": 9301, "order_number": "YC-ORD-2026-003",
     "customer_company_id": 9002, "quantity": 15, "due_date": _date("2026-09-15"),
     "priority": "normal", "status": "open"},
    # 9005 星河 (终端客户订单, customer=None; 分销台式机/笔记本)
    {"company_id": 9005, "product_id": 9401, "order_number": "XH-ORD-2026-001",
     "customer_company_id": None, "quantity": 500, "due_date": _date("2026-08-20"),
     "priority": "high", "status": "confirmed"},
    {"company_id": 9005, "product_id": 9402, "order_number": "XH-ORD-2026-002",
     "customer_company_id": None, "quantity": 400, "due_date": _date("2026-08-25"),
     "priority": "normal", "status": "confirmed"},
    {"company_id": 9005, "product_id": 9401, "order_number": "XH-ORD-2026-003",
     "customer_company_id": None, "quantity": 200, "due_date": _date("2026-09-20"),
     "priority": "normal", "status": "open"},
    # 9004 远达 (运输/仓储任务, 客户=创捷/鼎云/星河; 体现运力与履约需求)
    {"company_id": 9004, "product_id": 9501, "order_number": "YD-ORD-2026-001",
     "customer_company_id": 9002, "quantity": 50, "due_date": _date("2026-08-12"),
     "priority": "high", "status": "confirmed"},
    {"company_id": 9004, "product_id": 9502, "order_number": "YD-ORD-2026-002",
     "customer_company_id": 9003, "quantity": 30, "due_date": _date("2026-08-10"),
     "priority": "urgent", "status": "confirmed"},
    {"company_id": 9004, "product_id": 9502, "order_number": "YD-ORD-2026-003",
     "customer_company_id": 9005, "quantity": 20, "due_date": _date("2026-08-22"),
     "priority": "normal", "status": "confirmed"},
    {"company_id": 9004, "product_id": 9501, "order_number": "YD-ORD-2026-004",
     "customer_company_id": 9003, "quantity": 30, "due_date": _date("2026-09-15"),
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
    # 9001 华芯 预测 (创捷对 CPU/芯片组的后续需求)
    {"company_id": 9001, "product_id": 9201, "forecast_period": "2026-10",
     "forecast_quantity": 600, "confidence": 0.7, "source_type": "manual"},
    {"company_id": 9001, "product_id": 9202, "forecast_period": "2026-10",
     "forecast_quantity": 1000, "confidence": 0.65, "source_type": "manual"},
    # 9006 毅诚 预测 (创捷对 MLCC/电阻的后续需求)
    {"company_id": 9006, "product_id": 9301, "forecast_period": "2026-10",
     "forecast_quantity": 20, "confidence": 0.7, "source_type": "manual"},
    {"company_id": 9006, "product_id": 9302, "forecast_period": "2026-10",
     "forecast_quantity": 30, "confidence": 0.6, "source_type": "manual"},
    # 9005 星河 销售预测 (终端市场对整机的需求)
    {"company_id": 9005, "product_id": 9401, "forecast_period": "2026-10",
     "forecast_quantity": 300, "confidence": 0.7, "source_type": "manual"},
    {"company_id": 9005, "product_id": 9402, "forecast_period": "2026-10",
     "forecast_quantity": 200, "confidence": 0.65, "source_type": "manual"},
    # 9004 远达 物流需求预测 (仓储/配送后续运量)
    {"company_id": 9004, "product_id": 9501, "forecast_period": "2026-10",
     "forecast_quantity": 40, "confidence": 0.7, "source_type": "manual"},
    {"company_id": 9004, "product_id": 9502, "forecast_period": "2026-10",
     "forecast_quantity": 25, "confidence": 0.6, "source_type": "manual"},
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
    # 9001 华芯 芯片制造资源库存 (晶圆/基板/测试资源偏低 -> 缺件, 无在链直接供应商)
    {"company_id": 9001, "part_number": "WAFER-12-W", "part_name": "12寸晶圆",
     "category_name": "晶圆", "on_hand_qty": 500, "reserved_qty": 0, "safety_stock_qty": 1500},
    {"company_id": 9001, "part_number": "PHOTORESIST-KR", "part_name": "KrF光刻胶",
     "category_name": "光刻材料", "on_hand_qty": 4000, "reserved_qty": 0, "safety_stock_qty": 2000},
    {"company_id": 9001, "part_number": "SUBSTRATE-FCCSP", "part_name": "FC-CSP封装基板",
     "category_name": "封装材料", "on_hand_qty": 2000, "reserved_qty": 0, "safety_stock_qty": 1500},
    {"company_id": 9001, "part_number": "TEST-FT-RESOURCE", "part_name": "成品测试资源(机时)",
     "category_name": "测试资源", "on_hand_qty": 3000, "reserved_qty": 0, "safety_stock_qty": 2000},
    {"company_id": 9001, "part_number": "BONDING-WIRE-AU", "part_name": "金键合丝",
     "category_name": "封装材料", "on_hand_qty": 3000, "reserved_qty": 0, "safety_stock_qty": 1500},
    # 9006 毅诚 被动元件原材料库存 (陶瓷粉料/镍浆/银浆偏低 -> 缺件)
    {"company_id": 9006, "part_number": "CERAMIC-POWDER-BT", "part_name": "钛酸钡陶瓷粉料",
     "category_name": "陶瓷粉料", "on_hand_qty": 100, "reserved_qty": 0, "safety_stock_qty": 200},
    {"company_id": 9006, "part_number": "NI-PASTE-ELEC", "part_name": "镍电极浆料",
     "category_name": "电极浆料", "on_hand_qty": 80, "reserved_qty": 0, "safety_stock_qty": 100},
    {"company_id": 9006, "part_number": "BASE-SUBSTRATE-MLCC", "part_name": "MLCC基板",
     "category_name": "基板", "on_hand_qty": 200, "reserved_qty": 0, "safety_stock_qty": 100},
    {"company_id": 9006, "part_number": "CERAMIC-SUB-R", "part_name": "电阻陶瓷基板",
     "category_name": "陶瓷基板", "on_hand_qty": 100, "reserved_qty": 0, "safety_stock_qty": 60},
    {"company_id": 9006, "part_number": "AG-PASTE", "part_name": "导电银浆",
     "category_name": "电极浆料", "on_hand_qty": 50, "reserved_qty": 0, "safety_stock_qty": 100},
    {"company_id": 9006, "part_number": "PROTECT-FILM-R", "part_name": "保护膜",
     "category_name": "辅材", "on_hand_qty": 300, "reserved_qty": 0, "safety_stock_qty": 150},
    # 9005 星河 分销整机库存 (整机库存偏低 -> 缺件, 首选供应商=鼎云 9003 直接上游)
    {"company_id": 9005, "part_number": "PC-DT-DY-PRO", "part_name": "鼎云台式机整机",
     "category_name": "整机", "on_hand_qty": 150, "reserved_qty": 0, "safety_stock_qty": 400},
    {"company_id": 9005, "part_number": "PC-NB-DY-AIR", "part_name": "鼎云笔记本整机",
     "category_name": "整机", "on_hand_qty": 100, "reserved_qty": 0, "safety_stock_qty": 300},
    {"company_id": 9005, "part_number": "ACC-MOUSE-KB", "part_name": "键鼠套装",
     "category_name": "配件", "on_hand_qty": 1200, "reserved_qty": 0, "safety_stock_qty": 500},
    {"company_id": 9005, "part_number": "ACC-ADAPTER", "part_name": "电源适配器",
     "category_name": "配件", "on_hand_qty": 700, "reserved_qty": 0, "safety_stock_qty": 300},
    {"company_id": 9005, "part_number": "PACK-RETAIL-DT", "part_name": "台式机零售包装",
     "category_name": "包装", "on_hand_qty": 1500, "reserved_qty": 0, "safety_stock_qty": 500},
    {"company_id": 9005, "part_number": "PACK-RETAIL-NB", "part_name": "笔记本零售包装",
     "category_name": "包装", "on_hand_qty": 800, "reserved_qty": 0, "safety_stock_qty": 300},
    # 9004 远达 物流服务资源库存 (托盘位/车辆/司机偏低 -> 运力不足/履约风险)
    {"company_id": 9004, "part_number": "RES-WHS-PLT", "part_name": "仓储托盘位",
     "category_name": "仓储资源", "on_hand_qty": 8000, "reserved_qty": 0, "safety_stock_qty": 5000},
    {"company_id": 9004, "part_number": "RES-FORKLIFT", "part_name": "叉车",
     "category_name": "仓储设备", "on_hand_qty": 300, "reserved_qty": 0, "safety_stock_qty": 150},
    {"company_id": 9004, "part_number": "RES-WHS-STAFF", "part_name": "库管员",
     "category_name": "人力", "on_hand_qty": 200, "reserved_qty": 0, "safety_stock_qty": 150},
    {"company_id": 9004, "part_number": "RES-TRUCK", "part_name": "运输车辆",
     "category_name": "运输资源", "on_hand_qty": 400, "reserved_qty": 0, "safety_stock_qty": 300},
    {"company_id": 9004, "part_number": "RES-DRIVER", "part_name": "驾驶员",
     "category_name": "人力", "on_hand_qty": 500, "reserved_qty": 0, "safety_stock_qty": 300},
    {"company_id": 9004, "part_number": "RES-FUEL", "part_name": "燃油",
     "category_name": "耗材", "on_hand_qty": 20000, "reserved_qty": 0, "safety_stock_qty": 8000},
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
