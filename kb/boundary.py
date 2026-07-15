"""
企业业务边界模型 (Business Boundary Builder)。

在 AI 生成任何知识前, 先为每家公司建立业务边界, 后续所有生成内容受其约束。
至少总结: industry / primary_business / product_categories / allowed_business_scope /
forbidden_expansion_scope / upstream_role / downstream_role / probable_customer_types。

边界数据来自 company_segments + industry_segments (CSV/MySQL), 不凭空联想。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict

from kb.models import CompanyCache

logger = logging.getLogger("kb.boundary")


# 各产业环节的边界定义 (来自 industry_segments 种子数据 + 行业常识, 非编造)
_SEGMENT_BOUNDARIES: dict[str, dict] = {
    "passive_components": {
        "industry_cn": "被动元件", "industry_en": "Passive Components",
        "primary_business_cn": "MLCC电容/贴片电阻/电感/磁珠等基础电子元件的研发与制造",
        "primary_business_en": "R&D and manufacturing of MLCC capacitors, chip resistors, inductors and ferrite beads",
        "product_categories": ["MLCC", "贴片电阻", "电感", "磁珠", "二极管"],
        "allowed_business_scope_cn": ["产品销售", "样品申请", "技术选型支持", "替代料推荐", "批量供货", "定制规格(容值/精度/封装)"],
        "forbidden_expansion_scope_cn": ["整机ODM", "芯片设计", "SaaS软件平台", "化工原材料生产", "PCB制造"],
        "upstream_role": "材料/陶瓷粉体/铜箔采购方",
        "downstream_role": "向分销商/EMS/终端品牌供货",
        "probable_customer_types_cn": ["元器件分销商", "EMS代工厂", "终端品牌采购", "方案公司"],
    },
    "memory_storage": {
        "industry_cn": "内存与存储", "industry_en": "Memory and Storage",
        "primary_business_cn": "DRAM/NAND Flash/SSD/HBM 存储芯片与模组的研发、制造与销售",
        "primary_business_en": "R&D, manufacturing and sales of DRAM/NAND/SSD/HBM memory chips and modules",
        "product_categories": ["DRAM", "NAND Flash", "SSD", "HBM", "存储模组"],
        "allowed_business_scope_cn": ["产品销售", "模组定制", "存储方案", "样品申请", "批量供货", "技术支持"],
        "forbidden_expansion_scope_cn": ["被动元件", "连接器制造", "CPU设计", "化工原材料", "PCB制造"],
        "upstream_role": "晶圆代工/硅片采购方",
        "downstream_role": "向模组厂/品牌/数据中心供货",
        "probable_customer_types_cn": ["存储模组厂", "服务器/数据中心采购", "PC/手机品牌", "分销商"],
    },
    "semiconductor_chips": {
        "industry_cn": "半导体芯片", "industry_en": "Semiconductor Chips",
        "primary_business_cn": "CPU/GPU/SoC/芯片组等核心计算与控制芯片的设计与销售",
        "primary_business_en": "Design and sales of CPU/GPU/SoC/chipset computing and control chips",
        "product_categories": ["CPU", "GPU", "SoC", "芯片组", "PMIC", "MCU"],
        "allowed_business_scope_cn": ["产品销售", "技术支持", "参考设计", "样品申请", "批量供货", "驱动/固件支持"],
        "forbidden_expansion_scope_cn": ["被动元件生产", "化工原材料", "PCB制造", "整机代工组装", "SaaS平台"],
        "upstream_role": "晶圆代工(台积电/三星)客户",
        "downstream_role": "向OEM/ODM/品牌/方案商供货",
        "probable_customer_types_cn": ["PC/服务器品牌", "ODM/EMS", "方案设计公司", "分销商"],
    },
    "connectors_cables": {
        "industry_cn": "连接器与线束", "industry_en": "Connectors and Cables",
        "primary_business_cn": "Type-C/HDMI/板对板连接器/线束/排线的研发与制造",
        "primary_business_en": "R&D and manufacturing of Type-C/HDMI/board-to-board connectors, cable assemblies and FFC",
        "product_categories": ["Type-C连接器", "HDMI连接器", "板对板连接器", "线束", "FFC排线", "内存插槽"],
        "allowed_business_scope_cn": ["产品销售", "定制连接器", "样品申请", "批量供货", "选型支持"],
        "forbidden_expansion_scope_cn": ["芯片设计", "存储芯片", "化工原材料", "SaaS平台", "被动元件"],
        "upstream_role": "塑胶/铜材/电镀采购方",
        "downstream_role": "向EMS/品牌/方案商供货",
        "probable_customer_types_cn": ["EMS代工厂", "终端品牌采购", "方案公司", "分销商"],
    },
    "pcb_pcba": {
        "industry_cn": "PCB与PCBA", "industry_en": "PCB and PCBA",
        "primary_business_cn": "PCB制板、SMT贴片、PCBA加工及板级测试",
        "primary_business_en": "PCB fabrication, SMT assembly, PCBA processing and board-level testing",
        "product_categories": ["PCB硬板", "HDI板", "FPC柔性板", "PCBA代工", "SMT贴片"],
        "allowed_business_scope_cn": ["PCB打样", "批量制板", "PCBA代工", "SMT贴片", "测试服务", "样品申请"],
        "forbidden_expansion_scope_cn": ["芯片设计", "存储芯片生产", "被动元件生产", "化工原材料", "SaaS平台"],
        "upstream_role": "覆铜板/铜箔/油墨采购方",
        "downstream_role": "向品牌/ODM/方案商供货",
        "probable_customer_types_cn": ["终端品牌", "ODM/EMS", "方案设计公司", "硬件创业团队"],
    },
    "sourcing_distribution": {
        "industry_cn": "采购寻源与分销", "industry_en": "Sourcing and Distribution",
        "primary_business_cn": "电子元器件B2B分销、现货贸易、RFQ询价、报价比价与缺料管理",
        "primary_business_en": "Electronic component B2B distribution, spot trading, RFQ, quotation and shortage management",
        "product_categories": ["授权分销", "现货贸易", "代采服务", "BOM配单"],
        "allowed_business_scope_cn": ["现货销售", "授权分销", "代采", "BOM配单", "询价报价", "缺料寻源", "样品申请"],
        "forbidden_expansion_scope_cn": ["芯片自主研发", "被动元件自产", "化工原材料", "整机品牌", "SaaS PaaS"],
        "upstream_role": "原厂/品牌授权分销方",
        "downstream_role": "向终端采购/EMS/方案商供货",
        "probable_customer_types_cn": ["终端品牌采购", "EMS代工厂", "方案公司", "中小硬件厂商", "维修/翻新商"],
    },
    "odm_ems_manufacturing": {
        "industry_cn": "ODM/EMS制造组装", "industry_en": "ODM EMS Manufacturing",
        "primary_business_cn": "ODM方案设计、EMS电子制造、整机组装、软件烧录、老化测试与包装",
        "primary_business_en": "ODM design, EMS manufacturing, final assembly, software flashing, burn-in testing and packaging",
        "product_categories": ["ODM设计方案", "EMS代工", "整机组装", "SMT贴片", "测试包装"],
        "allowed_business_scope_cn": ["ODM设计", "EMS代工", "整机组装", "SMT贴片", "测试服务", "包装入库"],
        "forbidden_expansion_scope_cn": ["芯片自主研发", "被动元件自产", "存储芯片自产", "化工原材料", "SaaS平台"],
        "upstream_role": "元器件/PCB/结构件采购方",
        "downstream_role": "向品牌方交付整机/半成品",
        "probable_customer_types_cn": ["品牌方", "互联网公司", "行业集成商", "海外采购商"],
    },
}

# 兜底边界 (未匹配到 segment_code 时)
_FALLBACK = {
    "industry_cn": "电子元器件", "industry_en": "Electronic Components",
    "primary_business_cn": "电子元器件相关产品与服务",
    "primary_business_en": "Electronic component products and services",
    "product_categories": ["电子元器件"],
    "allowed_business_scope_cn": ["产品销售", "技术支持", "样品申请", "批量供货"],
    "forbidden_expansion_scope_cn": ["超出电子元器件领域的业务"],
    "upstream_role": "上游采购方",
    "downstream_role": "向下游客户供货",
    "probable_customer_types_cn": ["采购方", "分销商", "方案商"],
}


@dataclass
class BusinessBoundary:
    company_id: int
    company_name: str
    industry: str
    industry_en: str
    primary_business: str
    primary_business_en: str
    product_categories: list[str]
    allowed_business_scope: list[str]
    forbidden_expansion_scope: list[str]
    upstream_role: str
    downstream_role: str
    probable_customer_types: list[str]
    chain_position: str
    role: str

    def to_dict(self) -> dict:
        return asdict(self)

    def allows(self, text: str) -> bool:
        """粗略检查文本是否触碰禁止扩展范围 (质量校验用)。"""
        t = text or ""
        for forb in self.forbidden_expansion_scope:
            if forb and forb in t:
                return False
        return True


def build_boundary(company: CompanyCache) -> BusinessBoundary:
    code = company.segment_code
    base = _SEGMENT_BOUNDARIES.get(code, _FALLBACK)
    role = company.role or "制造商"
    bd = BusinessBoundary(
        company_id=company.id,
        company_name=company.name,
        industry=base.get("industry_cn", "电子元器件"),
        industry_en=base.get("industry_en", "Electronic Components"),
        primary_business=base.get("primary_business_cn", "电子元器件相关业务"),
        primary_business_en=base.get("primary_business_en", "Electronic component business"),
        product_categories=list(base.get("product_categories", [])),
        allowed_business_scope=list(base.get("allowed_business_scope_cn", [])),
        forbidden_expansion_scope=list(base.get("forbidden_expansion_scope_cn", [])),
        upstream_role=base.get("upstream_role", ""),
        downstream_role=base.get("downstream_role", ""),
        probable_customer_types=list(base.get("probable_customer_types_cn", [])),
        chain_position=company.chain_position or base.get("chain_position", "upstream"),
        role=role,
    )
    # 持久化到 CompanyCache
    company.business_boundary_json = json.dumps(bd.to_dict(), ensure_ascii=False)
    return bd


def get_boundary(company: CompanyCache) -> BusinessBoundary | None:
    if company.business_boundary_json:
        try:
            d = json.loads(company.business_boundary_json)
            return BusinessBoundary(**d)
        except Exception:
            pass
    return build_boundary(company)
