import { computed, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { getEnterpriseCompanies, getDashboard } from '@/api/enterprise'
import type { EnterpriseContext, ChainCompany } from '@/types/enterprise'

// ── Fallback 数据（后端无数据时保底展示）────────────────────────
const FALLBACK_DASHBOARDS: Record<number, Partial<EnterpriseContext>> = {
  9001: {
    company: { id: 9001, name: '华芯微电子', segment: '半导体芯片', role: '芯片设计商', location: '上海', note: '专注于 CPU/GPU/SoC 等核心计算与控制芯片的设计与销售。' },
    metrics: { pendingOrders: 18, forecastDemand: 126000, urgentOrders: 3, shortageParts: 4, availableProducts: 5, atRiskProducts: 2 },
    demands: [
      { id: 'SO-9001-01', type: '紧急', customer: '创捷主板', product: 'MF-CX900 主控芯片', quantity: 12000, due: '7 天内', status: '待封测放行', risk: '高' },
      { id: 'FC-9001-01', type: '预测', customer: '整机客户池', product: 'MF-PM32 电源管理 IC', quantity: 48000, due: '8 月', status: '需确认晶圆投片', risk: '中' },
    ],
    products: [
      { id: 1, name: '主控芯片', model: 'MF-CX900', capacity: '月产 80K', monthlyPlan: 42000, status: '受封测载板影响', risk: '高',
        bom: [
          { code: 'WAF-12', name: '12 英寸晶圆', inventory: 26000, demand: 42000, gap: 16000, risk: '高', alternatives: 1, suppliers: 2 },
          { code: 'PKG-BGA', name: 'BGA196 封装载板', inventory: 18000, demand: 36000, gap: 18000, risk: '高', alternatives: 2, suppliers: 3 },
        ] },
      { id: 2, name: '电源管理 IC', model: 'MF-PM32', capacity: '月产 120K', monthlyPlan: 68000, status: '正常', risk: '低',
        bom: [
          { code: 'WAF-8', name: '8 英寸晶圆', inventory: 70000, demand: 68000, gap: 0, risk: '低', alternatives: 2, suppliers: 4 },
          { code: 'PKG-QFN', name: 'QFN48 封装材料', inventory: 55000, demand: 68000, gap: 13000, risk: '中', alternatives: 3, suppliers: 5 },
        ] },
    ],
    shortages: [
      { part: 'BGA196 封装载板', code: 'PKG-BGA', gap: 18000, affectedOrders: ['SO-9001-01'], affectedProducts: ['MF-CX900'], risk: '高', substitutes: ['PKG-BGA-B'], suppliers: ['南山封装', '晶联载板'], action: '立即向载板厂发 RFQ' },
      { part: '12 英寸晶圆', code: 'WAF-12', gap: 16000, affectedOrders: ['SO-9001-01'], affectedProducts: ['MF-CX900'], risk: '高', substitutes: ['WAF-12-P'], suppliers: ['华东晶圆', '新湾晶圆'], action: '锁定 8 月投片窗口' },
    ],
    actions: [
      { id: 'A1', category: '采购', title: 'BGA196 载板加急询价', detail: '缺口 18K，影响紧急订单。', priority: '高', target: '南山封装' },
      { id: 'A2', category: '生产', title: '调整 CX900 封测排程', detail: '优先释放紧急订单。', priority: '高' },
    ],
    relations: [
      { id: 9002, name: '创捷主板', direction: '下游', segment: 'PCB与PCBA', scope: ['型号', '规格', '价格', '交期'], products: '主控芯片、电源管理 IC' },
    ],
    internalQuestions: ['本周 CX900 可承诺交付多少片？', 'PM32 的安全库存线是多少？'],
  },
  9002: {
    company: { id: 9002, name: '创捷主板模组', segment: 'PCB与PCBA', role: '主板/模组制造商', location: '深圳', note: 'PCB 制板、SMT 贴片、PCBA 加工与主板/模组设计制造。' },
    metrics: { pendingOrders: 24, forecastDemand: 18500, urgentOrders: 5, shortageParts: 6, availableProducts: 7, atRiskProducts: 3 },
    products: [
      { id: 3, name: '工控主板', model: 'MF-B760', capacity: '日产 900 片', monthlyPlan: 8800, status: '受主控芯片影响', risk: '高',
        bom: [
          { code: 'IC-CX900', name: '主控芯片 CX900', inventory: 960, demand: 4200, gap: 3240, risk: '高', alternatives: 2, suppliers: 3 },
          { code: 'CAP-MLCC', name: 'MLCC 0.1uF', inventory: 320000, demand: 280000, gap: 0, risk: '低', alternatives: 8, suppliers: 12 },
        ] },
    ],
    shortages: [
      { part: '主控芯片 CX900', code: 'IC-CX900', gap: 3240, affectedOrders: ['SO-9002-01'], affectedProducts: ['MF-B760'], risk: '高', substitutes: ['CX900A'], suppliers: ['华芯微电子'], action: '优先联系华芯确认交付批次。' },
    ],
    actions: [
      { id: 'B1', category: '采购', title: 'CX900 芯片缺口', detail: '缺口 3,240 片。', priority: '高', target: '华芯微电子' },
      { id: 'B2', category: '生产', title: 'B760 分批交付', detail: '先产 960 片，剩余等待到料。', priority: '高' },
    ],
    relations: [
      { id: 9001, name: '华芯微电子', direction: '上游', segment: '半导体芯片', scope: ['型号', '规格', '价格', '交期'], products: '主控芯片、电源管理 IC' },
      { id: 9003, name: '鼎云整机', direction: '下游', segment: 'ODM/EMS', scope: ['交付计划', '合作流程'], products: '主板模组' },
    ],
    internalQuestions: ['B760 当前齐套数量是多少？', '本周 SMT 产能能否插单？'],
  },
  9003: {
    company: { id: 9003, name: '鼎云整机制造', segment: 'ODM/EMS', role: 'ODM/EMS', location: '苏州', note: 'ODM 方案设计与 EMS 电子制造，向品牌方交付整机。' },
    metrics: { pendingOrders: 31, forecastDemand: 9200, urgentOrders: 4, shortageParts: 5, availableProducts: 6, atRiskProducts: 2 },
    shortages: [
      { part: 'MF-B760 工控主板', code: 'MB-B760', gap: 1540, affectedOrders: ['SO-9003-01'], affectedProducts: ['EdgeBox-700'], risk: '高', substitutes: ['MB-B760-R2'], suppliers: ['创捷主板'], action: '向创捷确认分批交期。' },
    ],
    actions: [
      { id: 'C1', category: '协同', title: '确认 B760 交付承诺', detail: '缺口 1,540 片。', priority: '高', target: '创捷主板' },
    ],
    relations: [
      { id: 9002, name: '创捷主板', direction: '上游', segment: 'PCB与PCBA', scope: ['型号', '规格', '交期'], products: '主板、模组' },
      { id: 9005, name: '星河数码', direction: '下游', segment: '分销', scope: ['交付计划'], products: '整机' },
    ],
    internalQuestions: ['EdgeBox-700 今天能装多少台？', '本月整机利润最高的产品？'],
  },
}

/** 用后端数据填充上下文，空字段用 fallback 补齐。 */
function fillContext(companyId: number, data: any): EnterpriseContext {
  const fb = FALLBACK_DASHBOARDS[companyId] || {}
  return _mapDashboard(companyId, data, fb)
}

function _mapDashboard(companyId: number, data: any, fb: Record<string, any>): EnterpriseContext {
  const choose = <T>(arr: T[], fallback: T[] = []) =>
    arr && arr.length > 0 ? arr : fallback

  const company = data.company || {}
  const productsSum = data.products_summary || {}
  const orders = data.orders_summary || {}
  const forecast = data.forecast_summary || {}
  const shortageObj = data.shortages || {}
  const shortageItems = shortageObj.items || []
  const actionsObj = data.recommended_actions || {}

  const allRelations = [
    ...(data.upstream_summary?.items || []),
    ...(data.downstream_summary?.items || []),
    ...(data.support_summary?.items || []),
  ]

  return {
    company: {
      id: companyId,
      name: company.name || fb.company?.name || '',
      segment: company.segment_name || company.segment_code || fb.company?.segment || '',
      role: company.role || fb.company?.role || '',
      location: company.region || fb.company?.location || '',
      note: company.description || fb.company?.note || '',
    },
    metrics: fb.metrics || {
      pendingOrders: orders.active_count || 0,
      forecastDemand: forecast.total_forecast_quantity || 0,
      urgentOrders: orders.by_priority?.urgent || orders.by_priority?.Urgent || 0,
      shortageParts: shortageObj.shortage_count || shortageItems.filter((s: any) => s.shortage_type === 'shortage').length,
      availableProducts: productsSum.active_count || productsSum.total || 0,
      atRiskProducts: 0,
    },
    demands: fb.demands || [],
    products: choose(productsSum.items, fb.products || []).map((p: any) => ({
      id: p.id || p.product_id,
      name: p.product_name || p.name || '',
      model: p.product_model || p.model || '',
      capacity: p.monthly_capacity ? `月产 ${p.monthly_capacity}` : (p.capacity || ''),
      monthlyPlan: p.monthly_plan || p.monthly_capacity || 0,
      status: p.status || '',
      risk: p.risk || '低',
      bom: (p.bom || []).map((b: any) => ({
        code: b.part_number || b.code || '',
        name: b.part_name || b.name || '',
        inventory: b.inventory || 0,
        demand: b.demand || 0,
        gap: b.gap || 0,
        risk: b.risk || '低',
        alternatives: b.alternatives || 0,
        suppliers: b.suppliers || 0,
      })),
    })),
    shortages: choose(shortageItems, fb.shortages || []).map((s: any) => ({
      part: s.part_name || s.part || '',
      code: s.part_number || s.code || '',
      gap: s.shortage_qty || s.gap || 0,
      affectedOrders: s.affected_order_numbers || s.affected_orders || [],
      affectedProducts: s.affected_product_ids || s.affected_products || [],
      risk: s.severity || s.risk || '低',
      substitutes: s.substitutes || [],
      suppliers: s.suppliers || [],
      action: s.action || s.recommendation || '',
    })),
    actions: choose(actionsObj.items, fb.actions || []).map((a: any) => ({
      id: a.id || '',
      category: a.category || '协同',
      title: a.title || '',
      detail: a.detail || '',
      priority: a.priority || '低',
      target: a.target,
    })),
    relations: choose(allRelations, fb.relations || []).map((r: any) => ({
      id: r.company_id || r.id,
      name: r.company_name || r.name || '',
      direction: r.direction || '上游',
      segment: r.segment_name || r.segment || '',
      scope: r.product_scope || r.scope || [],
      products: r.products || '',
    })),
    internalQuestions: fb.internalQuestions || [],
  }
}

const storageKey = 'matchforge-current-enterprise-id'

const companies = ref<ChainCompany[]>([])
const contexts = ref<Map<number, EnterpriseContext>>(new Map())
const currentEnterpriseId = ref(readInitialId())
const loading = ref(false)
let _loaded = false

function readInitialId(): number {
  const saved = Number(window.localStorage.getItem(storageKey))
  return Number.isFinite(saved) && saved > 0 ? saved : 0
}

function emptyContext(): EnterpriseContext {
  return {
    company: { id: 0, name: '', segment: '', role: '', location: '', note: '' },
    metrics: { pendingOrders: 0, forecastDemand: 0, urgentOrders: 0, shortageParts: 0, availableProducts: 0, atRiskProducts: 0 },
    demands: [], products: [], shortages: [], actions: [], relations: [], internalQuestions: [],
  }
}

const current = computed<EnterpriseContext>(() => {
  return contexts.value.get(currentEnterpriseId.value) || emptyContext()
})

/** 从后端加载企业列表（需要已登录）。 */
async function ensureLoaded() {
  const auth = useAuthStore()
  if (_loaded) return
  if (!auth.isAuthenticated) return
  _loaded = true
  loading.value = true

  try {
    const res = await getEnterpriseCompanies()
    const items = res.data?.items || []
    companies.value = items.map((c: any) => ({
      id: c.company_id || c.id,
      name: c.company?.name || c.name || '',
      segment: c.segment_name || c.segment_code || '',
      role: c.role || '',
      location: c.company?.region || '',
      note: c.company?.description || '',
    }))

    const validIds = new Set(companies.value.map((c) => c.id))
    if (companies.value.length > 0 && (!currentEnterpriseId.value || !validIds.has(currentEnterpriseId.value))) {
      setCurrentEnterprise(companies.value[0].id)
    } else if (companies.value.length > 0 && validIds.has(currentEnterpriseId.value) && !contexts.value.has(currentEnterpriseId.value)) {
      const ctx = await loadContext(currentEnterpriseId.value)
      if (ctx) contexts.value.set(currentEnterpriseId.value, ctx)
    }
  } catch {
    // 加载失败时保持空状态
  } finally {
    loading.value = false
  }
}

async function loadContext(id: number): Promise<EnterpriseContext | null> {
  try {
    const res = await getDashboard(id)
    return fillContext(id, res.data)
  } catch {
    return null
  }
}

function setCurrentEnterprise(id: number) {
  currentEnterpriseId.value = id
  window.localStorage.setItem(storageKey, String(id))
  if (!contexts.value.has(id)) {
    loadContext(id).then((ctx) => {
      if (ctx) contexts.value.set(id, ctx)
    })
  }
}

export function useEnterpriseContext() {
  ensureLoaded()
  return {
    companies,
    current,
    currentEnterpriseId,
    setCurrentEnterprise,
    loading,
    ensureLoaded,
  }
}