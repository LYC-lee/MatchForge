<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'

// ── 统计概览 ──
const stats = ref({
  pendingAlts: 3,
  pendingSuppliers: 2,
  totalAudited: 128,
  avgResponseTime: '2.4h',
})

// ── 审核项 ──
interface AltAuditItem {
  id: string
  originalPart: string
  altPart: string
  brand: string
  confidence: number
  source: string
  reason: string
  submittedAt: string
  status: 'pending' | 'approved' | 'rejected' | 'risk'
  sourceInput: string
  reviewer?: string
}

interface SupAuditItem {
  id: string
  name: string
  company: string
  status: 'pending' | 'approved' | 'rejected'
  category: string
  brands: string[]
  qualifications: string[]
  location: string
  contact: string
  submittedAt: string
  sourceInput: string
}

const activeTab = ref<'alternatives' | 'suppliers'>('alternatives')
const altQueue = ref<AltAuditItem[]>([])
const supQueue = ref<SupAuditItem[]>([])
const loading = ref(true)
const searchQuery = ref('')

const filteredAlts = computed(() => {
  if (!searchQuery.value) return altQueue.value
  const q = searchQuery.value.toLowerCase()
  return altQueue.value.filter(
    (a) => a.originalPart.toLowerCase().includes(q) || a.altPart.toLowerCase().includes(q) || a.brand.toLowerCase().includes(q),
  )
})

const filteredSups = computed(() => {
  if (!searchQuery.value) return supQueue.value
  const q = searchQuery.value.toLowerCase()
  return supQueue.value.filter(
    (s) => s.name.toLowerCase().includes(q) || s.company.toLowerCase().includes(q) || s.category.toLowerCase().includes(q),
  )
})

// ── 审核操作 ──
function approveAlt(item: AltAuditItem) {
  item.status = 'approved'
  altQueue.value = altQueue.value.filter((i) => i.id !== item.id)
  stats.value.pendingAlts--
}

function rejectAlt(item: AltAuditItem) {
  const reason = prompt('驳回原因（可选）:')
  item.status = 'rejected'
  altQueue.value = altQueue.value.filter((i) => i.id !== item.id)
  stats.value.pendingAlts--
  if (reason) item.reason = reason
}

function markRiskAlt(item: AltAuditItem) {
  item.status = 'risk'
  altQueue.value = altQueue.value.filter((i) => i.id !== item.id)
  stats.value.pendingAlts--
}

function approveSup(item: SupAuditItem) {
  item.status = 'approved'
  supQueue.value = supQueue.value.filter((i) => i.id !== item.id)
  stats.value.pendingSuppliers--
}

function rejectSup(item: SupAuditItem) {
  const reason = prompt('驳回原因（可选）:')
  item.status = 'rejected'
  supQueue.value = supQueue.value.filter((i) => i.id !== item.id)
  stats.value.pendingSuppliers--
}

function statusTag(status: string) {
  const map: Record<string, string> = {
    pending: 'tag-yellow',
    approved: 'tag-green',
    rejected: 'tag-gray',
    risk: 'tag-red',
  }
  return map[status] || 'tag-gray'
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    pending: '待审核',
    approved: '已通过',
    rejected: '已驳回',
    risk: '标记风险',
  }
  return map[status] || status
}

// ── 数据加载 ──
onMounted(() => {
  setTimeout(() => {
    altQueue.value = [
      { id: 'A001', originalPart: 'TMK212BJ105KG-T', altPart: '0805F105Z500NT', brand: 'Walsin', confidence: 0.66, source: 'llm_inferred', reason: '封装/容值匹配，额定电压有差异', submittedAt: '2026-07-14 10:30', status: 'pending', sourceInput: '' },
      { id: 'A002', originalPart: 'GRM188R61A106KE69D', altPart: 'CL10A106MP8NNNC', brand: 'Samsung EM', confidence: 0.58, source: 'llm_inferred(单一来源)', reason: '容值/封装匹配，温度系数差异需确认', submittedAt: '2026-07-14 09:15', status: 'pending', sourceInput: '' },
      { id: 'A003', originalPart: 'CC0805KKX7R9BB103', altPart: '0805B103K500CT', brand: 'Walsin', confidence: 0.72, source: '分销商数据', reason: '参数一致，来源为分销商数据需交叉核验', submittedAt: '2026-07-13 16:45', status: 'pending', sourceInput: '' },
    ]
    supQueue.value = [
      { id: 'S001', name: '深圳芯联电子有限公司', company: '芯联电子', status: 'pending', category: 'MLCC / 贴片电阻', brands: ['三星', '国巨'], qualifications: ['ISO9001'], location: '深圳', contact: '张经理', submittedAt: '2026-07-14 09:00', sourceInput: '' },
      { id: 'S002', name: '苏州微电子科技有限公司', company: '苏州微电子', status: 'pending', category: '被动元件 / 连接器', brands: ['Murata', 'TDK'], qualifications: ['ISO9001', 'IATF16949'], location: '苏州', contact: '李工', submittedAt: '2026-07-13 14:20', sourceInput: '' },
    ]
    loading.value = false
  }, 400)
})
</script>

<template>
  <div class="admin-page">
    <!-- 标题 -->
    <div class="page-head">
      <div>
        <h2 class="page-title">运营审核</h2>
        <p class="page-desc">人工审核低置信替代料和新入驻供应商数据</p>
      </div>
    </div>

    <!-- 统计概览 -->
    <div class="stats-row">
      <div class="stat-chip">
        <span class="stat-chip__num">{{ stats.pendingAlts }}</span>
        <span class="stat-chip__label">待审替代料</span>
      </div>
      <div class="stat-chip">
        <span class="stat-chip__num">{{ stats.pendingSuppliers }}</span>
        <span class="stat-chip__label">待审供应商</span>
      </div>
      <div class="stat-chip">
        <span class="stat-chip__num">{{ stats.totalAudited }}</span>
        <span class="stat-chip__label">累计审核</span>
      </div>
      <div class="stat-chip">
        <span class="stat-chip__num">{{ stats.avgResponseTime }}</span>
        <span class="stat-chip__label">平均响应</span>
      </div>
    </div>

    <!-- Tab + 搜索 -->
    <div class="toolbar">
      <div class="tabs">
        <button class="tab" :class="{ active: activeTab === 'alternatives' }" @click="activeTab = 'alternatives'">
          替代料审核
          <span v-if="stats.pendingAlts" class="tab-badge">{{ stats.pendingAlts }}</span>
        </button>
        <button class="tab" :class="{ active: activeTab === 'suppliers' }" @click="activeTab = 'suppliers'">
          供应商审核
          <span v-if="stats.pendingSuppliers" class="tab-badge">{{ stats.pendingSuppliers }}</span>
        </button>
      </div>
      <input v-model="searchQuery" class="search-input" placeholder="搜索型号/供应商…" />
    </div>

    <!-- 加载 -->
    <div v-if="loading" class="card"><div class="card__body"><div v-for="i in 3" :key="i" class="skeleton" style="height: 80px; margin-bottom: 8px" /></div></div>

    <!-- ======== 替代料审核 ======== -->
    <template v-if="activeTab === 'alternatives'">
      <!-- 空态 -->
      <div v-if="!loading && altQueue.length === 0" class="card">
        <div class="card__body empty-state">
          <p class="empty-icon">✅</p>
          <p><strong>无待审核替代料</strong></p>
        </div>
      </div>

      <!-- 列表 -->
      <div v-else class="audit-list">
        <div v-for="item in filteredAlts" :key="item.id" class="audit-card card">
          <div class="audit-card__body">
            <div class="audit-card__head">
              <span class="audit-label">替代关系</span>
              <span class="part mono">{{ item.originalPart }}</span>
              <span class="arrow">→</span>
              <span class="part mono">{{ item.altPart }}</span>
              <span class="tag tag-yellow">置信度 {{ (item.confidence * 100).toFixed(0) }}%</span>
              <span class="brand-tag">{{ item.brand }}</span>
            </div>

            <div class="audit-card__meta">
              <div>
                <span class="meta-label">来源</span>
                <span class="meta-value">{{ item.source }}</span>
              </div>
              <div>
                <span class="meta-label">推荐依据</span>
                <span class="meta-value">{{ item.reason }}</span>
              </div>
              <div>
                <span class="meta-label">提交时间</span>
                <span class="meta-value">{{ item.submittedAt }}</span>
              </div>
              <div>
                <span class="meta-label">状态</span>
                <span class="tag" :class="statusTag(item.status)">{{ statusLabel(item.status) }}</span>
              </div>
            </div>

            <div class="audit-card__actions">
              <input v-model="item.sourceInput" class="source-input" placeholder="补充来源链接 / 备注" />
              <div class="action-btns">
                <AppButton variant="danger" size="sm" @click="rejectAlt(item)">驳回</AppButton>
                <AppButton variant="ghost" size="sm" @click="markRiskAlt(item)">标记风险</AppButton>
                <AppButton variant="primary" size="sm" @click="approveAlt(item)">通过</AppButton>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- ======== 供应商审核 ======== -->
    <template v-if="activeTab === 'suppliers'">
      <div v-if="!loading && supQueue.length === 0" class="card">
        <div class="card__body empty-state">
          <p class="empty-icon">✅</p>
          <p><strong>无待审核供应商</strong></p>
        </div>
      </div>

      <div v-else class="audit-list">
        <div v-for="item in filteredSups" :key="item.id" class="audit-card card">
          <div class="audit-card__body">
            <div class="audit-card__head">
              <span class="audit-label">供应商</span>
              <span class="part">{{ item.name }}</span>
              <span class="tag tag-yellow">{{ item.status === 'pending' ? '待审核' : statusLabel(item.status) }}</span>
            </div>

            <div class="audit-card__meta">
              <div>
                <span class="meta-label">企业名</span>
                <span class="meta-value">{{ item.company }}</span>
              </div>
              <div>
                <span class="meta-label">品类</span>
                <span class="meta-value">{{ item.category }}</span>
              </div>
              <div>
                <span class="meta-label">品牌</span>
                <span class="meta-value">{{ item.brands.join('、') }}</span>
              </div>
              <div>
                <span class="meta-label">资质</span>
                <span class="meta-value">{{ item.qualifications.join('、') || '无' }}</span>
              </div>
              <div>
                <span class="meta-label">地区</span>
                <span class="meta-value">{{ item.location }}</span>
              </div>
              <div>
                <span class="meta-label">联系人</span>
                <span class="meta-value">{{ item.contact }}</span>
              </div>
              <div>
                <span class="meta-label">提交时间</span>
                <span class="meta-value">{{ item.submittedAt }}</span>
              </div>
            </div>

            <div class="audit-card__actions">
              <input v-model="item.sourceInput" class="source-input" placeholder="补充备注" />
              <div class="action-btns">
                <AppButton variant="danger" size="sm" @click="rejectSup(item)">驳回</AppButton>
                <AppButton variant="primary" size="sm" @click="approveSup(item)">通过</AppButton>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.admin-page {
  max-width: 1100px;
  margin: 0 auto;
  padding: var(--space-5);
}
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}
.page-title { font-size: var(--font-size-xl); font-weight: 700; }
.page-desc { color: var(--text-secondary); margin-top: 4px; font-size: var(--font-size-sm); }

/* 统计 */
.stats-row {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-5);
}
.stat-chip {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: var(--space-4);
  background: var(--bg-2);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
}
.stat-chip__num { font-size: var(--font-size-2xl); font-weight: 700; }
.stat-chip__label { font-size: var(--font-size-sm); color: var(--text-tertiary); }

/* 工具条 */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}
.tabs { display: flex; gap: 0; }
.tab {
  position: relative;
  padding: 10px 24px;
  border: none;
  background: none;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.15s;
}
.tab:hover { color: var(--text-primary); }
.tab.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
  font-weight: 600;
}
.tab-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 6px;
  margin-left: 6px;
  border-radius: var(--radius-full);
  background: var(--danger-soft);
  color: var(--danger);
  font-size: var(--font-size-xs);
  font-weight: 700;
}
.search-input {
  width: 240px;
  padding: 8px 12px;
  background: var(--bg-3);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  color: var(--text-primary);
  outline: none;
  transition: border-color var(--transition-fast);
}
.search-input:focus { border-color: var(--accent); }
.search-input::placeholder { color: var(--text-tertiary); }

/* 卡片通用 */
.card {
  background: var(--bg-2);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  margin-bottom: var(--space-3);
}
.card__body { padding: var(--space-4); }

/* 审核卡片 */
.audit-list { display: flex; flex-direction: column; gap: var(--space-3); }
.audit-card { margin-bottom: 0; }
.audit-card__body { padding: var(--space-4); }
.audit-card__head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
}
.audit-label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  background: var(--bg-3);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
}
.part { font-weight: 600; }
.arrow { color: var(--text-tertiary); }
.brand-tag {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  padding: 2px 8px;
  background: var(--bg-3);
  border-radius: var(--radius-sm);
}

.audit-card__meta {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-2) var(--space-4);
  margin-bottom: var(--space-3);
  font-size: var(--font-size-sm);
}
.audit-card__meta > div { display: flex; flex-direction: column; gap: 2px; }
.meta-label { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.meta-value { color: var(--text-secondary); }

.audit-card__actions {
  display: flex;
  gap: var(--space-3);
  align-items: center;
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}
.source-input {
  flex: 1;
  padding: 6px 10px;
  background: var(--bg-3);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  color: var(--text-primary);
  outline: none;
}
.source-input:focus { border-color: var(--accent); }
.source-input::placeholder { color: var(--text-tertiary); }
.action-btns { display: flex; gap: var(--space-2); flex-shrink: 0; }

.tag { font-size: var(--font-size-xs); padding: 2px 8px; border-radius: var(--radius-sm); }
.tag-yellow { color: var(--warning); background: var(--warning-soft); }
.tag-green { color: var(--success); background: var(--success-soft); }
.tag-gray { color: var(--text-tertiary); background: var(--bg-3); }
.tag-red { color: var(--danger); background: var(--danger-soft); }

.empty-state { text-align: center; padding: var(--space-8); color: var(--text-tertiary); }
.empty-icon { font-size: 40px; margin-bottom: var(--space-3); opacity: 0.4; }

.skeleton {
  background: linear-gradient(90deg, var(--bg-3) 25%, var(--border-subtle) 50%, var(--bg-3) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-sm);
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

@media (max-width: 768px) {
  .stats-row { flex-wrap: wrap; }
  .stat-chip { min-width: calc(50% - var(--space-3)); }
  .toolbar { flex-direction: column; align-items: stretch; }
  .search-input { width: 100%; }
  .audit-card__meta { grid-template-columns: repeat(2, 1fr); }
}
</style>
