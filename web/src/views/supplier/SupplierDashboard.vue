<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AppButton from '@/components/ui/AppButton.vue'

const router = useRouter()
const auth = useAuthStore()

const stats = ref({
  activeLeads: 0,
  totalProducts: 0,
  newInquiries: 0,
  responseRate: 0,
})

const recentLeads = ref<
  { id: string; title: string; grade: string; score: number; date: string; status: string }[]
>([])

const loading = ref(true)

// 模拟数据
onMounted(() => {
  setTimeout(() => {
    stats.value = {
      activeLeads: 4,
      totalProducts: 26,
      newInquiries: 2,
      responseRate: 78,
    }
    recentLeads.value = [
      { id: 'L001', title: 'MLCC 0805 10uF X7R 50V', grade: 'A', score: 88, date: '2026-07-14', status: 'new' },
      { id: 'L002', title: 'TMK212BJ105KG-T 替代料', grade: 'B', score: 72, date: '2026-07-13', status: 'contacted' },
      { id: 'L003', title: 'GRM188R61A106KE69D 寻源', grade: 'C', score: 55, date: '2026-07-12', status: 'won' },
    ]
    loading.value = false
  }, 600)
})

function gradeClass(grade: string) {
  if (grade === 'A') return 'grade-A'
  if (grade === 'B') return 'grade-B'
  if (grade === 'C') return 'grade-c'
  return 'grade-d'
}
</script>

<template>
  <div class="supplier-page">
    <div class="page-head">
      <div>
        <h2 class="page-title">供应商工作台</h2>
        <p class="page-desc">{{ auth.user?.company || '您的企业' }} · 供应商端</p>
      </div>
      <AppButton variant="primary" @click="router.push('/supplier/products')">
        管理产品
      </AppButton>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-card__value">{{ stats.activeLeads }}</div>
        <div class="stat-card__label">活跃线索</div>
      </div>
      <div class="stat-card">
        <div class="stat-card__value">{{ stats.totalProducts }}</div>
        <div class="stat-card__label">产品总数</div>
      </div>
      <div class="stat-card">
        <div class="stat-card__value stat-card__value--warn">{{ stats.newInquiries }}</div>
        <div class="stat-card__label">新询价待处理</div>
      </div>
      <div class="stat-card">
        <div class="stat-card__value">{{ stats.responseRate }}%</div>
        <div class="stat-card__label">历史响应率</div>
      </div>
    </div>

    <!-- 最近线索 -->
    <div class="card">
      <div class="card__head">
        <h3>最近线索</h3>
        <AppButton variant="ghost" size="sm" @click="router.push('/supplier/leads')">
          查看全部 →
        </AppButton>
      </div>
      <div class="card__body">
        <table v-if="recentLeads.length" class="table">
          <thead>
            <tr>
              <th>线索</th>
              <th>分级</th>
              <th>时间</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="lead in recentLeads" :key="lead.id">
              <td>{{ lead.title }}</td>
              <td>
                <span class="inline-grade" :class="gradeClass(lead.grade)">
                  {{ lead.grade }} {{ lead.score }}分
                </span>
              </td>
              <td class="text-muted">{{ lead.date }}</td>
              <td>
                <span class="state-tag" :class="`state-${lead.status}`">
                  {{ lead.status === 'new' ? '新线索' : lead.status === 'contacted' ? '已联系' : '已成交' }}
                </span>
              </td>
              <td>
                <AppButton variant="ghost" size="sm">查看</AppButton>
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
      <div class="quick-card" @click="router.push('/supplier/products')">
        <div class="quick-card__icon">📦</div>
        <div class="quick-card__title">产品管理</div>
        <div class="quick-card__desc">管理您的元器件产品目录</div>
      </div>
      <div class="quick-card" @click="router.push('/supplier/leads')">
        <div class="quick-card__icon">📋</div>
        <div class="quick-card__title">线索管理</div>
        <div class="quick-card__desc">查看和处理采购询价</div>
      </div>
      <div class="quick-card" @click="router.push('/supplier/profile')">
        <div class="quick-card__icon">🏢</div>
        <div class="quick-card__title">企业信息</div>
        <div class="quick-card__desc">更新资质和经营信息</div>
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

.text-muted { color: var(--text-tertiary); }

.inline-grade {
  font-family: var(--font-mono);
  font-weight: 600;
  font-size: var(--font-size-sm);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
}
.grade-A { color: var(--success); background: var(--success-soft); }
.grade-B { color: var(--success); background: var(--success-soft); }
.grade-c { color: var(--warning); background: var(--warning-soft); }

.state-tag {
  font-size: var(--font-size-xs);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
}
.state-new { color: var(--accent); background: var(--accent-soft); }
.state-contacted { color: var(--warning); background: var(--warning-soft); }
.state-won { color: var(--success); background: var(--success-soft); }

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
