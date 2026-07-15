<template>
  <div class="page-container">
    <h2 class="page-title">运营审核</h2>

    <div class="tabs">
      <button
        class="tab"
        :class="{ active: activeTab === 'alternatives' }"
        @click="activeTab = 'alternatives'"
      >
        替代料审核
      </button>
      <button
        class="tab"
        :class="{ active: activeTab === 'suppliers' }"
        @click="activeTab = 'suppliers'"
      >
        供应商审核
      </button>
    </div>

    <!-- 替代料审核队列 -->
    <template v-if="activeTab === 'alternatives'">
      <div v-if="altQueue.length === 0" class="card">
        <div class="card-body empty-state">
          <p class="icon">✅</p>
          <p><strong>无待审核项</strong></p>
        </div>
      </div>

      <div v-for="item in altQueue" :key="item.id" class="card audit-card">
        <div class="card-body">
          <div class="audit-header">
            <div class="audit-info">
              <span class="audit-label">替代关系</span>
              <span class="part">{{ item.originalPart }}</span>
              <span class="arrow">→</span>
              <span class="part">{{ item.altPart }}</span>
              <span class="tag tag-yellow">置信度 {{ ((item.confidence ?? 0) * 100).toFixed(0) }}%</span>
            </div>
            <span class="audit-time">{{ item.submittedAt }}</span>
          </div>

          <div class="audit-meta">
            <div><strong>来源：</strong>{{ item.source }}</div>
            <div><strong>推荐依据：</strong>{{ item.reason }}</div>
          </div>

          <div class="audit-actions">
            <input v-model="item.sourceInput" class="source-input" placeholder="补充来源链接" />
            <button class="btn btn-sm btn-danger" @click="reject(item)">驳回</button>
            <button class="btn btn-sm btn-secondary" @click="markRisk(item)">标记风险</button>
            <button class="btn btn-sm btn-primary" @click="approve(item)">通过</button>
          </div>
        </div>
      </div>
    </template>

    <!-- 供应商审核队列 -->
    <template v-if="activeTab === 'suppliers'">
      <div v-if="supQueue.length === 0" class="card">
        <div class="card-body empty-state">
          <p class="icon">✅</p>
          <p><strong>无待审核项</strong></p>
        </div>
      </div>

      <div v-for="item in supQueue" :key="item.id" class="card audit-card">
        <div class="card-body">
          <div class="audit-header">
            <div class="audit-info">
              <span class="audit-label">供应商</span>
              <span class="part">{{ item.name }}</span>
              <span class="tag tag-yellow">{{ item.status }}</span>
            </div>
            <span class="audit-time">{{ item.submittedAt }}</span>
          </div>

          <div class="audit-meta">
            <div><strong>品类：</strong>{{ item.category }}</div>
            <div><strong>品牌：</strong>{{ (item.brands || []).join('、') }}</div>
            <div><strong>资质：</strong>{{ (item.qualifications || []).join('、') || '无' }}</div>
            <div><strong>地区：</strong>{{ item.location }}</div>
          </div>

          <div class="audit-actions">
            <input v-model="item.sourceInput" class="source-input" placeholder="补充来源/备注" />
            <button class="btn btn-sm btn-danger" @click="rejectSup(item)">驳回</button>
            <button class="btn btn-sm btn-primary" @click="approveSup(item)">通过</button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const activeTab = ref<'alternatives' | 'suppliers'>('alternatives')

interface AuditItem {
  id: string
  originalPart?: string
  altPart?: string
  confidence?: number
  source: string
  reason?: string
  submittedAt: string
  sourceInput: string
  // supplier fields
  name?: string
  status?: string
  category?: string
  brands?: string[]
  qualifications?: string[]
  location?: string
}

const altQueue = ref<AuditItem[]>([
  {
    id: 'A001',
    originalPart: 'TMK212BJ105KG-T',
    altPart: '0805F105Z500NT',
    confidence: 0.66,
    source: 'llm_inferred',
    reason: '封装/容值匹配，额定电压有差异',
    submittedAt: '2026-07-14 10:30',
    sourceInput: '',
  },
])

const supQueue = ref<AuditItem[]>([
  {
    id: 'S001',
    name: '深圳芯联电子有限公司',
    status: 'pending',
    category: 'MLCC',
    brands: ['三星', '国巨'],
    qualifications: ['ISO9001'],
    location: '深圳',
    submittedAt: '2026-07-14 09:00',
    source: '供应商自报',
    sourceInput: '',
  },
])

function approve(item: AuditItem) {
  alert(`已通过: ${item.altPart}`)
  altQueue.value = altQueue.value.filter((i) => i.id !== item.id)
}

function reject(item: AuditItem) {
  const reason = prompt('驳回原因:')
  if (reason) {
    alert(`已驳回: ${item.altPart}`)
    altQueue.value = altQueue.value.filter((i) => i.id !== item.id)
  }
}

function markRisk(item: AuditItem) {
  alert(`已标记风险: ${item.altPart}`)
}

function approveSup(item: AuditItem) {
  alert(`已通过: ${item.name}`)
  supQueue.value = supQueue.value.filter((i) => i.id !== item.id)
}

function rejectSup(item: AuditItem) {
  const reason = prompt('驳回原因:')
  if (reason) {
    alert(`已驳回: ${item.name}`)
    supQueue.value = supQueue.value.filter((i) => i.id !== item.id)
  }
}
</script>

<style scoped>
.page-title {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 16px;
}

.tabs {
  display: flex;
  gap: 0;
  margin-bottom: 16px;
  border-bottom: 1px solid var(--color-border);
}

.tab {
  padding: 8px 20px;
  border: none;
  background: none;
  font-size: 14px;
  color: var(--color-text-secondary);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.15s;
}

.tab:hover {
  color: var(--color-text);
}

.tab.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
  font-weight: 600;
}

.audit-card {
  margin-bottom: 12px;
}

.audit-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.audit-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.audit-label {
  font-size: 12px;
  color: var(--color-text-muted);
  background: #f1f5f9;
  padding: 2px 8px;
  border-radius: 4px;
}

.part {
  font-weight: 600;
  font-family: 'SF Mono', 'Cascadia Code', monospace;
  font-size: 14px;
}

.arrow {
  color: var(--color-text-muted);
}

.audit-time {
  font-size: 12px;
  color: var(--color-text-muted);
}

.audit-meta {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-bottom: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.audit-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  padding-top: 12px;
  border-top: 1px solid var(--color-border);
}

.source-input {
  flex: 1;
  padding: 4px 8px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 12px;
  font-family: inherit;
}

.source-input:focus {
  outline: none;
  border-color: var(--color-primary);
}
</style>