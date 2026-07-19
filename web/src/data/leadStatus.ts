/**
 * 线索 / RFQ 状态共享字典 (supplier 端 + 审核端统一消费)。
 * declined=已拒绝、closed=已关闭 二者独立，不塌缩为同一态。
 *
 * tagType 对应 ui/Tag.vue 的语义类型（色字 + soft 底 + border 边的徽章公式），
 * 消灭 SupplierLeads / SupplierDashboard 两页翻译与配色不一致。
 */
export type LeadStatus = 'pending' | 'sent' | 'viewed' | 'quoted' | 'declined' | 'closed'

export type LeadTagType = 'neutral' | 'notice' | 'warning' | 'success' | 'danger'

export interface LeadStatusMeta {
  label: string
  tagType: LeadTagType
}

export const LEAD_STATUS: Record<LeadStatus, LeadStatusMeta> = {
  pending: { label: '待发送', tagType: 'neutral' },
  sent: { label: '新线索', tagType: 'notice' },
  viewed: { label: '已查看', tagType: 'warning' },
  quoted: { label: '已报价', tagType: 'success' },
  declined: { label: '已拒绝', tagType: 'danger' },
  closed: { label: '已关闭', tagType: 'neutral' },
}

/** 未收录的状态降级 neutral 并原样显示 */
export function leadStatusMeta(status: string): LeadStatusMeta {
  return LEAD_STATUS[status as LeadStatus] || { label: status, tagType: 'neutral' }
}

export function leadStatusLabel(status: string): string {
  return leadStatusMeta(status).label
}

export function leadTagType(status: string): LeadTagType {
  return leadStatusMeta(status).tagType
}
