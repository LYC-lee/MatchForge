<script setup lang="ts">
import { ref, watch, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useEnterpriseContext } from '@/composables/useEnterpriseContext'
import { onDemoRefresh } from '@/composables/useDemoRefresh'
import { getSupplierLeads, type SupplierLead } from '@/api/enterprise'
import { useDemo } from '@/composables/useDemo'
import AppButton from '@/components/ui/AppButton.vue'

const router = useRouter()
const { current, currentEnterpriseId } = useEnterpriseContext()
const demo = useDemo()

const isDemo = computed(() => demo.isDemo.value)

const leads = ref<SupplierLead[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

async function fetchLeads(companyId: number) {
  if (isDemo.value) {
    // demo 模式: loading 状态跟随 useDemo
    loading.value = demo.loadingSupplier.value
    return
  }
  loading.value = true
  error.value = null
  try {
    const res = await getSupplierLeads(companyId)
    leads.value = (res.data?.items || []) as SupplierLead[]
  } catch (e: any) {
    error.value = e?.message || '接口不可用'
    leads.value = []
  } finally {
    loading.value = false
  }
}

// 加载超时保护: 8 秒后强制展示内容（即使 loading 未完成）
onMounted(() => {
  setTimeout(() => {
    if (loading.value) {
      loading.value = false
    }
  }, 8000)
})

watch(currentEnterpriseId, (id) => {
  if (id) fetchLeads(id)
}, { immediate: true })

onDemoRefresh(() => {
  if (isDemo.value) {
    demo.fetchSupplierView()
  } else {
    fetchLeads(currentEnterpriseId.value)
  }
})

/** 统一统计: demo 模式从 supplierView 派生, 否则从真实 leads 派生 */
const stats = computed(() => {
  if (isDemo.value) {
    const items = demo.supplierView.value?.items || []
    return {
      activeLeads: items.filter((i) => i.rfq_status !== 'closed' && !i.my_quote).length,
      totalLeads: items.length,
      newInquiries: items.filter((i) => i.rfq_status === 'sent' && !i.my_quote).length,
      quoted: items.filter((i) => !!i.my_quote).length,
    }
  }
  return {
    activeLeads: leads.value.filter((l) => l.status !== 'declined' && l.status !== 'quoted').length,
    totalLeads: leads.value.length,
    newInquiries: leads.value.filter((l) => l.status === 'sent' || l.status === 'pending').length,
    quoted: leads.value.filter((l) => l.status === 'quoted').length,
  }
})

const recentLeads = computed(() => {
  if (isDemo.value) {
    const items = demo.supplierView.value?.items || []
    return items.slice(0, 5).map((i) => ({
      id: i.rfq_id,
      rfq_number: i.rfq_number,
      buyer_name: i.buyer_name,
      part_name: i.part_name || i.part_number,
      part_number: i.part_number,
      quantity: i.quantity,
      status: i.my_quote ? 'quoted' : (i.rfq_status === 'sent' ? 'sent' : i.rfq_status),
    }))
  }
  return leads.value.slice(0, 5)
})

function statusLabel(s: string) {
  const map: Record<string, string> = {
    pending: '待发送', sent: '新线索', viewed: '已查看', quoted: '已报价', declined: '已拒绝',
    closed: '已关闭',
  }
  return map[s] || s
}

function statusClass(s: string) {
  const map: Record<string, string> = {
    pending: 'state-pending', sent: 'state-new', viewed: 'state-contacted', quoted: 'state-won', declined: 'state-lost',
    closed: 'state-lost',
  }
  return map[s] || 'state-pending'
}
</script>

<template>
  <div class="supplier-page">
    <div class="page-head">
      <div>
        <span class="eyebrow">{{ current.company.name }}</span>
        <h2 class="page-title">供应商工作台</h2>
        <p class="page-desc">当前企业作为供应商, 查看收到的 RFQ 线索并在线报价。</p>
      </div>
      <AppButton variant="primary" @click="router.push('/supplier/leads')">
        管理线索
      </AppButton>
    </div>

    <div v-if="loading" class="loading-bar">正在拉取供应商线索…</div>
    <div v-else-if="error" class="notice-bar">线索接口不可用: {{ error }}</div>
    <div v-if="isDemo" class="notice-bar notice-bar--demo">演示沙盘数据 · 线索来自当前企业作为候选供应商收到的 demo RFQ (基于直接关系动态匹配)</div>

    <!-- 统计卡片 -->
    <div v-if="!loading" class="stats-grid">
      <div class="stat-card">
        <div class="stat-card__value">{{ stats.totalLeads }}</div>
        <div class="stat-card__label">线索总数</div>
      </div>
      <div class="stat-card">
        <div class="stat-card__value">{{ stats.activeLeads }}</div>
        <div class="stat-card__label">活跃线索</div>
      </div>
      <div class="stat-card">
        <div class="stat-card__value stat-card__value--warn">{{ stats.newInquiries }}</div>
        <div class="stat-card__label">新询价待处理</div>
      </div>
      <div class="stat-card">
        <div class="stat-card__value">{{ stats.quoted }}</div>
        <div class="stat-card__label">已报价</div>
      </div>
    </div>

    <!-- 最近线索 -->
    <div v-if="!loading" class="card">
      <div class="card__head">
        <h3>最近线索</h3>
        <AppButton variant="ghost" size="sm" @click="router.push('/supplier/leads')">
          查看全部 ->
        </AppButton>
      </div>
      <div class="card__body">
        <table v-if="recentLeads.length" class="table">
          <thead>
            <tr>
              <th>RFQ</th>
              <th>采购方</th>
              <th>零件</th>
              <th>数量</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="lead in recentLeads" :key="lead.id">
              <td class="mono">{{ lead.rfq_number }}</td>
              <td>{{ lead.buyer_name || '-' }}</td>
              <td>{{ lead.part_name || lead.part_number || '-' }}</td>
              <td>{{ lead.quantity?.toLocaleString() || '-' }}</td>
              <td>
                <span class="state-tag" :class="statusClass(lead.status)">{{ statusLabel(lead.status) }}</span>
              </td>
              <td>
                <AppButton variant="ghost" size="sm" @click="router.push('/supplier/leads')">处理</AppButton>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty-state">
          <p>暂无线索</p>
        </div>
      </div>
    </div>

    <!-- 快速入口 -->
    <div class="quick-links">
      <div class="quick-card" @click="router.push('/supplier/leads')">
        <div class="quick-card__icon">📋</div>
        <div class="quick-card__title">线索管理</div>
        <div class="quick-card__desc">查看和处理采购询价, 在线提交报价</div>
      </div>
      <div class="quick-card" @click="router.push('/products-bom')">
        <div class="quick-card__icon">📦</div>
        <div class="quick-card__title">产品与 BOM</div>
        <div class="quick-card__desc">查看当前企业的可生产产品与 BOM</div>
      </div>
      <div class="quick-card" @click="router.push('/company-assistant')">
        <div class="quick-card__icon">🏢</div>
        <div class="quick-card__title">企业内部问答</div>
        <div class="quick-card__desc">基于企业知识回答经营问题</div>
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
.eyebrow { color: var(--text-tertiary); font-size: var(--font-size-xs); font-weight: 700; }
.page-title { font-size: var(--font-size-xl); font-weight: 700; margin-top: 4px; }
.page-desc { color: var(--text-secondary); margin-top: 4px; font-size: var(--font-size-sm); }
.loading-bar { padding: var(--space-3) var(--space-4); margin-bottom: var(--space-4); border-radius: 6px; border: 1px solid var(--border-subtle); background: var(--bg-2); color: var(--text-tertiary); font-size: var(--font-size-sm); }
.notice-bar { padding: var(--space-3) var(--space-4); margin-bottom: var(--space-4); border-radius: 6px; border: 1px solid rgba(234, 179, 8, 0.25); background: var(--warning-soft); color: var(--warning); font-size: var(--font-size-sm); }
.notice-bar--demo { border: 1px solid rgba(99, 102, 241, 0.3); background: var(--accent-soft); color: var(--accent); }

/* 统计卡片 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-3);
  margin-bottom: var(--space-5);
}
.stat-card {
  padding: var(--space-5);
  background: var(--bg-2);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
}
.stat-card__value { font-size: var(--font-size-3xl); font-weight: 700; color: var(--text-primary); }
.stat-card__value--warn { color: var(--warning); }
.stat-card__label { font-size: var(--font-size-sm); color: var(--text-tertiary); margin-top: 4px; }

/* 卡片通用 */
.card {
  background: var(--bg-2);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  margin-bottom: var(--space-5);
}
.card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-subtle);
}
.card__head h3 { font-size: var(--font-size-md); font-weight: 600; }
.card__body { padding: var(--space-4); }

.table { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
.table th { text-align: left; color: var(--text-tertiary); font-size: var(--font-size-xs); padding: 8px 12px; border-bottom: 1px solid var(--border-default); font-weight: 600; }
.table td { padding: 10px 12px; border-bottom: 1px solid var(--border-subtle); color: var(--text-secondary); }
.mono { font-family: var(--font-mono); font-size: var(--font-size-xs); }

.state-tag {
  font-size: var(--font-size-xs);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
}
.state-pending { color: var(--text-tertiary); background: var(--bg-3); }
.state-new { color: var(--accent); background: var(--accent-soft); }
.state-contacted { color: var(--warning); background: var(--warning-soft); }
.state-won { color: var(--success); background: var(--success-soft); }
.state-lost { color: var(--text-tertiary); background: var(--bg-3); }

.empty-state { text-align: center; padding: var(--space-6); color: var(--text-tertiary); }

/* 快速入口 */
.quick-links {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-3);
}
.quick-card {
  padding: var(--space-5);
  background: var(--bg-2);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.quick-card:hover {
  border-color: var(--accent-border);
  background: var(--bg-elevated);
}
.quick-card__icon { font-size: 28px; margin-bottom: var(--space-3); }
.quick-card__title { font-size: var(--font-size-md); font-weight: 600; margin-bottom: var(--space-2); }
.quick-card__desc { font-size: var(--font-size-sm); color: var(--text-tertiary); }

@media (max-width: 768px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .quick-links { grid-template-columns: 1fr; }
}
</style>
