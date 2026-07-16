/**
 * 驾驶舱企业类型定义（从 mock 提取，供视图使用）。
 */

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

export function riskRank(risk: RiskLevel): number {
  return risk === '高' ? 3 : risk === '中' ? 2 : 1
}