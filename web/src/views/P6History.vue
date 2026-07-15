<template>
  <div class="page-container">
    <h2 class="page-title">历史记录</h2>

    <!-- Tab 切换 -->
    <div class="tabs">
      <button
        class="tab"
        :class="{ active: activeTab === 'procure' }"
        @click="activeTab = 'procure'"
      >
        寻源记录
      </button>
      <button
        class="tab"
        :class="{ active: activeTab === 'rfq' }"
        @click="activeTab = 'rfq'"
      >
        询价单
      </button>
    </div>

    <!-- 加载 -->
    <div v-if="loading" class="card">
      <div class="card-body">
        <div class="skeleton" style="height: 40px; margin-bottom: 8px" v-for="i in 5" :key="i" />
      </div>
    </div>

    <!-- 错误 -->
    <div v-else-if="loadError" class="card">
      <div class="card-body error-state">
        <p>{{ loadError }}</p>
        <button class="btn btn-primary" @click="fetchRecords">重试</button>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="records.length === 0" class="card">
      <div class="card-body empty-state">
        <p class="icon">📋</p>
        <p><strong>还没有寻源记录</strong></p>
        <router-link to="/" class="btn btn-primary" style="margin-top: 12px">去首页试试</router-link>
      </div>
    </div>

    <!-- 列表 -->
    <div v-else class="card">
      <table class="table">
        <thead>
          <tr>
            <th>时间</th>
            <th>原始需求</th>
            <th>型号</th>
            <th>替代数</th>
            <th>供应商数</th>
            <th v-if="activeTab === 'rfq'">状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="rec in records" :key="rec.id">
            <td class="time-cell">{{ rec.time }}</td>
            <td class="query-cell">{{ rec.rawQuery?.slice(0, 40) }}{{ rec.rawQuery?.length > 40 ? '…' : '' }}</td>
            <td>{{ rec.partNumber || '-' }}</td>
            <td>{{ rec.altCount || 0 }}</td>
            <td>{{ rec.supCount || 0 }}</td>
            <td v-if="activeTab === 'rfq'">
              <span class="tag" :class="statusTagClass(rec.status)">
                {{ rec.status || '草稿' }}
              </span>
            </td>
            <td>
              <div class="action-btns">
                <button class="btn btn-ghost btn-sm" @click="viewDetail(rec)">查看</button>
                <button
                  v-if="activeTab === 'procure'"
                  class="btn btn-ghost btn-sm"
                  @click="reuse(rec)"
                >
                  复用
                </button>
                <button class="btn btn-ghost btn-sm" @click="deleteRecord(rec)">删除</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getRfqs } from '@/api'

const router = useRouter()

const activeTab = ref<'procure' | 'rfq'>('procure')
const loading = ref(false)
const loadError = ref('')

interface HistoryItem {
  id: string
  time: string
  rawQuery: string
  partNumber?: string
  altCount: number
  supCount: number
  status?: string
}

const records = ref<HistoryItem[]>([])

function statusTagClass(status?: string) {
  const map: Record<string, string> = {
    sent: 'tag-blue',
    quoted: 'tag-yellow',
    closed: 'tag-gray',
    draft: 'tag-gray',
  }
  return map[status || 'draft'] || 'tag-gray'
}

function viewDetail(rec: HistoryItem) {
  // TODO: 跳转到详情页复用 store 状态
  alert(`查看详情: ${rec.id}`)
}

function reuse(_rec: HistoryItem) {
  // 复用寻源：跳回首页填充 query
  router.push('/')
}

function deleteRecord(rec: HistoryItem) {
  if (confirm(`确定删除记录 ${rec.id}?`)) {
    records.value = records.value.filter((r) => r.id !== rec.id)
  }
}

async function fetchRecords() {
  loading.value = true
  loadError.value = ''
  try {
    const res = await getRfqs()
    records.value = (res.data || []).map((r: any) => ({
      id: r.id || r.rfq_id,
      time: r.created_at || '-',
      rawQuery: r.raw_query || '-',
      partNumber: r.parsed_spec?.part_number,
      altCount: (r.alternatives || []).length,
      supCount: 0,
      status: r.status,
    }))
  } catch {
    // 使用模拟数据
    records.value = []
  } finally {
    loading.value = false
  }
}

onMounted(fetchRecords)
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

.time-cell {
  white-space: nowrap;
  font-size: 12px;
  color: var(--color-text-muted);
}

.query-cell {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-btns {
  display: flex;
  gap: 4px;
}
</style>