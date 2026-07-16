"""
双语知识生成器 (Product Knowledge Generator + Business Knowledge Generator)。

两条路径:
  A. 真实 LLM (DASHSCOPE_API_KEY 存在): 调用 Qwen 生成结构化 JSON, 业务边界内约束
  B. 确定性模板 (降级): 基于 segment 边界生成真实、结构化、可控的知识 (当前环境生效)

生成产物 (结构化 dict) -> 由 chunker.py 语义切片。
绝对业务边界: 生成内容不超出 boundary.allowed_business_scope / product_categories。
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any

from kb.boundary import BusinessBoundary, build_boundary
from kb.config import KB_DEMO_MODE, KB_LLM_FOR_GENERATION, llm_available
from kb.llm_client import chat_json
from kb.models import CompanyCache, KnowledgeManual, Product

logger = logging.getLogger("kb.generator")


# ============================================================
# 源哈希 (用于增量更新判断)
# ============================================================
def source_hash(company: CompanyCache) -> str:
    payload = json.dumps(
        {
            "id": company.id,
            "name": company.name,
            "description": company.description,
            "segment_code": company.segment_code,
            "source_hash": company.source_hash,
            "demo_mode": KB_DEMO_MODE,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ============================================================
# 真实 LLM 路径 -- 生成产品知识 JSON
# ============================================================
_PRODUCT_LLM_SYSTEM_ZH = """你是企业知识库工程师。根据公司信息和业务边界, 生成结构化产品知识 JSON。
严格遵守业务边界: 只生成 boundary.product_categories 范围内的产品, 不得跨行业。
返回 JSON: {"manual_title": str, "products": [{"product_name","product_series","product_model","category","positioning","overview","specification":{...},"model_differences","price":{currency,price_min,price_max,price_type,confidence},"installation","procurement":{moq,lead_time,payment,packaging,customization},"faq":[...]}]}
产品数量 3-5 个, 每个含 1-2 个型号。所有内容用中文。价格标注 price_type=demo, confidence 为 0-1。"""

_PRODUCT_LLM_SYSTEM_EN = """You are an enterprise knowledge engineer. Generate structured product knowledge JSON from the company info and business boundary.
Strictly obey the business boundary: only products within boundary.product_categories. No cross-industry invention.
Return JSON: {"manual_title": str, "products": [{"product_name","product_series","product_model","category","positioning","overview","specification":{...},"model_differences","price":{currency,price_min,price_max,price_type,confidence},"installation","procurement":{moq,lead_time,payment,packaging,customization},"faq":[...]}]}
3-5 products, each with 1-2 models. All content in English. price_type=demo, confidence 0-1."""

_BUSINESS_LLM_SYSTEM_ZH = """你是企业知识库工程师。根据公司信息和业务边界, 生成业务知识 JSON。
业务类型必须来自 boundary.allowed_business_scope, 不得超出。
返回 JSON: {"manual_title": str, "business_types": [{"business_type","definition","applicable_customers","prerequisite_info":[...],"process_steps":[...],"internal_logic","communication","exceptions":[...],"faq":[...]}]}
3-5 个业务类型。所有内容用中文。"""

_BUSINESS_LLM_SYSTEM_EN = """You are an enterprise knowledge engineer. Generate business knowledge JSON from the company info and business boundary.
Business types must come from boundary.allowed_business_scope.
Return JSON: {"manual_title": str, "business_types": [{"business_type","definition","applicable_customers","prerequisite_info":[...],"process_steps":[...],"internal_logic","communication","exceptions":[...],"faq":[...]}]}
3-5 business types. All content in English."""


async def _llm_generate(company: CompanyCache, boundary: BusinessBoundary, manual_type: str, lang: str) -> dict | None:
    # KB_LLM_FOR_GENERATION=off -> 强制模板; =auto 且 llm 可用 -> 用 LLM
    if KB_LLM_FOR_GENERATION == "off":
        return None
    if not llm_available():
        return None
    sys_map = {
        ("product", "zh"): _PRODUCT_LLM_SYSTEM_ZH,
        ("product", "en"): _PRODUCT_LLM_SYSTEM_EN,
        ("business", "zh"): _BUSINESS_LLM_SYSTEM_ZH,
        ("business", "en"): _BUSINESS_LLM_SYSTEM_EN,
    }
    system = sys_map.get((manual_type, lang))
    if not system:
        return None
    user = json.dumps(
        {
            "company": {
                "name": company.name,
                "name_en": company.name_en or company.name,
                "description": company.description,
                "website": company.website,
                "role": boundary.role,
            },
            "boundary": boundary.to_dict(),
        },
        ensure_ascii=False,
    )
    return await chat_json(system, user, heavy=True, temperature=0.3, max_tokens=6000)


# ============================================================
# 确定性模板路径 -- 按 segment 生成
# ============================================================
# 每 segment 的产品模板 (series + models + spec 字段 + 价格区间)
# 这些模板基于行业公开常识 (industry_segments typical_products), 非编造具体参数。
_SEGMENT_PRODUCTS: dict[str, list[dict]] = {
    "passive_components": [
        {
            "series_zh": "GRM 通用型 MLCC", "series_en": "GRM General-Purpose MLCC",
            "models": [
                {"model": "GRM188R71H104KA93D", "spec_zh": {"封装": "0603", "容值": "100nF", "精度": "±10%", "温度系数": "X7R", "额定电压": "50V"}, "spec_en": {"Package": "0603", "Capacitance": "100nF", "Tolerance": "±10%", "Temp Coeff": "X7R", "Rated Voltage": "50V"}, "price": 0.028},
                {"model": "GRM188R71C105KA93D", "spec_zh": {"封装": "0603", "容值": "1uF", "精度": "±10%", "温度系数": "X5R", "额定电压": "16V"}, "spec_en": {"Package": "0603", "Capacitance": "1uF", "Tolerance": "±10%", "Temp Coeff": "X5R", "Rated Voltage": "16V"}, "price": 0.035},
            ],
            "category": "MLCC", "positioning_zh": "去耦/滤波通用, 适配消费电子与工业控制电源电路", "positioning_en": "Decoupling/filtering for consumer and industrial power circuits",
        },
        {
            "series_zh": "高容值型 MLCC", "series_en": "High-Capacitance MLCC",
            "models": [
                {"model": "GRM21BR61A106KE73L", "spec_zh": {"封装": "0805", "容值": "10uF", "精度": "±20%", "温度系数": "X5R", "额定电压": "10V"}, "spec_en": {"Package": "0805", "Capacitance": "10uF", "Tolerance": "±20%", "Temp Coeff": "X5R", "Rated Voltage": "10V"}, "price": 0.08},
            ],
            "category": "MLCC", "positioning_zh": "大容量去耦, 适配 SoC/FPGA 核心电源", "positioning_en": "High-cap bulk decoupling for SoC/FPGA core power",
        },
        {
            "series_zh": "贴片电阻 RN 系列", "series_en": "Chip Resistor RN Series",
            "models": [
                {"model": "RC0603FR-0710KL", "spec_zh": {"封装": "0603", "阻值": "10kΩ", "精度": "±1%", "额定功率": "1/10W"}, "spec_en": {"Package": "0603", "Resistance": "10kΩ", "Tolerance": "±1%", "Rated Power": "1/10W"}, "price": 0.012},
            ],
            "category": "贴片电阻", "positioning_zh": "通用分压/限流, 适配信号与偏置电路", "positioning_en": "General voltage divider/current limiting for signal and bias circuits",
        },
    ],
    "memory_storage": [
        {
            "series_zh": "DDR5 DRAM 颗粒", "series_en": "DDR5 DRAM Die",
            "models": [
                {"model": "DDR5-6400 16Gb", "spec_zh": {"类型": "DDR5", "容量": "16Gb", "速率": "6400Mbps", "电压": "1.1V"}, "spec_en": {"Type": "DDR5", "Density": "16Gb", "Speed": "6400Mbps", "Voltage": "1.1V"}, "price": 4.5},
                {"model": "DDR5-5600 8Gb", "spec_zh": {"类型": "DDR5", "容量": "8Gb", "速率": "5600Mbps", "电压": "1.1V"}, "spec_en": {"Type": "DDR5", "Density": "8Gb", "Speed": "5600Mbps", "Voltage": "1.1V"}, "price": 2.8},
            ],
            "category": "DRAM", "positioning_zh": "PC/服务器主存, 适配计算平台内存子系统", "positioning_en": "PC/server main memory for computing platforms",
        },
        {
            "series_zh": "3D NAND Flash", "series_en": "3D NAND Flash",
            "models": [
                {"model": "232L TLC 512Gb", "spec_zh": {"类型": "3D NAND TLC", "容量": "512Gb", "层数": "232层", "接口": "ONFI"}, "spec_en": {"Type": "3D NAND TLC", "Density": "512Gb", "Layers": "232L", "Interface": "ONFI"}, "price": 18.0},
            ],
            "category": "NAND Flash", "positioning_zh": "SSD/移动存储主控配对, 适配大容量存储产品", "positioning_en": "SSD/mobile storage, high-capacity storage products",
        },
        {
            "series_zh": "消费级 SSD", "series_en": "Consumer SSD",
            "models": [
                {"model": "SSD-512GB-NVMe", "spec_zh": {"形态": "M.2 2280", "容量": "512GB", "接口": "PCIe Gen4 NVMe", "顺序读取": "3500MB/s"}, "spec_en": {"Form Factor": "M.2 2280", "Capacity": "512GB", "Interface": "PCIe Gen4 NVMe", "Seq Read": "3500MB/s"}, "price": 32.0},
            ],
            "category": "SSD", "positioning_zh": "PC/笔电主存储, 适配消费级整机", "positioning_en": "PC/laptop main storage for consumer devices",
        },
    ],
    "semiconductor_chips": [
        {
            "series_zh": "桌面 CPU", "series_en": "Desktop CPU",
            "models": [
                {"model": "CPU-8C-3.6GHz", "spec_zh": {"核心": "8核", "基础频率": "3.6GHz", "加速频率": "5.0GHz", "TDP": "65W", "制程": "7nm"}, "spec_en": {"Cores": "8", "Base Clock": "3.6GHz", "Boost Clock": "5.0GHz", "TDP": "65W", "Process": "7nm"}, "price": 220.0},
                {"model": "CPU-6C-3.2GHz", "spec_zh": {"核心": "6核", "基础频率": "3.2GHz", "加速频率": "4.6GHz", "TDP": "65W", "制程": "7nm"}, "spec_en": {"Cores": "6", "Base Clock": "3.2GHz", "Boost Clock": "4.6GHz", "TDP": "65W", "Process": "7nm"}, "price": 160.0},
            ],
            "category": "CPU", "positioning_zh": "桌面/工作站计算, 适配主流整机与 DIY 市场", "positioning_en": "Desktop/workstation computing for mainstream PCs and DIY",
        },
        {
            "series_zh": "GPU 加速卡", "series_en": "GPU Accelerator",
            "models": [
                {"model": "GPU-24GB-AI", "spec_zh": {"显存": "24GB GDDR6", "加速计算": "AI训练/推理", "TDP": "300W", "接口": "PCIe Gen5"}, "spec_en": {"Memory": "24GB GDDR6", "Workload": "AI training/inference", "TDP": "300W", "Interface": "PCIe Gen5"}, "price": 1200.0},
            ],
            "category": "GPU", "positioning_zh": "AI/数据中心加速, 适配训练与推理服务器", "positioning_en": "AI/datacenter acceleration for training and inference servers",
        },
        {
            "series_zh": "移动 SoC", "series_en": "Mobile SoC",
            "models": [
                {"model": "SoC-Mobile-8C", "spec_zh": {"核心": "8核 (1大+3中+4小)", "制程": "4nm", "AI算力": "45TOPS"}, "spec_en": {"Cores": "8 (1+3+4)", "Process": "4nm", "AI Compute": "45TOPS"}, "price": 90.0},
            ],
            "category": "SoC", "positioning_zh": "移动/PC 平台主控, 适配轻薄本与移动终端", "positioning_en": "Mobile/PC platform controller for ultrabooks and mobile devices",
        },
    ],
    "connectors_cables": [
        {
            "series_zh": "USB Type-C 连接器", "series_en": "USB Type-C Connector",
            "models": [
                {"model": "TC-16P-SMT", "spec_zh": {"类型": "USB Type-C 16Pin", "安装": "SMT贴片", "电流": "5A", "插拔次数": "10000次"}, "spec_en": {"Type": "USB Type-C 16Pin", "Mount": "SMT", "Current": "5A", "Mating Cycles": "10000"}, "price": 0.45},
                {"model": "TC-24P-DIP", "spec_zh": {"类型": "USB Type-C 24Pin", "安装": "DIP直插", "电流": "5A", "插拔次数": "10000次"}, "spec_en": {"Type": "USB Type-C 24Pin", "Mount": "DIP", "Current": "5A", "Mating Cycles": "10000"}, "price": 0.55},
            ],
            "category": "连接器", "positioning_zh": "数据/充电接口, 适配手机笔电及外设", "positioning_en": "Data/charging interface for phones, laptops and peripherals",
        },
        {
            "series_zh": "板对板连接器", "series_en": "Board-to-Board Connector",
            "models": [
                {"model": "BTB-0.4mm-40P", "spec_zh": {"间距": "0.4mm", "针数": "40Pin", "堆叠高度": "5mm", "安装": "SMT"}, "spec_en": {"Pitch": "0.4mm", "Pins": "40", "Stack Height": "5mm", "Mount": "SMT"}, "price": 0.32},
            ],
            "category": "连接器", "positioning_zh": "板级互连, 适配模组化设计与屏幕排线", "positioning_en": "Board-level interconnect for modular design and display flex",
        },
        {
            "series_zh": "FFC 柔性排线", "series_en": "FFC Flat Flexible Cable",
            "models": [
                {"model": "FFC-0.5mm-30P-50mm", "spec_zh": {"间距": "0.5mm", "芯数": "30", "长度": "50mm", "类型": "FFC"}, "spec_en": {"Pitch": "0.5mm", "Cores": "30", "Length": "50mm", "Type": "FFC"}, "price": 0.18},
            ],
            "category": "线束", "positioning_zh": "内部信号传输, 适配屏幕/摄像头/键盘模组连接", "positioning_en": "Internal signal routing for display/camera/keyboard modules",
        },
    ],
    "pcb_pcba": [
        {
            "series_zh": "多层 PCB 硬板", "series_en": "Multilayer Rigid PCB",
            "models": [
                {"model": "PCB-4L-FR4-1.6mm", "spec_zh": {"层数": "4层", "板材": "FR4", "板厚": "1.6mm", "铜厚": "1oz", "最小线宽": "0.1mm"}, "spec_en": {"Layers": "4", "Material": "FR4", "Thickness": "1.6mm", "Copper": "1oz", "Min Trace": "0.1mm"}, "price": 0.6},
                {"model": "PCB-6L-HDI-1.0mm", "spec_zh": {"层数": "6层 HDI", "板材": "FR4", "板厚": "1.0mm", "铜厚": "1oz", "最小线宽": "0.075mm"}, "spec_en": {"Layers": "6 HDI", "Material": "FR4", "Thickness": "1.0mm", "Copper": "1oz", "Min Trace": "0.075mm"}, "price": 1.8},
            ],
            "category": "PCB硬板", "positioning_zh": "主板/显卡/电源板, 适配消费与工业电子产品", "positioning_en": "Motherboard/graphics/power boards for consumer and industrial electronics",
        },
        {
            "series_zh": "FPC 柔性板", "series_en": "FPC Flexible PCB",
            "models": [
                {"model": "FPC-2L-0.1mm", "spec_zh": {"层数": "2层", "材料": "PI", "板厚": "0.1mm", "弯折次数": "≥10万次"}, "spec_en": {"Layers": "2", "Material": "PI", "Thickness": "0.1mm", "Bend Cycles": "≥100k"}, "price": 0.25},
            ],
            "category": "PCB硬板", "positioning_zh": "活动部件连接, 适配屏幕/摄像头/折叠模组", "positioning_en": "Moving-part connection for display/camera/folding modules",
        },
        {
            "series_zh": "PCBA 代工服务", "series_en": "PCBA Assembly Service",
            "models": [
                {"model": "PCBA-SMT-0402", "spec_zh": {"工艺": "SMT贴片", "最小封装": "0402", "贴片精度": "±0.05mm", "检测": "AOI+X-Ray"}, "spec_en": {"Process": "SMT", "Min Package": "0402", "Placement Accuracy": "±0.05mm", "Inspection": "AOI+X-Ray"}, "price": 0.05},
            ],
            "category": "PCBA代工", "positioning_zh": "板级加工, 适配中小批量打样与量产", "positioning_en": "Board-level assembly for prototyping and mass production",
        },
    ],
    "sourcing_distribution": [
        {
            "series_zh": "授权分销服务", "series_en": "Authorized Distribution Service",
            "models": [
                {"model": "AUTH-DIST-MLCC", "spec_zh": {"服务": "原厂授权分销", "品类": "MLCC/电阻/连接器", "供货周期": "2-4周", "MOQ": "按原厂MOQ"}, "spec_en": {"Service": "Authorized distribution", "Category": "MLCC/resistor/connector", "Lead Time": "2-4 weeks", "MOQ": "Per OEM MOQ"}, "price": 0.0},
            ],
            "category": "授权分销", "positioning_zh": "正品原厂货源, 适配规模化稳定采购", "positioning_en": "Authentic OEM-channel sourcing for stable volume procurement",
        },
        {
            "series_zh": "现货贸易", "series_en": "Spot Trading",
            "models": [
                {"model": "SPOT-FAST-1D", "spec_zh": {"服务": "现货库存发货", "品类": "通用元器件", "发货": "24-48小时", "起订": "1个起"}, "spec_en": {"Service": "Spot stock shipping", "Category": "General components", "Shipping": "24-48h", "MOQ": "From 1 piece"}, "price": 0.0},
            ],
            "category": "现货贸易", "positioning_zh": "缺料应急, 适配小批量打样与急单交付", "positioning_en": "Shortage emergency, small-batch prototyping and urgent orders",
        },
        {
            "series_zh": "BOM 配单服务", "series_en": "BOM Consolidation Service",
            "models": [
                {"model": "BOM-CONSOLIDATE", "spec_zh": {"服务": "BOM一站式配单", "支持": "替代料推荐", "交付": "齐套发货", "报告": "BOM分析报告"}, "spec_en": {"Service": "One-stop BOM consolidation", "Includes": "Cross-reference", "Delivery": "Kit shipment", "Report": "BOM analysis"}, "price": 0.0},
            ],
            "category": "BOM配单", "positioning_zh": "整 BOM 一次到位, 适配新项目导入与中小厂商", "positioning_en": "Complete BOM in one go for NPI and SMB manufacturers",
        },
    ],
    "odm_ems_manufacturing": [
        {
            "series_zh": "ODM 设计方案", "series_en": "ODM Design Solution",
            "models": [
                {"model": "ODM-Notebook-14", "spec_zh": {"方案": "14寸笔电ODM", "阶段": "ID/MD/HW/BIOS", "交付": "EVT/DVT/PVT", "周期": "6-9月"}, "spec_en": {"Solution": "14-inch laptop ODM", "Stage": "ID/MD/HW/BIOS", "Delivery": "EVT/DVT/PVT", "Timeline": "6-9 months"}, "price": 0.0},
                {"model": "ODM-Server-AI", "spec_zh": {"方案": "AI服务器ODM", "阶段": "HW/Thermal/BIOS", "交付": "EVT/DVT/PVT", "周期": "9-12月"}, "spec_en": {"Solution": "AI server ODM", "Stage": "HW/Thermal/BIOS", "Delivery": "EVT/DVT/PVT", "Timeline": "9-12 months"}, "price": 0.0},
            ],
            "category": "ODM设计", "positioning_zh": "整机方案设计, 适配品牌方新品开发", "positioning_en": "Full-system design for brand new product development",
        },
        {
            "series_zh": "EMS 代工组装", "series_en": "EMS Assembly",
            "models": [
                {"model": "EMS-SMT-FAT", "spec_zh": {"服务": "SMT贴片+整机组装", "工艺": "0201/BGA", "产能": "日产万台级", "测试": "FCT/老化"}, "spec_en": {"Service": "SMT + final assembly", "Process": "0201/BGA", "Capacity": "10k+/day", "Test": "FCT/burn-in"}, "price": 0.0},
            ],
            "category": "EMS代工", "positioning_zh": "规模化制造, 适配品牌方量产外包", "positioning_en": "Scale manufacturing for brand mass-production outsourcing",
        },
        {
            "series_zh": "测试与包装服务", "series_en": "Testing & Packaging Service",
            "models": [
                {"model": "TEST-BURNIN-PACK", "spec_zh": {"服务": "老化测试+包装入库", "项目": "FCT/EMC/老化", "包装": "彩盒/定制", "物流": "直发"}, "spec_en": {"Service": "Burn-in + packaging", "Items": "FCT/EMC/burn-in", "Packaging": "Retail box/custom", "Logistics": "Direct ship"}, "price": 0.0},
            ],
            "category": "EMS代工", "positioning_zh": "后段制程, 适配成品交付前质量保障", "positioning_en": "Back-end process for pre-delivery quality assurance",
        },
    ],
}


def _name(company: CompanyCache, lang: str) -> str:
    if lang == "en":
        return company.name_en or company.name
    return company.name


# industry 中文名 -> segment_code (兼容旧 boundary 数据)
_INDUSTRY_TO_CODE = {
    "被动元件": "passive_components",
    "内存与存储": "memory_storage",
    "半导体芯片": "semiconductor_chips",
    "连接器与线束": "connectors_cables",
    "PCB与PCBA": "pcb_pcba",
    "采购寻源与分销": "sourcing_distribution",
    "ODM/EMS制造组装": "odm_ems_manufacturing",
}


def _segment_for(boundary: BusinessBoundary) -> str:
    """从 boundary 解析 segment_code (优先 segment_code, 回退 industry 中文名映射)。"""
    if boundary.segment_code:
        return boundary.segment_code
    return _INDUSTRY_TO_CODE.get(boundary.industry, "passive_components")


def _template_products(company: CompanyCache, boundary: BusinessBoundary, lang: str) -> dict:
    """确定性生成产品知识。"""
    seg = _segment_for(boundary)
    templates = _SEGMENT_PRODUCTS.get(seg, _SEGMENT_PRODUCTS["passive_components"])
    cname = _name(company, lang)
    is_en = lang == "en"
    products: list[dict] = []
    for tmpl in templates:
        series = tmpl["series_en"] if is_en else tmpl["series_zh"]
        for m in tmpl["models"]:
            spec = m["spec_en"] if is_en else m["spec_zh"]
            positioning = tmpl["positioning_en"] if is_en else tmpl["positioning_zh"]
            model = m["model"]
            price_val = m["price"]
            price_min = round(price_val * 0.9, 4) if price_val else None
            price_max = round(price_val * 1.15, 4) if price_val else None

            if is_en:
                pname = f"{series} {model}"
                overview = (
                    f"{pname} is a {tmpl['category']} product of {cname} ({boundary.industry_en}), "
                    f"{positioning}. It addresses {('bulk decoupling and filtering' if tmpl['category'] in ('MLCC',) else 'high-reliability interconnect')}, "
                    f"core value: stable supply, datasheet-grade specifications, cross-reference support. "
                    f"Applicable scenarios: consumer electronics, industrial control, and computing platforms. "
                    f"Limitations: operate within rated voltage/temperature; verify DC bias characteristics for MLCC."
                )
                spec_text = "; ".join(f"{k}={v}" for k, v in spec.items())
                model_diff = (
                    f"Model {model} differs by {'capacitance and package' if tmpl['category']=='MLCC' else 'specification'}; "
                    f"choose higher capacitance for bulk decoupling, smaller package for space-constrained designs."
                )
                installation = (
                    f"Mounting: SMT reflow. Ensure pad per datasheet footprint; "
                    f"reflow profile within {('260°C peak') if tmpl['category'] in ('MLCC','贴片电阻') else 'spec range'}; "
                    f"avoid mechanical stress post-assembly. No field-serviceable parts."
                ) if tmpl["category"] not in ("ODM设计", "EMS代工", "PCBA代工", "授权分销", "现货贸易", "BOM配单") else (
                    f"Deployment: integrate per {cname}'s design guideline; "
                    f"for services, provide BOM/gerber/forecast to initiate."
                )
                procurement = {
                    "moq": "Per OEM MOQ",
                    "lead_time": "2-4 weeks (authorized); 24-48h (spot)",
                    "payment": "Net 30 / T/T",
                    "packaging": "Tape & reel",
                    "customization": "Spec customization available for qualified volume",
                }
                faq = [
                    f"Q: What is the MOQ for {model}? A: Typically per OEM MOQ; spot orders accept smaller qty.",
                    f"Q: Is {model} in stock? A: Check real-time stock via sales; spot channel for urgent needs.",
                    f"Q: Can {cname} provide a cross-reference? A: Yes, within the same category and spec envelope.",
                ]
            else:
                pname = f"{series} {model}"
                overview = (
                    f"{pname} 是 {cname}（{boundary.industry}）的 {tmpl['category']} 产品，"
                    f"{positioning}。解决{'大容量去耦与电源滤波' if tmpl['category'] in ('MLCC',) else '高可靠互连与信号传输'}问题，"
                    f"核心价值：稳定供货、datasheet 级规格参数、替代料交叉支持。"
                    f"适用场景：消费电子、工业控制、计算平台。"
                    f"使用限制：须在额定电压/温度范围内工作；MLCC 需评估 DC 偏压特性。"
                )
                spec_text = "；".join(f"{k}={v}" for k, v in spec.items())
                model_diff = (
                    f"型号 {model} 差异主要体现在{'容值与封装' if tmpl['category']=='MLCC' else '规格参数'}；"
                    f"去耦选大容值，空间紧张选小封装，高速信号选低损耗型号。"
                )
                installation = (
                    f"安装方式：SMT 回流焊。按 datasheet 焊盘设计；"
                    f"回流曲线峰值不超过{'260℃' if tmpl['category'] in ('MLCC','贴片电阻') else '规格上限'}；"
                    f"装配后避免机械应力。无可现场维修部件。"
                ) if tmpl["category"] not in ("ODM设计", "EMS代工", "PCBA代工", "授权分销", "现货贸易", "BOM配单") else (
                    f"接入方式：按 {cname} 设计规范集成；"
                    f"服务类产品需提供 BOM/gerber/需求预测后启动。"
                )
                procurement = {
                    "moq": "按原厂 MOQ",
                    "lead_time": "授权 2-4 周；现货 24-48 小时",
                    "payment": "月结 30 天 / 电汇",
                    "packaging": "编带包装",
                    "customization": "合格量产可定制规格",
                }
                faq = [
                    f"问：{model} 的 MOQ 是多少？答：一般按原厂 MOQ，现货渠道可小批量。",
                    f"问：{model} 有库存吗？答：实时库存请联系销售确认，急单走现货渠道。",
                    f"问：{cname} 能提供替代料吗？答：可以，在同类同规格范围内交叉推荐。",
                ]

            products.append({
                "product_name": pname,
                "product_series": series,
                "product_model": model,
                "category": tmpl["category"],
                "positioning": positioning,
                "overview": overview,
                "specification": spec,
                "spec_text": spec_text,
                "model_differences": model_diff,
                "price": {
                    "currency": "USD",
                    "price": price_val if price_val else None,
                    "price_min": price_min,
                    "price_max": price_max,
                    "price_type": "demo" if not price_val else "demo",
                    "source_type": "ai_generated_demo",
                    "confidence": 0.65,
                },
                "installation": installation,
                "procurement": procurement,
                "faq": faq,
            })

    title = f"{cname} 产品知识手册" if not is_en else f"{cname} Product Knowledge Manual"
    return {"manual_title": title, "products": products, "source": "template"}


# 业务类型模板 (按 segment 的 allowed_business_scope)
_BUSINESS_TEMPLATES: dict[str, list[dict]] = {
    "passive_components": [
        ("产品采购", "Product Procurement", "标准元器件批量采购"),
        ("样品申请", "Sample Request", "研发阶段小批量样品"),
        ("替代料推荐", "Cross-Reference", "缺料/降本替代方案"),
        ("定制规格", "Custom Specification", "特殊容值/精度/封装定制"),
    ],
    "memory_storage": [
        ("产品采购", "Product Procurement", "存储芯片/模组批量采购"),
        ("模组定制", "Module Customization", "定制存储模组方案"),
        ("样品申请", "Sample Request", "研发样品支持"),
        ("技术支持", "Technical Support", "选型与方案技术支持"),
    ],
    "semiconductor_chips": [
        ("产品采购", "Product Procurement", "CPU/GPU/SoC 批量采购"),
        ("技术支持", "Technical Support", "参考设计与选型支持"),
        ("样品申请", "Sample Request", "研发样品申请"),
        ("参考设计", "Reference Design", "配套参考设计方案"),
    ],
    "connectors_cables": [
        ("产品采购", "Product Procurement", "连接器/线束批量采购"),
        ("定制连接器", "Custom Connector", "定制规格连接器"),
        ("样品申请", "Sample Request", "研发样品支持"),
        ("选型支持", "Selection Support", "选型与替代支持"),
    ],
    "pcb_pcba": [
        ("PCB打样", "PCB Prototyping", "小批量 PCB 打样"),
        ("批量制板", "Volume PCB", "规模化 PCB 制造"),
        ("PCBA代工", "PCBA Assembly", "SMT 贴片与 PCBA 加工"),
        ("测试服务", "Testing Service", "板级测试服务"),
    ],
    "sourcing_distribution": [
        ("现货销售", "Spot Sales", "现货库存销售"),
        ("授权分销", "Authorized Distribution", "原厂授权分销"),
        ("BOM配单", "BOM Consolidation", "一站式 BOM 配单"),
        ("询价报价", "RFQ & Quotation", "RFQ 询价与报价"),
        ("缺料寻源", "Shortage Sourcing", "缺料寻源服务"),
    ],
    "odm_ems_manufacturing": [
        ("ODM设计", "ODM Design", "整机 ODM 方案设计"),
        ("EMS代工", "EMS Manufacturing", "电子制造代工"),
        ("整机组装", "Final Assembly", "整机组装与测试"),
        ("测试包装", "Test & Packaging", "测试与包装入库"),
    ],
}


def _template_business(company: CompanyCache, boundary: BusinessBoundary, lang: str) -> dict:
    cname = _name(company, lang)
    is_en = lang == "en"
    seg = _segment_for(boundary)
    items = _BUSINESS_TEMPLATES.get(seg, _BUSINESS_TEMPLATES["sourcing_distribution"])
    business_types: list[dict] = []
    for zh_name, en_name, _desc in items:
        bt_name = en_name if is_en else zh_name
        if is_en:
            entry = {
                "business_type": bt_name,
                "definition": f"{bt_name} is a core service of {cname} ({boundary.industry_en}), covering {_desc}.",
                "applicable_customers": ", ".join(boundary.probable_customer_types) + " (translated: " + ", ".join(["distributor", "EMS", "brand buyer", "design house"]) + ")",
                "prerequisite_info": ["Product category and part number", "Monthly/annual quantity", "Application scenario", "Technical requirements", "Budget and target lead time", "Delivery region"],
                "process_steps": [
                    "Step 1: Customer submits requirement (part number, qty, scenario)",
                    "Step 2: Sales/engineer confirms spec feasibility within business boundary",
                    "Step 3: Provide quotation or solution (price, lead time, MOQ)",
                    "Step 4: Customer confirms; PO placed",
                    "Step 5: Production/procurement execution",
                    "Step 6: QC, delivery, after-sales",
                ],
                "internal_logic": "Judge whether the requirement falls within allowed_business_scope; if not, decline and guide to the right channel. For non-standard specs, route to technical confirmation. Hand off to human when contract/value exceeds threshold.",
                "communication": "First contact -> requirement confirmation -> product/solution recommendation -> quotation -> delivery -> after-sales. Keep within the company's product categories; do not promise out-of-scope products.",
                "exceptions": ["No matching product in catalog", "Vague requirement", "Lead time too short", "Large volume with custom spec", "Spec conflict with boundary"],
                "faq": [
                    f"Q: How to start {bt_name}? A: Submit part number/qty/scenario; sales confirms within 1 business day.",
                    f"Q: Can {cname} customize? A: Within allowed categories and qualified volume, yes.",
                    "Q: What if no matching product? A: Sales recommends the closest alternative or cross-reference.",
                ],
            }
        else:
            entry = {
                "business_type": bt_name,
                "definition": f"{bt_name}是{cname}（{boundary.industry}）的核心业务之一，涵盖{_desc}。",
                "applicable_customers": "、".join(boundary.probable_customer_types),
                "prerequisite_info": ["产品类型与料号", "月/年需求量", "使用场景", "技术要求", "预算与目标交期", "交付地区"],
                "process_steps": [
                    "第1步：客户提交需求（料号、数量、场景）",
                    "第2步：销售/工程师在业务边界内确认规格可行性",
                    "第3步：提供报价或方案（价格、交期、MOQ）",
                    "第4步：客户确认，下达订单",
                    "第5步：生产/采购执行",
                    "第6步：质检、交付、售后",
                ],
                "internal_logic": "判断需求是否落在 allowed_business_scope 内；不在则婉拒并引导至正确渠道。非标规格转技术确认。合同金额/价值超阈值转人工跟进。",
                "communication": "首次沟通→需求确认→产品/方案推荐→报价→交付→售后。严守公司产品类别，不承诺范围外产品。",
                "exceptions": ["无匹配型号", "需求不明确", "交期过短", "大批量定制", "规格与业务边界冲突"],
                "faq": [
                    f"问：如何发起{bt_name}？答：提交料号/数量/场景，销售1个工作日内确认。",
                    f"问：{cname}能定制吗？答：在允许品类且达到合格量产量的前提下可以。",
                    "问：没有匹配型号怎么办？答：销售推荐最接近的替代或交叉料。",
                ],
            }
        business_types.append(entry)
    title = f"{cname} 业务知识手册" if not is_en else f"{cname} Business Knowledge Manual"
    return {"manual_title": title, "business_types": business_types, "source": "template"}


# ============================================================
# 对外入口
# ============================================================
async def generate_product_knowledge(company: CompanyCache, boundary: BusinessBoundary, lang: str) -> dict:
    """生成产品知识结构 — 仅使用真实 LLM。"""
    data = await _llm_generate(company, boundary, "product", lang)
    if data and data.get("products"):
        data["source"] = "llm"
        return data
    raise RuntimeError(f"LLM product knowledge generation failed for company {company.id} ({company.name})")


async def generate_business_knowledge(company: CompanyCache, boundary: BusinessBoundary, lang: str) -> dict:
    """生成业务知识结构 — 仅使用真实 LLM。"""
    data = await _llm_generate(company, boundary, "business", lang)
    if data and data.get("business_types"):
        data["source"] = "llm"
        return data
    raise RuntimeError(f"LLM business knowledge generation failed for company {company.id} ({company.name})")
