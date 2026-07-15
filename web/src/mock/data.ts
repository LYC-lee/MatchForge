import type {
  Alternative,
  LeadGrade,
  ProcureState,
  SpecField,
  Supplier,
} from '@/types/procure'

/** 判断需求信息是否严重不足(无法安全推荐替代料) */
export function isVagueQuery(query: string): boolean {
  const q = query.trim()
  if (q.length < 4) return true
  const hasModel = /[a-z]{2,}\d{2,}/i.test(q)
  const hasSpec = /(容值|电容|电阻|封装|0402|0603|0805|1206|uf|µf|pf|nf|kv|x7r|x5r|c0g)/i.test(q)
  return !hasModel && !hasSpec
}

export function buildParsedSpec(): Record<string, SpecField> {
  return {
    型号: { value: 'TMK212BJ105KG-T', confidence: 0.98 },
    品牌: { value: 'TAIYO YUDEN(太阳诱电)', confidence: 0.92 },
    封装: { value: '0805', confidence: 0.9 },
    容值: { value: '1µF', confidence: 0.95 },
    容差: { value: '±5% (J)', confidence: 0.55 },
    温度系数: { value: 'X5R', confidence: 0.9 },
    额定电压: { value: '25V', confidence: 0.7 },
    月用量: { value: '', confidence: 0, missing: true, editable: true },
    交期要求: { value: '', confidence: 0, missing: true, editable: true },
  }
}

export function buildNormalizedSpec(): Record<string, SpecField> {
  return {
    型号: { value: 'TMK212BJ105KG-T', confidence: 0.98 },
    品牌: { value: 'TAIYO YUDEN(太阳诱电)', confidence: 0.93 },
    封装: { value: '0805 (2012 Metric)', confidence: 0.92 },
    容值: { value: '1µF (1000nF)', confidence: 0.95 },
    容差: { value: '±5% (J)', confidence: 0.68 },
    温度系数: { value: 'X5R (-55~85℃)', confidence: 0.91 },
    额定电压: { value: '25V DC', confidence: 0.78 },
    月用量: { value: '', confidence: 0, missing: true, editable: true },
    交期要求: { value: '', confidence: 0, missing: true, editable: true },
  }
}

export function buildAlternatives(): Alternative[] {
  return [
    {
      part_name: 'CL21B105KAFNNNE',
      brand: 'Samsung Electro-Mechanics',
      package: '0805',
      key_params: { 容值: '1µF', 容差: '±10%', 温度系数: 'X5R', 额定电压: '25V' },
      level: 'L2',
      confidence: 0.92,
      verified: true,
      source: '品牌官方规格书 + 知识图谱交叉比对',
      updated_at: '2025-07-10',
      diffs: [
        { field: '封装', original: '0805', alternative: '0805', status: 'match' },
        { field: '容值', original: '1µF', alternative: '1µF', status: 'match' },
        { field: '容差', original: '±5%', alternative: '±10%', status: 'diff', note: '容差放宽,需确认电路容差裕度' },
        { field: '温度系数', original: 'X5R', alternative: 'X5R', status: 'match' },
        { field: '额定电压', original: '25V', alternative: '25V', status: 'match' },
      ],
    },
    {
      part_name: 'CC0805KKX5R6BB105',
      brand: 'YAGEO(国巨)',
      package: '0805',
      key_params: { 容值: '1µF', 容差: '±10%', 温度系数: 'X5R', 额定电压: '25V' },
      level: 'L2',
      confidence: 0.9,
      verified: true,
      source: '品牌官方规格书',
      updated_at: '2025-07-08',
      diffs: [
        { field: '封装', original: '0805', alternative: '0805', status: 'match' },
        { field: '容值', original: '1µF', alternative: '1µF', status: 'match' },
        { field: '容差', original: '±5%', alternative: '±10%', status: 'diff', note: '容差放宽' },
        { field: '温度系数', original: 'X5R', alternative: 'X5R', status: 'match' },
        { field: '额定电压', original: '25V', alternative: '25V', status: 'match' },
      ],
    },
    {
      part_name: '0805X105K250CT',
      brand: 'Walsin(华新科)',
      package: '0805',
      key_params: { 容值: '1µF', 容差: '±10%', 温度系数: 'X5R', 额定电压: '25V' },
      level: 'L3',
      confidence: 0.78,
      verified: false,
      source: '分销商规格书(未经原厂交叉确认)',
      updated_at: '2025-06-30',
      note: '纹波电流特性未确认,需工程师评估高频去耦场景适用性',
      diffs: [
        { field: '封装', original: '0805', alternative: '0805', status: 'match' },
        { field: '容值', original: '1µF', alternative: '1µF', status: 'match' },
        { field: '容差', original: '±5%', alternative: '±10%', status: 'diff' },
        { field: '温度系数', original: 'X5R', alternative: 'X5R', status: 'match' },
        { field: '额定电压', original: '25V', alternative: '25V', status: 'match' },
      ],
    },
    {
      part_name: 'GRM21BR61E105KA12L',
      brand: 'Murata(村田)',
      package: '0805',
      key_params: { 容值: '1µF', 容差: '±10%', 温度系数: 'X5R', 额定电压: '25V' },
      level: 'L5',
      confidence: 0.42,
      verified: false,
      source: '第三方数据聚合(单一来源,未交叉核验)',
      updated_at: '2025-05-12',
      note: '数据来源单一且置信度低,仅供参考,需工程师向原厂确认',
      diffs: [
        { field: '封装', original: '0805', alternative: '0805', status: 'match' },
        { field: '容值', original: '1µF', alternative: '1µF', status: 'match' },
        { field: '容差', original: '±5%', alternative: '±10%', status: 'diff' },
        { field: '温度系数', original: 'X5R', alternative: 'X5R', status: 'match' },
        { field: '额定电压', original: '25V', alternative: '25V', status: 'match' },
      ],
    },
  ]
}

export function buildSuppliers(): Supplier[] {
  return [
    {
      id: 's1', name: '深圳华强电子世界·恒达元器件', region: '华南·深圳',
      categories: ['MLCC', '贴片电阻', '连接器'],
      brands: ['TAIYO YUDEN', 'YAGEO', 'Samsung EM'],
      qualifications: ['ISO9001', '一般纳税人'],
      moq: 5000, response_speed: '24h 内首次响应',
      data_source: '企业工商信息 + 平台自报', updated_at: '2025-07-12',
      confirmed_stock: false, confirmed_lead: false, confirmed_price: false,
      match_score: 0.86,
    },
    {
      id: 's2', name: '上海赛格集成电路', region: '华东·上海',
      categories: ['被动元件', '分立器件'],
      brands: ['YAGEO', 'Murata', 'Walsin'],
      qualifications: ['ISO9001', 'ISO14001', '原厂授权(部分)'],
      moq: 10000, response_speed: '48h 内首次响应',
      data_source: '原厂授权名录 + 平台自报', updated_at: '2025-07-09',
      confirmed_stock: false, confirmed_lead: false, confirmed_price: false,
      match_score: 0.82,
    },
    {
      id: 's3', name: '苏州芯源微电子', region: '华东·苏州',
      categories: ['MLCC', '钽电容'],
      brands: ['Samsung EM', 'Walsin'],
      qualifications: ['ISO9001'],
      moq: 5000, response_speed: '72h 内首次响应',
      data_source: '平台自报', updated_at: '2025-06-28',
      confirmed_stock: false, confirmed_lead: false, confirmed_price: false,
      match_score: 0.74,
    },
    {
      id: 's4', name: '北京中发电子市场·联盛', region: '华北·北京',
      categories: ['通用元件'],
      brands: ['多品牌(未明确)'],
      qualifications: [],
      moq: 20000, response_speed: '约 5 个工作日',
      data_source: '平台自报(资质未验证)', updated_at: '2025-06-15',
      confirmed_stock: false, confirmed_lead: false, confirmed_price: false,
      match_score: 0.61,
    },
    {
      id: 's5', name: '深圳某现货贸易商', region: '华南·深圳',
      categories: ['现货贸易'],
      brands: ['不明'],
      qualifications: [],
      moq: 1000, response_speed: '12h 内首次响应',
      data_source: '单一来源,资质未验证', updated_at: '2025-05-20',
      confirmed_stock: false, confirmed_lead: false, confirmed_price: false,
      match_score: 0.55,
    },
  ]
}

export function buildLeadGrade(): LeadGrade {
  return {
    grade: 'B',
    score: 72,
    reasons: [
      '月用量 50 万属中高量级,具备议价空间',
      '已匹配 3 家资质较全的目标供应商',
      '需求规格明确度高,可替代方案清晰',
      '原型号缺货场景,价格敏感度中等',
    ],
  }
}

/** LLM 生成失败时的固定模板兜底 */
export function buildRfqTemplate(input: {
  rawQuery: string
  spec: Record<string, SpecField> | null
  alternatives: Alternative[]
  suppliers: Supplier[]
}): string {
  const s = input.spec || {}
  const f = (k: string) => s[k]?.value || '__(待补充)__'
  const altLines = input.alternatives
    .filter((a) => a.level !== 'L5')
    .map((a, i) => `${i + 1}. ${a.part_name} (${a.brand}) — ${a.level} ${a.level === 'L2' ? '跨品牌兼容' : '需工程评估'}`)
    .join('\n')
  const supLines = input.suppliers.slice(0, 3).map((sp) => sp.name).join(' / ')
  return `【询价单 RFQ】
RFQ-ID: MF-${Date.now().toString().slice(-8)}
日期: ${new Date().toISOString().slice(0, 10)}

一、品名
多层陶瓷贴片电容(MLCC)

二、原始需求
${input.rawQuery}

三、规格要求
- 封装: ${f('封装')}
- 标称容值: ${f('容值')}
- 容差: ${f('容差')}
- 温度系数: ${f('温度系数')}
- 额定电压: ${f('额定电压')}
- 月用量: ${f('月用量')}
- 期望交期: ${f('交期要求')}

四、可接受替代料(仅供参考,需工程师确认)
${altLines || '__(待补充)__'}

五、目标供应商
${supLines || '__(待补充)__'}

六、说明
本询价单由 MatchForge AI 辅助生成,替代料仅供参考,最终可替代性须由工程师确认。
供应商回复的库存 / 交期 / 价格均以正式确认为准,本平台不承诺实时库存与报价。`
}

/** 流式 RFQ 文本(供 gen_rfq 阶段逐 token 切片推送) */
export function buildRfqStream(input: {
  spec: Record<string, SpecField> | null
  alternatives: Alternative[]
  suppliers: Supplier[]
}): string {
  return buildRfqTemplate({
    rawQuery: 'TMK212BJ105KG-T 缺货,找替代',
    spec: input.spec,
    alternatives: input.alternatives,
    suppliers: input.suppliers,
  })
}

/** 信息不足时的空 state */
export function buildVagueState(threadId: string, query: string): Partial<ProcureState> {
  return {
    thread_id: threadId,
    raw_query: query,
    parsed_spec: null,
    normalized_spec: null,
    alternatives: [],
    matched_suppliers: [],
    rfq_doc: null,
    rfq_id: null,
    lead_grade: null,
    errors: ['需求信息严重不足:未识别到有效型号或规格参数,无法安全推荐替代料,请补充型号或规格描述'],
  }
}
