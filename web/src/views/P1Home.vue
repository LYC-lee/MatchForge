<template>
  <div class="page-container">
    <!-- 头部 -->
    <header class="home-header">
      <h1 class="logo">MatchForge <span class="logo-sub">智配</span></h1>
      <p class="subtitle">电子元器件 AI 替代料寻源助手</p>
    </header>

    <!-- 输入区 -->
    <section class="search-section card">
      <div class="card-body">
        <div class="input-group">
          <textarea
            v-model="query"
            class="query-input"
            rows="3"
            placeholder="输入型号或描述需求，如 TMK212BJ105KG-T 缺货找替代"
            :disabled="store.isStreaming"
            @keydown.ctrl.enter="handleSubmit"
          />
          <div class="input-actions">
            <div class="example-chips">
              <span class="chip-label">试试：</span>
              <button
                v-for="(ex, i) in examples"
                :key="i"
                class="chip"
                :disabled="store.isStreaming"
                @click="query = ex"
              >
                {{ ex.length > 40 ? ex.slice(0, 40) + '…' : ex }}
              </button>
            </div>
            <div class="action-buttons">
              <button class="btn btn-ghost" :disabled="!query || store.isStreaming" @click="query = ''">
                清空
              </button>
              <button
                class="btn btn-primary"
                :disabled="!query.trim() || store.isStreaming"
                @click="handleSubmit"
              >
                <span v-if="store.isStreaming" class="loading-spinner" />
                {{ store.isStreaming ? '寻源中…' : '开始寻源' }}
              </button>
            </div>
          </div>
        </div>
        <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
      </div>
    </section>

    <!-- 进度 -->
    <section v-if="store.isStreaming" class="progress-section card">
      <div class="card-body">
        <div class="progress-bar">
          <div class="progress-bar-fill" :style="{ width: progressPercent + '%' }" />
        </div>
        <p class="progress-text">
          {{ currentProgressText }}
        </p>
      </div>
    </section>

    <!-- 历史快捷入口 -->
    <section class="history-section">
      <router-link to="/history" class="history-link">
        查看历史寻源记录 →
      </router-link>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useProcureStore } from '@/stores/procure'
import { procureStream } from '@/api'

const router = useRouter()
const store = useProcureStore()

const query = ref('')
const errorMsg = ref('')

const examples = [
  'TMK212BJ105KG-T 缺货，找替代',
  '0805 10uF X7R 50V MLCC，月用量50万，要国巨或华新科',
  '寻找 GRM188R61A106KE69D 的替代料，交期2周',
]

const currentProgressText = computed(() => {
  if (!store.progress.length) return '正在解析需求…'
  const last = store.progress[store.progress.length - 1]
  const labels: Record<string, string> = {
    parse: '正在识别型号与参数…',
    normalize: '正在标准化规格…',
    alternatives: '正在查询替代料…',
    match: '正在匹配供应商…',
    gen_rfq: '正在生成询价单…',
    grade: '正在分级线索…',
  }
  return labels[last.agent] || '处理中…'
})

const progressPercent = computed(() => {
  const agents = ['parse', 'normalize', 'alternatives', 'match', 'gen_rfq', 'grade']
  const done = store.progress.filter((p) => p.status === 'done').length
  return Math.round((done / agents.length) * 100)
})

function handleSubmit() {
  if (!query.value.trim() || store.isStreaming) return
  errorMsg.value = ''

  store.reset()
  store.rawQuery = query.value
  store.isStreaming = true

  procureStream(
    query.value,
    store.threadId,
    (event, data) => {
      switch (event) {
        case 'start':
          store.threadId = data.thread_id
          if (data.rfq_id) store.rfqId = data.rfq_id
          break
        case 'progress':
          store.progress.push({ agent: data.agent, status: data.status })
          // 增量更新各阶段结果
          if (data.result) {
            if (data.agent === 'parse') store.parsedSpec = data.result
            if (data.agent === 'normalize') store.normalizedSpec = data.result
            if (data.agent === 'alternatives') store.alternatives = data.result
            if (data.agent === 'match') store.matchedSuppliers = data.result
            if (data.agent === 'gen_rfq') store.rfqDoc = data.result
            if (data.agent === 'grade') store.leadGrade = data.result
          }
          break
        case 'error':
          store.errors.push(data.message)
          break
        case 'result':
          store.applyState(data)
          break
        case 'end':
          store.isStreaming = false
          // 跳转到规格确认页
          router.push('/spec-confirm')
          break
      }
    },
    (err) => {
      errorMsg.value = `请求失败: ${err.message}`
      store.isStreaming = false
    }
  )
}
</script>

<style scoped>
.home-header {
  text-align: center;
  margin-bottom: 32px;
  padding-top: 40px;
}

.logo {
  font-size: 32px;
  font-weight: 700;
  color: var(--color-text);
}

.logo-sub {
  color: var(--color-primary);
  font-weight: 400;
}

.subtitle {
  margin-top: 8px;
  color: var(--color-text-secondary);
  font-size: 16px;
}

.search-section {
  margin-bottom: 20px;
}

.query-input {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 15px;
  font-family: inherit;
  line-height: 1.6;
  resize: vertical;
  color: var(--color-text);
}

.query-input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-light);
}

.query-input:disabled {
  background: #f8fafc;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.example-chips {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  flex: 1;
}

.chip-label {
  font-size: 12px;
  color: var(--color-text-muted);
}

.chip {
  padding: 4px 10px;
  border: 1px solid var(--color-border);
  border-radius: 16px;
  background: var(--color-surface);
  font-size: 12px;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}

.chip:hover:not(:disabled) {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.action-buttons {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.error-msg {
  margin-top: 8px;
  color: var(--color-danger);
  font-size: 13px;
}

.progress-section {
  margin-bottom: 20px;
}

.progress-text {
  margin-top: 8px;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.history-section {
  text-align: center;
  margin-top: 24px;
}

.history-link {
  font-size: 14px;
  color: var(--color-text-secondary);
}
</style>