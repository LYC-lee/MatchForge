/**
 * 企业驾驶舱 API 客户端。
 */
import api from './index'

/** 企业驾驶舱列表 */
export function getEnterpriseCompanies() {
  return api.get('/enterprise-context/companies')
}

/** 单企业驾驶舱详情 */
export function getEnterpriseContext(companyId: number) {
  return api.get(`/enterprise-context/${companyId}`)
}

/** 企业 BOM 汇总 */
export function getBomSummary(companyId: number) {
  return api.get(`/companies/${companyId}/bom-summary`)
}

/** 企业订单 */
export function getOrders(companyId: number) {
  return api.get(`/companies/${companyId}/orders`)
}

/** 企业预测 */
export function getForecasts(companyId: number) {
  return api.get(`/companies/${companyId}/forecasts`)
}

/** 企业缺件 */
export function getShortages(companyId: number) {
  return api.get(`/companies/${companyId}/shortages`)
}

/** 企业推荐动作 */
export function getRecommendedActions(companyId: number) {
  return api.get(`/companies/${companyId}/recommended-actions`)
}

/** 企业聚合驾驶舱 */
export function getDashboard(companyId: number) {
  return api.get(`/companies/${companyId}/dashboard`)
}

/** 企业上下游关系 */
export function getRelationships(companyId: number) {
  return api.get(`/companies/${companyId}/relationships`)
}

/** 企业可协同问答伙伴 */
export function getChatPartners(companyId: number) {
  return api.get(`/companies/${companyId}/chat-partners`)
}

/** 与指定伙伴协同问答 */
export function partnerChat(
  companyId: number,
  partnerCompanyId: number,
  query: string,
  scope: 'product' | 'business' = 'product',
) {
  return api.post(`/companies/${companyId}/partner-chat`, {
    partner_company_id: partnerCompanyId,
    query,
    scope,
  })
}