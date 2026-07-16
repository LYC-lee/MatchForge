export interface DemoCompany {
  company_id: number
  name: string
  short_name: string
  segment_name: string
  role: string
  chain_position: '上游' | '中游' | '下游' | '支撑'
}

export const DEMO_COMPANIES: DemoCompany[] = [
  {
    company_id: 9001,
    name: '华芯微电子',
    short_name: '华芯',
    segment_name: '芯片/元器件',
    role: '芯片与关键元器件供应商',
    chain_position: '上游',
  },
  {
    company_id: 9002,
    name: '创捷主板模组科技',
    short_name: '创捷主板',
    segment_name: '主板/模组',
    role: '主板与模组制造商',
    chain_position: '上游',
  },
  {
    company_id: 9003,
    name: '鼎云整机制造有限公司',
    short_name: '鼎云整机',
    segment_name: '整机制造',
    role: 'ODM/EMS 整机制造商',
    chain_position: '中游',
  },
  {
    company_id: 9004,
    name: '远达供应链服务',
    short_name: '远达物流',
    segment_name: '物流/服务',
    role: '运输与履约支撑服务商',
    chain_position: '支撑',
  },
  {
    company_id: 9005,
    name: '星河数码渠道',
    short_name: '星河渠道',
    segment_name: '渠道/客户',
    role: '整机销售与渠道客户',
    chain_position: '下游',
  },
  {
    company_id: 9006,
    name: '毅诚被动元件',
    short_name: '毅诚',
    segment_name: '连接器/被动件',
    role: '元器件制造与备货供应商',
    chain_position: '上游',
  },
]

export const DEFAULT_DEMO_COMPANY_ID = 9003

export function findDemoCompany(companyId?: number | null) {
  return DEMO_COMPANIES.find((company) => company.company_id === companyId)
}
