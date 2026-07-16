import api from './index'

export interface DemoEvent {
  id?: number | string
  event_id?: number | string
  scenario_id?: string
  company_id?: number
  company_name?: string
  affected_company_id?: number
  affected_company_name?: string
  action_type?: string
  event_type?: string
  summary?: string
  result_summary?: string
  message?: string
  created_at?: string
  timestamp?: string
}

export interface DemoState {
  scenario_id?: string
  company_id?: number
  events?: DemoEvent[]
  recent_events?: DemoEvent[]
  [key: string]: unknown
}

export interface DemoActionResult {
  ok?: boolean
  message?: string
  summary?: string
  state?: DemoState
  events?: DemoEvent[]
  [key: string]: unknown
}

export function getDemoState(companyId?: number) {
  return api.get<DemoState>('/demo/state', { params: companyId ? { company_id: companyId } : undefined })
}

export function getDemoEvents(companyId?: number) {
  return api.get<{ items?: DemoEvent[]; events?: DemoEvent[] } | DemoEvent[]>('/demo/events', {
    params: companyId ? { company_id: companyId } : undefined,
  })
}

export function resetDemoScenario(companyId?: number) {
  return api.post<DemoActionResult>('/demo/scenarios/reset', companyId ? { company_id: companyId } : undefined)
}

export function generateDemoOrders(companyId: number) {
  return api.post<DemoActionResult>('/demo/actions/generate-orders', { company_id: companyId })
}

export function consumeDemoInventory(companyId: number) {
  return api.post<DemoActionResult>('/demo/actions/consume-inventory', { company_id: companyId })
}

export function recalculateDemoShortages(companyId: number) {
  return api.post<DemoActionResult>('/demo/actions/recalculate-shortages', { company_id: companyId })
}

export function generateDemoRfq(companyId: number) {
  return api.post<DemoActionResult>('/demo/actions/generate-rfq', { company_id: companyId })
}

export function simulateDemoQuotes(companyId: number) {
  return api.post<DemoActionResult>('/demo/actions/simulate-quotes', { company_id: companyId })
}

export function executeDemoReplenishment(companyId: number) {
  return api.post<DemoActionResult>('/demo/actions/execute-replenishment', { company_id: companyId })
}

export function selectDemoAlternative(companyId: number) {
  return api.post<DemoActionResult>('/demo/actions/select-alternative', { company_id: companyId })
}
