<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'
import Tag from '@/components/ui/Tag.vue'

interface LeadItem {
  id: string
  title: string
  spec: string
  grade: 'A' | 'B' | 'C' | 'D'
  score: number
  moq: number
  qty: number
  company: string
  date: string
  status: 'new' | 'contacted' | 'quoted' | 'won' | 'lost'
  message?: string
}

const leads = ref<LeadItem[]>([])
const loading = ref(true)
const activeTab = ref<'all' | 'new' | 'won'>('all')

const filteredLeads = computed(() => {
  if (activeTab.value === 'all') return leads.value
  return leads.value.filter((l) => l.status === activeTab.value)
})

function statusLabel(s: string) {
  const map: Record<string, string> = { new: '新线索', contacted: '已联系', quoted: '已报价', won: '已成交', lost: '已流失' }
  return map[s] || s
}

function statusClass(s: string) {
  const map: Record<string, string> = { new: 'tag-blue', contacted: 'tag-yellow', quoted: 'tag-yellow', won: 'tag-green', lost: 'tag-gray' }
  return map[s] || 'tag-gray'
}

function gradeClass(g: string) {
  if (g === 'A' || g === 'B') return 'grade--high'
  if (g === 'C') return 'grade--mid'
  return 'grade--low'
}

function handleRespond(lead: LeadItem) {
  alert(`回复询价: ${lead.id}\n功能将在 MVP 阶段对接真实消息系统。`)
}

function handleQuote(lead: LeadItem) {
  alert(`报价: ${lead.id}\n功能将在 MVP 阶段对接询价单系统。`)
}

onMounted(() => {
  setTimeout(() => {
    leads.value = [
      { id: 'L001', title: 'MLCC 0805 10uF X7R 50V', spec: '0805 10uF X7R ±10% 50V', grade: 'A', score: 88, moq: 5000, qty: 500000, company: '深圳华强电子', date: '2026-07-14', status: 'new', message: '请报含税单价及交期，月用量50万' },
      { id: 'L002', title: 'TMK212BJ105KG-T 替代料', spec: '0805 1uF X5R 25V', grade: 'B', score: 72, moq: 10000, qty: 200000, company: '上海赛格电子', date: '2026-07-13', status: 'new' },
      { id: 'L003', title: 'GRM188R61A106KE69D 寻源', spec: '0603 10uF X5R 10V', grade: 'C', score: 55, moq: 20000, qty: 100000, company: '东莞电子科技', date: '2026-07-11', status: 'contacted' },
      { id: 'L004', title: 'CC0805KKX7R9BB103 批量', spec: '0805 10nF X7R 50V', grade: 'A', score: 92, moq: 3000, qty: 1000000, company: '北京中发电子', date: '2026-07-10', status: 'quoted' },
      { id: 'L005', title: 'CL21B105KAFNNNE 询价', spec: '0805 1uF X5R 25V', grade: 'B', score: 68, moq: 5000, qty: 300000, company: '苏州元器件贸易', date: '2026-07-08', status: 'won' },
    ]
    loading.value = false
  }, 500)
})
</script>

<template>
  <div class="supplier-page">
    <div class="page-head">
      <div>
        <h2 class="page-title">线索管理</h2>
        <p class="page-desc">查看和处理采购询价线索</p>
      </div>
    </div>

    <!-- Tabs -->
    <div class="tabs">
      <button class="tab" :class="{ active: activeTab === 'all' }" @click="activeTab = 'all'">全部</button>
      <button class="tab" :class="{ active: activeTab === 'new' }" @click="activeTab = 'new'">新线索</button>
      <button class="tab" :class="{ active: activeTab === 'won' }" @click="activeTab = 'won'">已成交</button>
    </div>

    <!-- 加载 -->
    <div v-if="loading" class="card">
      <div class="card__body">
        <div v-for="i in 3" :key="i" class="skeleton" style="height: 60px; margin-bottom: 8px" />
      </div>
    </div>

    <!-- 空态 -->
    <div v-else-if="filteredLeads.length === 0" class="card">
      <div class="card__body empty-state">
        <p class="empty-icon">📋</p>
        <p>暂无线索</p>
      </div>
    </div>

    <!-- 列表 -->
    <div v-else class="leads-list">
      <div v-for="lead in filteredLeads" :key="lead.id" class="lead-card card">
        <div class="lead-card__head">
          <div class="lead-card__info">
            <div class="lead-card__title">{{ lead.title }}</div>
            <div class="lead-card__spec mono">{{ lead.spec }}</div>
          </div>
          <div class="lead-card__badges">
            <span class="inline-grade" :class="gradeClass(lead.grade)">{{ lead.grade }} {{ lead.score }}</span>
            <span class="tag" :class="statusClass(lead.status)">{{ statusLabel(lead.status) }}</span>
          </div>
        </div>

        <div class="lead-card__meta">
          <div class="lead-meta-item">
            <span class="meta-label">采购方</span>
            <span>{{ lead.company }}</span>
          </div>
          <div class="lead-meta-item">
            <span class="meta-label">月用量</span>
            <span>{{ lead.qty.toLocaleString() }} pcs</span>
          </div>
          <div class="lead-meta-item">
            <span class="meta-label">MOQ</span>
            <span>{{ lead.moq.toLocaleString() }} pcs</span>
          </div>
          <div class="lead-meta-item">
            <span class="meta-label">日期</span>
            <span>{{ lead.date }}</span>
          </div>
        </div>

        <div v-if="lead.message" class="lead-card__msg">
          <span class="msg-label">询价备注：</span>
          {{ lead.message }}
        </div>

        <div class="lead-card__actions">
          <AppButton variant="ghost" size="sm" @click="handleRespond(lead)">回复</AppButton>
          <AppButton variant="primary" size="sm" @click="handleQuote(lead)">报价</AppButton>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.supplier-page {
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

.tabs {
  display: flex;
  gap: 0;
  margin-bottom: var(--space-4);
  border-bottom: 1px solid var(--border-default);
}
.tab {
  padding: 8px 20px;
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

.card {
  background: var(--bg-2);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  margin-bottom: var(--space-3);
}
.card__body { padding: var(--space-4); }

.leads-list { display: flex; flex-direction: column; gap: var(--space-3); }
.lead-card { padding: var(--space-4); }
.lead-card__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.lead-card__title { font-weight: 600; font-size: var(--font-size-md); }
.lead-card__spec { font-size: var(--font-size-sm); color: var(--text-tertiary); margin-top: 4px; }
.lead-card__badges { display: flex; gap: var(--space-2); align-items: center; flex-shrink: 0; }
.lead-card__meta {
  display: flex;
  gap: var(--space-5);
  margin-bottom: var(--space-3);
  font-size: var(--font-size-sm);
  flex-wrap: wrap;
}
.lead-meta-item { display: flex; gap: 6px; }
.meta-label { color: var(--text-tertiary); }
.lead-card__msg {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  padding: var(--space-2) var(--space-3);
  background: var(--bg-3);
  border-radius: var(--radius-sm);
  margin-bottom: var(--space-3);
}
.msg-label { color: var(--text-tertiary); }
.lead-card__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}

.inline-grade {
  font-family: var(--font-mono);
  font-weight: 600;
  font-size: var(--font-size-sm);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
}
.grade--high { color: var(--success); background: var(--success-soft); }
.grade--mid { color: var(--warning); background: var(--warning-soft); }
.grade--low { color: var(--danger); background: var(--danger-soft); }

.tag { font-size: var(--font-size-xs); padding: 2px 8px; border-radius: var(--radius-sm); }
.tag-blue { color: var(--accent); background: var(--accent-soft); }
.tag-yellow { color: var(--warning); background: var(--warning-soft); }
.tag-green { color: var(--success); background: var(--success-soft); }
.tag-gray { color: var(--text-tertiary); background: var(--bg-3); }

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
</style>
