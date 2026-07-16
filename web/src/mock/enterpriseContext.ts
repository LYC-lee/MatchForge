export type RiskLevel = '高' | '中' | '低'
export type RelationDirection = '上游' | '下游'

export interface ChainCompany {
  id: number
  name: string
  segment: string
  role: string
  location: string
  note: string
}

export interface DemandItem {
  id: string
  type: '订单' | '预测' | '紧急'
  customer: string
  product: string
  quantity: number
  due: string
  status: string
  risk: RiskLevel
}

export interface BomPart {
  code: string
  name: string
  inventory: number
  demand: number
  gap: number
  risk: RiskLevel
  alternatives: number
  suppliers: number
}

export interface ProductItem {
  id: string
  name: string
  model: string
  capacity: string
  monthlyPlan: number
  status: string
  risk: RiskLevel
  bom: BomPart[]
}

export interface ShortageItem {
  part: string
  code: string
  gap: number
  affectedOrders: string[]
  affectedProducts: string[]
  risk: RiskLevel
  substitutes: string[]
  suppliers: string[]
  action: string
}

export interface RecommendedAction {
  id: string
  category: '采购' | '生产' | '销售' | '协同'
  title: string
  detail: string
  priority: RiskLevel
  target?: string
}

export interface RelationCompany {
  id: number
  name: string
  direction: RelationDirection
  segment: string
  scope: string[]
  products: string
}

export interface EnterpriseContext {
  company: ChainCompany
  metrics: {
    pendingOrders: number
    forecastDemand: number
    urgentOrders: number
    shortageParts: number
    availableProducts: number
    atRiskProducts: number
  }
  demands: DemandItem[]
  products: ProductItem[]
  shortages: ShortageItem[]
  actions: RecommendedAction[]
  relations: RelationCompany[]
  internalQuestions: string[]
}

export const enterpriseContexts: EnterpriseContext[] = [
  {
    company: {
      id: 101,
      name: '华芯微电子',
      segment: '芯片/元器件',
      role: '主控芯片与电源管理 IC 供应商',
      location: '深圳',
      note: '面向主板厂和模组厂供货，重点关注晶圆排产、封测产能和关键客户交付。',
    },
    metrics: { pendingOrders: 18, forecastDemand: 126000, urgentOrders: 3, shortageParts: 4, availableProducts: 5, atRiskProducts: 2 },
    demands: [
      { id: 'SO-CHIP-2407', type: '紧急', customer: '东海主板', product: 'MF-CX900 主控芯片', quantity: 12000, due: '7 天内', status: '待封测放行', risk: '高' },
      { id: 'FC-CHIP-2408', type: '预测', customer: '整机客户池', product: 'MF-PM32 电源管理 IC', quantity: 48000, due: '8 月', status: '需确认晶圆投片', risk: '中' },
      { id: 'SO-CHIP-2398', type: '订单', customer: '星河模组', product: 'MF-LAN210 网口芯片', quantity: 8600, due: '14 天内', status: '可排产', risk: '低' },
    ],
    products: [
      {
        id: 'P-CX900',
        name: '主控芯片',
        model: 'MF-CX900',
        capacity: '月产 80K',
        monthlyPlan: 42000,
        status: '受封测载板影响',
        risk: '高',
        bom: [
          { code: 'WAF-12-A7', name: '12 英寸晶圆', inventory: 26000, demand: 42000, gap: 16000, risk: '高', alternatives: 1, suppliers: 2 },
          { code: 'PKG-BGA-196', name: 'BGA196 封装载板', inventory: 18000, demand: 36000, gap: 18000, risk: '高', alternatives: 2, suppliers: 3 },
          { code: 'TEST-SOCKET-CX', name: '测试座', inventory: 46, demand: 60, gap: 14, risk: '中', alternatives: 1, suppliers: 2 },
        ],
      },
      {
        id: 'P-PM32',
        name: '电源管理 IC',
        model: 'MF-PM32',
        capacity: '月产 120K',
        monthlyPlan: 68000,
        status: '正常',
        risk: '低',
        bom: [
          { code: 'WAF-8-PM', name: '8 英寸晶圆', inventory: 70000, demand: 68000, gap: 0, risk: '低', alternatives: 2, suppliers: 4 },
          { code: 'PKG-QFN-48', name: 'QFN48 封装材料', inventory: 55000, demand: 68000, gap: 13000, risk: '中', alternatives: 3, suppliers: 5 },
        ],
      },
    ],
    shortages: [
      { part: 'BGA196 封装载板', code: 'PKG-BGA-196', gap: 18000, affectedOrders: ['SO-CHIP-2407'], affectedProducts: ['MF-CX900'], risk: '高', substitutes: ['PKG-BGA-196B', 'PKG-BGA-196M'], suppliers: ['南山封装材料', '晶联载板'], action: '立即向 2 家载板厂发 RFQ，并确认加急交期。' },
      { part: '12 英寸晶圆', code: 'WAF-12-A7', gap: 16000, affectedOrders: ['SO-CHIP-2407', 'FC-CHIP-2408'], affectedProducts: ['MF-CX900'], risk: '高', substitutes: ['WAF-12-A7P'], suppliers: ['华东晶圆厂', '新湾晶圆'], action: '锁定 8 月投片窗口，评估是否调整 CX900 交付承诺。' },
      { part: 'QFN48 封装材料', code: 'PKG-QFN-48', gap: 13000, affectedOrders: ['FC-CHIP-2408'], affectedProducts: ['MF-PM32'], risk: '中', substitutes: ['PKG-QFN-48G', 'PKG-QFN-48L'], suppliers: ['鹏城封测', '海芯材料'], action: '发起替代封装验证，降低 PM32 预测风险。' },
    ],
    actions: [
      { id: 'A1', category: '采购', title: 'BGA196 载板加急询价', detail: '缺口 18K，影响东海主板紧急订单。', priority: '高', target: '南山封装材料' },
      { id: 'A2', category: '生产', title: '调整 CX900 封测排程', detail: '优先释放 12K 紧急订单，延后低风险预测单。', priority: '高' },
      { id: 'A3', category: '协同', title: '向下游同步可交付批次', detail: '对东海主板提供 7 天/14 天两档交期承诺。', priority: '中', target: '东海主板' },
    ],
    relations: [
      { id: 201, name: '华东晶圆厂', direction: '上游', segment: '晶圆制造', products: '8/12 英寸晶圆', scope: ['投片窗口', '工艺节点', '价格', '交期', '付款方式'] },
      { id: 202, name: '南山封装材料', direction: '上游', segment: '封装材料', products: 'BGA/QFN 载板', scope: ['规格', 'MOQ', '替代料', '加急交期', '售后'] },
      { id: 301, name: '东海主板', direction: '下游', segment: '主板制造', products: '工控主板', scope: ['型号适配', '预测需求', '合同条款', '售后流程'] },
      { id: 302, name: '星河模组', direction: '下游', segment: '模组企业', products: '通信模组', scope: ['供货区域', '价格阶梯', '交期'] },
    ],
    internalQuestions: ['本周 CX900 可承诺交付多少片？', '哪些订单会被封装载板影响？', 'PM32 的安全库存线是多少？', '封测产能还有多少余量？'],
  },
  {
    company: {
      id: 301,
      name: '东海主板',
      segment: '主板/模组',
      role: '工业电脑主板制造商',
      location: '苏州',
      note: '承接整机厂订单，核心决策是芯片缺件、BOM 替代和产线排程。',
    },
    metrics: { pendingOrders: 24, forecastDemand: 18500, urgentOrders: 5, shortageParts: 6, availableProducts: 7, atRiskProducts: 3 },
    demands: [
      { id: 'SO-MB-8821', type: '紧急', customer: '联盛整机', product: 'MF-B760 工控主板', quantity: 1800, due: '5 天内', status: '缺主控芯片', risk: '高' },
      { id: 'SO-MB-8809', type: '订单', customer: '北辰终端', product: 'MF-H610 商用主板', quantity: 2600, due: '12 天内', status: '待排产', risk: '中' },
      { id: 'FC-MB-2408', type: '预测', customer: '渠道预测', product: 'MF-N100 迷你主板', quantity: 6200, due: '8 月', status: '需确认内存颗粒', risk: '中' },
    ],
    products: [
      {
        id: 'P-B760',
        name: '工控主板',
        model: 'MF-B760',
        capacity: '日产 900 片',
        monthlyPlan: 8800,
        status: '受主控芯片影响',
        risk: '高',
        bom: [
          { code: 'IC-CX900', name: '主控芯片 CX900', inventory: 960, demand: 4200, gap: 3240, risk: '高', alternatives: 2, suppliers: 3 },
          { code: 'CAP-MLCC-104', name: 'MLCC 0.1uF', inventory: 320000, demand: 280000, gap: 0, risk: '低', alternatives: 8, suppliers: 12 },
          { code: 'CONN-PCIE16', name: 'PCIe 插槽', inventory: 2200, demand: 4200, gap: 2000, risk: '中', alternatives: 3, suppliers: 4 },
        ],
      },
      {
        id: 'P-N100',
        name: '迷你主板',
        model: 'MF-N100',
        capacity: '日产 1200 片',
        monthlyPlan: 9600,
        status: '受内存颗粒影响',
        risk: '中',
        bom: [
          { code: 'DRAM-DDR4-8G', name: 'DDR4 8G 颗粒', inventory: 5800, demand: 9600, gap: 3800, risk: '中', alternatives: 4, suppliers: 5 },
          { code: 'PMIC-PM32', name: '电源管理 IC PM32', inventory: 11200, demand: 9600, gap: 0, risk: '低', alternatives: 2, suppliers: 3 },
        ],
      },
    ],
    shortages: [
      { part: '主控芯片 CX900', code: 'IC-CX900', gap: 3240, affectedOrders: ['SO-MB-8821'], affectedProducts: ['MF-B760'], risk: '高', substitutes: ['IC-CX900A', 'IC-CX870'], suppliers: ['华芯微电子', '启明芯片'], action: '优先联系华芯微电子确认 7 天内可交付批次。' },
      { part: 'PCIe 插槽', code: 'CONN-PCIE16', gap: 2000, affectedOrders: ['SO-MB-8821', 'SO-MB-8809'], affectedProducts: ['MF-B760', 'MF-H610'], risk: '中', substitutes: ['CONN-PCIE16-L', 'CONN-PCIE16-S'], suppliers: ['安桥连接器', '立通电子'], action: '同步工程确认低背替代件，生成 RFQ。' },
      { part: 'DDR4 8G 颗粒', code: 'DRAM-DDR4-8G', gap: 3800, affectedOrders: ['FC-MB-2408'], affectedProducts: ['MF-N100'], risk: '中', substitutes: ['DRAM-DDR4-8G-B', 'DRAM-DDR4-16G'], suppliers: ['长江存储分销', '星海存储'], action: '锁价 8 月预测需求，避免渠道价格上行。' },
    ],
    actions: [
      { id: 'A1', category: '采购', title: 'CX900 芯片缺口优先处理', detail: '缺口 3,240 片，直接影响联盛整机 1,800 台紧急订单。', priority: '高', target: '华芯微电子' },
      { id: 'A2', category: '生产', title: 'B760 产线拆分两批交付', detail: '先生产库存齐套的 960 片，剩余等待芯片到料。', priority: '高' },
      { id: 'A3', category: '销售', title: '向联盛整机提供分批交付方案', detail: '5 天交付 960 台，12 天补齐剩余数量。', priority: '中', target: '联盛整机' },
    ],
    relations: [
      { id: 101, name: '华芯微电子', direction: '上游', segment: '芯片/元器件', products: '主控芯片、电源管理 IC', scope: ['型号', '规格', '价格', 'MOQ', '交期', '替代品'] },
      { id: 203, name: '安桥连接器', direction: '上游', segment: '连接器', products: 'PCIe/USB/板对板连接器', scope: ['规格', '替代品', '供货区域', '售后'] },
      { id: 401, name: '联盛整机', direction: '下游', segment: '整机制造', products: '工业电脑整机', scope: ['预测需求', '合同条款', '付款方式', '售后'] },
      { id: 402, name: '北辰终端', direction: '下游', segment: '整机制造', products: '商用终端', scope: ['型号适配', '交付计划', '合作流程'] },
    ],
    internalQuestions: ['B760 当前齐套数量是多少？', '哪些订单受 CX900 缺口影响？', 'N100 的 DDR4 替代方案有哪些？', '本周 SMT 产能能否插单？'],
  },
  {
    company: {
      id: 401,
      name: '联盛整机',
      segment: '整机制造',
      role: '工业电脑与边缘计算整机厂',
      location: '东莞',
      note: '面向渠道和项目客户交付整机，重点关注主板到料、整机装配、销售报价与物流交付。',
    },
    metrics: { pendingOrders: 31, forecastDemand: 9200, urgentOrders: 4, shortageParts: 5, availableProducts: 6, atRiskProducts: 2 },
    demands: [
      { id: 'SO-PC-7102', type: '紧急', customer: '华北渠道', product: 'EdgeBox-700 工业电脑', quantity: 780, due: '6 天内', status: '缺 B760 主板', risk: '高' },
      { id: 'SO-PC-7091', type: '订单', customer: '智慧园区项目', product: 'OfficeMini-300 商用主机', quantity: 1200, due: '15 天内', status: '待物流排仓', risk: '中' },
      { id: 'FC-PC-2408', type: '预测', customer: '渠道预测', product: 'EdgeBox-500', quantity: 3600, due: '8 月', status: '需确认电源库存', risk: '中' },
    ],
    products: [
      {
        id: 'P-EB700',
        name: '工业电脑',
        model: 'EdgeBox-700',
        capacity: '日产 420 台',
        monthlyPlan: 5200,
        status: '受主板影响',
        risk: '高',
        bom: [
          { code: 'MB-B760', name: 'MF-B760 工控主板', inventory: 260, demand: 1800, gap: 1540, risk: '高', alternatives: 1, suppliers: 2 },
          { code: 'SSD-512G-I', name: '工业级 SSD 512G', inventory: 2100, demand: 1800, gap: 0, risk: '低', alternatives: 5, suppliers: 6 },
          { code: 'PSU-250W', name: '250W 电源', inventory: 980, demand: 1800, gap: 820, risk: '中', alternatives: 3, suppliers: 4 },
        ],
      },
      {
        id: 'P-OM300',
        name: '商用主机',
        model: 'OfficeMini-300',
        capacity: '日产 650 台',
        monthlyPlan: 6100,
        status: '物流待确认',
        risk: '中',
        bom: [
          { code: 'MB-H610', name: 'MF-H610 商用主板', inventory: 1600, demand: 1200, gap: 0, risk: '低', alternatives: 2, suppliers: 2 },
          { code: 'CASE-MINI-A', name: '迷你机箱 A 款', inventory: 900, demand: 1200, gap: 300, risk: '中', alternatives: 2, suppliers: 3 },
        ],
      },
    ],
    shortages: [
      { part: 'MF-B760 工控主板', code: 'MB-B760', gap: 1540, affectedOrders: ['SO-PC-7102'], affectedProducts: ['EdgeBox-700'], risk: '高', substitutes: ['MF-B760-R2'], suppliers: ['东海主板', '海越板卡'], action: '向东海主板确认分批交付，并评估 R2 版本替代。' },
      { part: '250W 电源', code: 'PSU-250W', gap: 820, affectedOrders: ['FC-PC-2408'], affectedProducts: ['EdgeBox-700', 'EdgeBox-500'], risk: '中', substitutes: ['PSU-300W', 'PSU-250W-G'], suppliers: ['正源电气', '航嘉工业'], action: '生成 8 月预测 RFQ，争取阶梯价。' },
      { part: '迷你机箱 A 款', code: 'CASE-MINI-A', gap: 300, affectedOrders: ['SO-PC-7091'], affectedProducts: ['OfficeMini-300'], risk: '中', substitutes: ['CASE-MINI-B'], suppliers: ['鑫成五金', '东莞精密'], action: '确认 B 款外观差异，销售同步项目客户。' },
    ],
    actions: [
      { id: 'A1', category: '协同', title: '确认 B760 主板交付承诺', detail: '缺口 1,540 片，影响华北渠道 780 台紧急订单。', priority: '高', target: '东海主板' },
      { id: 'A2', category: '销售', title: '渠道订单拆分交付', detail: '先交付库存可装配 260 台，剩余按主板到货滚动排产。', priority: '高', target: '华北渠道' },
      { id: 'A3', category: '采购', title: '250W 电源锁价', detail: '预测需求 3,600 台，建议提前询价避免 8 月涨价。', priority: '中', target: '正源电气' },
    ],
    relations: [
      { id: 301, name: '东海主板', direction: '上游', segment: '主板/模组', products: '工控主板、商用主板', scope: ['型号', '规格', '价格', 'MOQ', '交期', '替代品'] },
      { id: 204, name: '正源电气', direction: '上游', segment: '电源企业', products: '工业电源', scope: ['规格', '价格', '认证', '售后'] },
      { id: 501, name: '捷运通物流', direction: '下游', segment: '物流/服务', products: '仓配一体、干线运输', scope: ['供货区域', '合作流程', '合同条款', '付款方式'] },
      { id: 601, name: '华北渠道', direction: '下游', segment: '渠道客户', products: '工业电脑采购', scope: ['交付计划', '售后', '付款方式'] },
    ],
    internalQuestions: ['EdgeBox-700 今天最多能装多少台？', '哪些销售订单受 B760 主板影响？', '本月整机毛利最高的产品是哪几个？', '渠道订单能否拆分交付？'],
  },
  {
    company: {
      id: 501,
      name: '捷运通物流',
      segment: '物流/服务',
      role: '电脑制造产业链仓配与干线服务商',
      location: '上海',
      note: '为芯片、主板、整机企业提供仓储、干线与项目交付服务，重点关注仓容、路线和交付风险。',
    },
    metrics: { pendingOrders: 42, forecastDemand: 7600, urgentOrders: 6, shortageParts: 3, availableProducts: 4, atRiskProducts: 1 },
    demands: [
      { id: 'SO-LG-3301', type: '紧急', customer: '联盛整机', product: '华北渠道整机配送', quantity: 780, due: '3 天内', status: '缺华北仓位', risk: '高' },
      { id: 'SO-LG-3288', type: '订单', customer: '东海主板', product: '苏州至东莞干线', quantity: 12, due: '本周', status: '可调度', risk: '低' },
      { id: 'FC-LG-2408', type: '预测', customer: '园区企业池', product: '8 月仓配需求', quantity: 7600, due: '8 月', status: '需扩容', risk: '中' },
    ],
    products: [
      {
        id: 'P-WH',
        name: '仓配一体服务',
        model: 'JYT-WH-STD',
        capacity: '日处理 9,000 件',
        monthlyPlan: 7600,
        status: '华北仓紧张',
        risk: '高',
        bom: [
          { code: 'WH-NORTH', name: '华北仓位', inventory: 320, demand: 1100, gap: 780, risk: '高', alternatives: 2, suppliers: 3 },
          { code: 'PACK-ESD', name: '防静电包装', inventory: 9000, demand: 7600, gap: 0, risk: '低', alternatives: 4, suppliers: 5 },
        ],
      },
      {
        id: 'P-LINE',
        name: '干线运输',
        model: 'JYT-LINE-E',
        capacity: '每日 38 车次',
        monthlyPlan: 620,
        status: '正常',
        risk: '低',
        bom: [
          { code: 'TRUCK-9M6', name: '9.6 米厢车', inventory: 42, demand: 38, gap: 0, risk: '低', alternatives: 2, suppliers: 4 },
          { code: 'DRIVER-A', name: 'A 级司机班次', inventory: 31, demand: 38, gap: 7, risk: '中', alternatives: 1, suppliers: 2 },
        ],
      },
    ],
    shortages: [
      { part: '华北仓位', code: 'WH-NORTH', gap: 780, affectedOrders: ['SO-LG-3301'], affectedProducts: ['JYT-WH-STD'], risk: '高', substitutes: ['天津临时仓', '济南协同仓'], suppliers: ['津仓供应链', '鲁通仓配'], action: '启用天津临时仓，并向联盛整机同步分拨方案。' },
      { part: 'A 级司机班次', code: 'DRIVER-A', gap: 7, affectedOrders: ['FC-LG-2408'], affectedProducts: ['JYT-LINE-E'], risk: '中', substitutes: ['B 级司机+双人复核'], suppliers: ['速达车队', '安运车队'], action: '锁定 8 月干线班次，避免项目交付拥堵。' },
    ],
    actions: [
      { id: 'A1', category: '生产', title: '华北仓临时扩容', detail: '缺 780 件仓位，影响联盛整机渠道订单。', priority: '高' },
      { id: 'A2', category: '协同', title: '向联盛整机确认分拨时刻', detail: '提供上海直发和天津中转两套方案。', priority: '高', target: '联盛整机' },
      { id: 'A3', category: '销售', title: '给园区企业池报价 8 月仓配包', detail: '基于预测需求提前锁仓，提高满载率。', priority: '中' },
    ],
    relations: [
      { id: 401, name: '联盛整机', direction: '上游', segment: '整机制造', products: '工业电脑、商用主机', scope: ['交付计划', '合同条款', '售后', '付款方式'] },
      { id: 301, name: '东海主板', direction: '上游', segment: '主板/模组', products: '板卡运输', scope: ['包装规格', '合作流程', '供货区域'] },
      { id: 701, name: '津仓供应链', direction: '下游', segment: '协同仓', products: '华北临时仓', scope: ['仓位', '价格', 'MOQ', '交期'] },
      { id: 702, name: '华北项目客户', direction: '下游', segment: '终端客户', products: '项目交付签收', scope: ['签收流程', '售后', '合同条款'] },
    ],
    internalQuestions: ['华北仓还能接多少件？', '本周哪些运输订单有延误风险？', '联盛整机订单最优路线是什么？', '8 月仓配预测需要多少临时仓位？'],
  },
]

export const defaultEnterpriseId = enterpriseContexts[1].company.id

export function getEnterpriseContext(id: number) {
  return enterpriseContexts.find((item) => item.company.id === id) || enterpriseContexts[0]
}

export function riskRank(risk: RiskLevel) {
  return risk === '高' ? 3 : risk === '中' ? 2 : 1
}
