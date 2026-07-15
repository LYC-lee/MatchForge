<template>
  <div class="page-container">
    <!-- 步骤指示器 -->
    <div class="steps">
      <div class="step done">1. 输入需求</div>
      <div class="step done">2. 规格确认</div>
      <div class="step active">3. 替代料</div>
      <div class="step">4. 供应商</div>
      <div class="step">5. 询价单</div>
    </div>

    <h2 class="page-title">替代料推荐</h2>

    <!-- 原型号信息卡 -->
    <div class="card original-card">
      <div class="card-header">原型号</div>
      <div class="card-body">
        <div class="original-specs">
          <span class="spec-item" v-for="(v, k) in store.parsedSpec" :key="k">
            <span class="spec-key">{{ k }}:</span> {{ v }}
          </span>
        </div>
      </div>
    </div>

    <!-- 加载 -->
    <div v-if="loading" class="card">
      <div class="card-body empty-state">
        <div class="loading-spinner" style="margin: 0 auto 12px" />
        <p>正在查询替代料…</p>
      </div>
    </div>

    <!-- 错误 -->
    <div v-else-if="loadError" class="card">
      <div class="card-body error-state">
        <p>{{ loadError }}</p>
        <button class="btn btn-primary" @click="fetchAlternatives">重试</button>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="store.alternatives.length === 0" class="card">
      <div class="card-body empty-state">
        <p class="icon">🔍</p>
        <p><strong>暂无替代建议</strong></p>
        <p>建议联系原厂或工程师确认</p>
      </div>
    </div>

    <!-- 替代列表 -->
    <div v-else>
      <!-- 顶部提示 -->
      <div v-if="hasUnverified" class="alert alert-warning" style="margin-bottom: 16px">
        ⚠️ 部分替代料未经人工核验，标记为"仅供参考"，需工程师确认后方可使用。
      </div>

      <div
        v-for="(alt, i) in sortedAlternatives"
        :key="alt.part"
        class="card alt-card"
        :class="{ 'alt-low-conf': alt.level === 'L5' || (!alt.verified && alt.confidence < 0.7) }"
      >
        <div class="card-body">
          <!-- 替代料头部 -->
          <div class="alt-header">
            <div class="alt-title">
              <span class="alt-part">{{ alt.part }}</span>
              <span class="alt-brand">{{ alt.brand }}</span>
              <span class="tag" :class="levelTagClass(alt.level)">{{ levelLabel(alt.level) }}</span>
              <span v-if="alt.verified" class="tag tag-green">已核验</span>
              <span v-else class="tag tag-gray">待核验</span>
            </div>
            <div class="alt-confidence">
              置信度: {{ (alt.confidence * 100).toFixed(0) }}%
            </div>
          </div>

          <!-- 参数差异表 -->
          <div v-if="alt.diff_items && alt.diff_items.length" class="diff-table-wrap">
            <table class="table diff-table">
              <thead>
                <tr>
                  <th>参数</th>
                  <th>原型号</th>
                  <th>替代型号</th>
                  <th>差异</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="d in alt.diff_items"
                  :key="d.param"
                  :class="{
                    'row-match': d.type === 'match',
                    'row-diff': d.type === 'diff',
                    'row-risk': d.type === 'risk',
                  }"
                >
                  <td>{{ d.param }}</td>
                  <td>{{ d.original }}</td>
                  <td>{{ d.alternative }}</td>
                  <td>
                    <span v-if="d.type === 'match'" class="tag tag-green">一致</span>
                    <span v-else-if="d.type === 'diff'" class="tag tag-yellow">差异</span>
                    <span v-else class="tag tag-red">⚠ 风险</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- 推荐依据 -->
          <div class="alt-footer">
            <div class="alt-reason">
              <strong>推荐依据：</strong>{{ alt.reason || '参数匹配' }}
            </div>
            <div class="alt-source">
              <strong>来源：</strong>{{ alt.source }}
              <span v-if="alt.updated_at" class="source-time">
                (更新于 {{ alt.updated_at }})
              </span>
            </div>
          </div>

          <!-- 操作 -->
          <div class="alt-actions">
            <button class="btn btn-ghost btn-sm" @click="markUseless(alt, i)">标记无用</button>
            <button
              class="btn btn-primary"
              :class="{ 'btn-sm': true }"
              @click="selectAndGo(alt)"
            >
              查看供应商
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 返回 -->
    <div style="margin-top: 16px">
      <button class="btn btn-ghost" @click="$router.push('/spec-confirm')">← 返回修改规格</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useProcureStore } from '@/stores/procure'
import { getAlternatives } from '@/api'
import type { Alternative } from '@/api'

const router = useRouter()
const store = useProcureStore()

const loading = ref(false)
const loadError = ref('')

const hasUnverified = computed(() =>
  store.alternatives.some((a) => !a.verified)
)

// 排序: L1 优先, 高置信在前
const sortedAlternatives = computed(() => {
  const levelOrder: Record<string, number> = { L1: 0, L2: 1, L3: 2, L4: 3, L5: 4 }
  return [...store.alternatives].sort((a, b) => {
    const la = levelOrder[a.level || 'L5'] ?? 5
    const lb = levelOrder[b.level || 'L5'] ?? 5
    if (la !== lb) return la - lb
    return b.confidence - a.confidence
  })
})

function levelLabel(level?: string) {
  const map: Record<string, string> = {
    L1: '完全等效',
    L2: '向上兼容',
    L3: '需工程确认',
    L4: '封装不兼容',
    L5: '仅供参考',
  }
  return map[level || 'L5'] || '未知'
}

function levelTagClass(level?: string) {
  const map: Record<string, string> = {
    L1: 'tag-green',
    L2: 'tag-green',
    L3: 'tag-yellow',
    L4: 'tag-red',
    L5: 'tag-gray',
  }
  return map[level || 'L5'] || 'tag-gray'
}

function selectAndGo(alt: Alternative) {
  store.selectedAlternative = alt
  router.push('/supplier-match')
}

function markUseless(_alt: Alternative, _i: number) {
  // TODO: 上报用户反馈
  alert('已标记"无用"，系统将优化推荐')
}

async function fetchAlternatives() {
  if (!store.parsedSpec) return
  loading.value = true
  loadError.value = ''
  try {
    const res = await getAlternatives(store.parsedSpec)
    store.alternatives = res.data.alternatives || []
  } catch (e: any) {
    loadError.value = `替代料查询失败: ${e.message}`
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (!store.parsedSpec) {
    router.push('/')
    return
  }
  if (store.alternatives.length === 0) {
    fetchAlternatives()
  }
})
</script>

<style scoped>
.page-title {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 16px;
}

.original-card {
  margin-bottom: 20px;
}

.original-specs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
}

.spec-item {
  font-size: 13px;
}

.spec-key {
  color: var(--color-text-secondary);
}

.alt-card {
  margin-bottom: 16px;
}

.alt-card.alt-low-conf {
  opacity: 0.7;
  border-left: 3px solid var(--color-warning);
}

.alt-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 8px;
}

.alt-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.alt-part {
  font-weight: 600;
  font-size: 15px;
  font-family: 'SF Mono', 'Cascadia Code', monospace;
}

.alt-brand {
  color: var(--color-text-secondary);
  font-size: 13px;
}

.alt-confidence {
  font-size: 12px;
  color: var(--color-text-muted);
}

.diff-table-wrap {
  overflow-x: auto;
  margin-bottom: 12px;
}

.diff-table {
  font-size: 12px;
}

.diff-table th {
  font-size: 12px;
}

.row-match {
  background: #f8fdf8;
}

.row-diff {
  background: #fffdf7;
}

.row-risk {
  background: #fff7f7;
}

.alt-footer {
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.alt-source {
  margin-top: 4px;
  font-size: 12px;
}

.source-time {
  color: var(--color-text-muted);
}

.alt-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border);
}
</style>