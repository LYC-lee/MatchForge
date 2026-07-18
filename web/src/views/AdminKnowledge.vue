<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import {
  adminStats, adminCapabilities, adminGenerate, adminIncremental,
  adminRebuildIndex, adminListTasks, adminTaskFailures, adminCancelTask,
  getCompanies,
  type KbStats, type KbTask,
} from '@/api/kb'
import AppButton from '@/components/ui/AppButton.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'

const stats = ref<KbStats | null>(null)
const caps = ref<Record<string, any>>({})
const tasks = ref<KbTask[]>([])
const companies = ref<any[]>([])
const failures = ref<Record<string, any[]>>({})
const loading = ref(false)
const genForce = ref(false)
/** 目标公司选择（替代裸 ID 输入：从已加载 companies 勾选） */
const genCompanyIds = ref<Set<number>>(new Set())
const incCompany = ref<string | number>('')
let pollTimer: any = null

// 操作确认 + submitting
const showGenConfirm = ref(false)
const showRebuildConfirm = ref(false)
const generating = ref(false)
const rebuilding = ref(false)
const actionError = ref<string | null>(null)

async function refresh() {
  loading.value = true
  try {
    const [s, c, t, comps] = await Promise.all([
      adminStats(), adminCapabilities(), adminListTasks(), getCompanies(),
    ])
    stats.value = s.data
    caps.value = c.data
    tasks.value = t.data.items
    companies.value = comps.data.items
    for (const tk of tasks.value) {
      if (['running', 'partially_completed', 'failed'].includes(tk.status)) {
        await loadFailures(tk.task_id)
      }
    }
  } catch (e: any) {
    console.error('refresh failed', e)
  } finally {
    loading.value = false
  }
}

async function loadFailures(taskId: string) {
  try {
    const r = await adminTaskFailures(taskId)
    failures.value[taskId] = r.data.items
  } catch { /* ignore */ }
}

function toggleGenCompany(id: number) {
  const s = new Set(genCompanyIds.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  genCompanyIds.value = s
}

const genTargetDescription = computed(() => {
  if (genCompanyIds.value.size === 0) return '未选择任何公司，将对全部公司执行'
  const names = companies.value
    .filter((c) => genCompanyIds.value.has(c.id))
    .map((c) => `#${c.id} ${c.name}`)
    .join('、')
  return `目标：${names}`
})

async function startGenerate() {
  // 留空 + 强制重生成 是高风险一键操作，需二次确认
  if (genCompanyIds.value.size === 0 && genForce.value) {
    showGenConfirm.value = true
    return
  }
  doGenerate()
}

async function doGenerate() {
  showGenConfirm.value = false
  generating.value = true
  actionError.value = null
  try {
    const ids = genCompanyIds.value.size > 0 ? [...genCompanyIds.value] : undefined
    await adminGenerate(ids, genForce.value)
    await refresh()
    startPolling()
  } catch (e: any) {
    actionError.value = e?.message || '启动生成失败'
  } finally {
    generating.value = false
  }
}

async function startIncremental(companyId: number) {
  try {
    await adminIncremental(companyId)
    await refresh()
    startPolling()
  } catch (e: any) {
    actionError.value = e?.message || '增量更新失败'
  }
}

async function doRebuild() {
  showRebuildConfirm.value = false
  rebuilding.value = true
  actionError.value = null
  try {
    await adminRebuildIndex(false)
    await refresh()
    startPolling()
  } catch (e: any) {
    actionError.value = e?.message || '重建索引失败'
  } finally {
    rebuilding.value = false
  }
}

async function cancelTask(taskId: string) {
  await adminCancelTask(taskId)
  await refresh()
}

function startPolling() {
  if (pollTimer) return
  pollTimer = setInterval(async () => {
    await refresh()
    const running = tasks.value.some((t) => t.status === 'running' || t.status === 'pending')
    if (!running) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }, 3000)
}

function statusColor(s: string) {
  return {
    completed: 'ok', partially_completed: 'warn', failed: 'err',
    running: 'run', pending: 'muted', cancelled: 'muted',
  }[s] || 'muted'
}

onMounted(refresh)
onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })
</script>

<template>
  <div class="admin-kb">
    <header class="page-head">
      <div>
        <h2>知识库管理</h2>
        <p class="muted small">企业双语私域知识库 · Company-Level RAG</p>
      </div>
      <AppButton variant="secondary" size="sm" :loading="loading" @click="refresh">刷新</AppButton>
    </header>

    <div v-if="actionError" class="notice-bar" role="alert">{{ actionError }}</div>

    <!-- 运行时能力 -->
    <section class="card">
      <h3>运行时后端</h3>
      <div class="cap-grid">
        <div class="cap"><span class="muted small">LLM</span><b>{{ caps.llm }}</b><span class="muted small">{{ caps.llm_model }}</span></div>
        <div class="cap"><span class="muted small">Embedding</span><b>{{ caps.embedding }}</b><span class="muted small">{{ caps.embedding_dim }}d</span></div>
        <div class="cap"><span class="muted small">向量库</span><b>{{ caps.vector_store }}</b></div>
        <div class="cap"><span class="muted small">数据库</span><b>{{ caps.database }}</b></div>
        <div class="cap"><span class="muted small">Demo 模式</span><b>{{ caps.demo_mode ? 'ON' : 'OFF' }}</b></div>
      </div>
    </section>

    <!-- 统计 -->
    <section class="card" v-if="stats">
      <h3>知识库统计</h3>
      <div class="stat-grid">
        <div class="stat"><b class="num">{{ stats.company_count }}</b><span class="muted small">公司总数</span></div>
        <div class="stat ok"><b class="num">{{ stats.companies_ready }}</b><span class="muted small">知识就绪</span></div>
        <div class="stat"><b class="num">{{ stats.manual_count }}</b><span class="muted small">手册(活跃)</span></div>
        <div class="stat"><b class="num">{{ stats.zh_manual_count }}/{{ stats.en_manual_count }}</b><span class="muted small">中/英手册</span></div>
        <div class="stat"><b class="num">{{ stats.product_chunk_count }}</b><span class="muted small">产品切片</span></div>
        <div class="stat"><b class="num">{{ stats.business_chunk_count }}</b><span class="muted small">业务切片</span></div>
        <div class="stat"><b class="num">{{ stats.zh_chunk_count }}/{{ stats.en_chunk_count }}</b><span class="muted small">中/英切片</span></div>
        <div class="stat"><b class="num">{{ stats.product_count }}</b><span class="muted small">结构化产品</span></div>
        <div class="stat"><b class="num">{{ stats.vector_count }}</b><span class="muted small">向量数 ({{ stats.vector_backend }})</span></div>
      </div>
    </section>

    <!-- 操作 -->
    <section class="card">
      <h3>知识生成操作</h3>
      <div class="ops">
        <div class="op">
          <label class="muted small">全量生成 / 增量生成</label>
          <div class="company-pick">
            <span class="muted small">{{ genTargetDescription }}</span>
            <div class="company-list">
              <label
                v-for="c in companies"
                :key="c.id"
                class="company-item"
                :class="{ 'company-item--on': genCompanyIds.has(c.id) }"
              >
                <input type="checkbox" :checked="genCompanyIds.has(c.id)" @change="toggleGenCompany(c.id)">
                <span>#{{ c.id }} {{ c.name }}</span>
              </label>
              <span v-if="!companies.length" class="muted small">暂无公司数据</span>
            </div>
          </div>
          <div class="op-row">
            <label class="checkbox"><input type="checkbox" v-model="genForce"> 强制重生成</label>
            <AppButton :loading="generating" @click="startGenerate">启动生成</AppButton>
          </div>
        </div>
        <div class="op">
          <label class="muted small">单公司增量更新</label>
          <div class="op-row">
            <select v-model="incCompany" class="input">
              <option value="">选择公司…</option>
              <option v-for="c in companies" :key="c.id" :value="c.id">#{{ c.id }} {{ c.name }}</option>
            </select>
            <AppButton variant="secondary" :disabled="!incCompany" @click="startIncremental(Number(incCompany))">增量更新</AppButton>
          </div>
        </div>
        <div class="op">
          <label class="muted small">向量索引</label>
          <div class="op-row">
            <AppButton variant="danger" :loading="rebuilding" @click="showRebuildConfirm = true">从 Source of Truth 重建索引</AppButton>
          </div>
        </div>
      </div>
    </section>

    <!-- 任务列表 -->
    <section class="card">
      <h3>任务列表 <span class="muted small">({{ tasks.length }})</span></h3>
      <div class="task-list">
        <div v-for="t in tasks" :key="t.task_id" class="task">
          <div class="task__head">
            <span class="task__type">{{ t.task_type }}</span>
            <span class="task__status" :class="`s--${statusColor(t.status)}`">{{ t.status }}</span>
            <span class="muted small">{{ t.company_id ? `公司#${t.company_id}` : '全部' }}</span>
            <span class="muted small num">{{ t.progress }}%</span>
            <button v-if="t.status === 'running' || t.status === 'pending'" class="btn-cancel" @click="cancelTask(t.task_id)">取消</button>
          </div>
          <div class="task__stage muted small" v-if="t.current_stage">{{ t.current_stage }}</div>
          <div class="task__progress"><div class="task__progress-bar" :style="{ width: t.progress + '%' }" /></div>
          <div class="task__stage muted small" v-if="t.error_message">错误: {{ t.error_message }}</div>
          <div v-if="failures[t.task_id]?.length" class="task__failures">
            <div class="muted small">失败记录 ({{ failures[t.task_id].length }}):</div>
            <div v-for="(f, i) in failures[t.task_id].slice(0, 5)" :key="i" class="failure">
              <span>#{{ f.company_id }} {{ f.company_name }} · {{ f.stage }}</span>
              <span class="muted small">{{ f.error?.slice(0, 80) }}</span>
            </div>
          </div>
          <div v-if="t.result_summary" class="task__summary muted small">
            {{ JSON.stringify(t.result_summary).slice(0, 200) }}
          </div>
        </div>
        <div v-if="!tasks.length" class="muted small">暂无任务</div>
      </div>
    </section>

    <ConfirmDialog
      v-model:open="showGenConfirm"
      title="确认对全部公司强制重生成？"
      description="未选择公司且开启了强制重生成，将对全部公司重新生成知识库，耗时较长且会覆盖现有数据。"
      confirm-text="确认执行"
      danger
      :loading="generating"
      @confirm="doGenerate"
    />
    <ConfirmDialog
      v-model:open="showRebuildConfirm"
      title="重建向量索引？"
      description="将从 Source of Truth 重新构建向量索引，期间检索不可用。"
      confirm-text="重建"
      danger
      :loading="rebuilding"
      @confirm="doRebuild"
    />
  </div>
</template>

<style scoped>
.admin-kb { padding: var(--space-5); display: flex; flex-direction: column; gap: var(--space-4); }
.page-head { display: flex; justify-content: space-between; align-items: flex-start; }
.page-head h2 { font-size: var(--font-size-2xl); line-height: var(--leading-2xl); }
.muted { color: var(--text-tertiary); }
.small { font-size: var(--font-size-xs); line-height: var(--leading-xs); }
.notice-bar { padding: var(--space-3) var(--space-4); border-radius: var(--radius-md); border: 1px solid var(--danger-border); background: var(--danger-soft); color: var(--danger); font-size: var(--font-size-sm); line-height: var(--leading-sm); }
.card {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: var(--space-4) var(--space-5);
}
.card h3 { font-size: var(--font-size-md); line-height: var(--leading-md); margin-bottom: var(--space-3); }
.cap-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: var(--space-3); }
.cap { display: flex; flex-direction: column; gap: var(--space-1); padding: var(--space-3); background: var(--bg-subtle); border-radius: var(--radius-md); }
.cap b { color: var(--text-primary); font-size: var(--font-size-sm); line-height: var(--leading-sm); }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: var(--space-3); }
.stat { display: flex; flex-direction: column; padding: var(--space-3); background: var(--bg-subtle); border-radius: var(--radius-md); }
.stat b { font-size: var(--font-size-xl); line-height: var(--leading-xl); color: var(--text-primary); font-family: var(--font-mono); }
.stat.ok b { color: var(--success); }
.ops { display: flex; flex-direction: column; gap: var(--space-4); }
.op { display: flex; flex-direction: column; gap: var(--space-2); }
.op-row { display: flex; gap: var(--space-2); align-items: center; flex-wrap: wrap; }
.input {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-3);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  outline: none;
  min-width: 200px;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.input:focus { border-color: var(--accent-border); box-shadow: 0 0 0 3px var(--accent-soft); }
.checkbox { display: flex; align-items: center; gap: var(--space-1); font-size: var(--font-size-sm); line-height: var(--leading-sm); color: var(--text-secondary); }
.btn-cancel { padding: var(--space-1) var(--space-2); font-size: var(--font-size-xs); line-height: var(--leading-xs); border-radius: var(--radius-sm); border: 1px solid var(--border-default); background: var(--bg-subtle); color: var(--text-tertiary); cursor: pointer; }

/* 按公司选择 */
.company-pick { display: flex; flex-direction: column; gap: var(--space-2); }
.company-list { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.company-item {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-full);
  background: var(--bg-surface);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  color: var(--text-secondary);
  cursor: pointer;
  transition: border-color var(--transition-fast), background-color var(--transition-fast);
}
.company-item input { accent-color: var(--accent); }
.company-item--on { border-color: var(--accent-border); background: var(--accent-soft); color: var(--accent-text); }

.task-list { display: flex; flex-direction: column; gap: var(--space-3); }
.task { padding: var(--space-3); background: var(--bg-subtle); border-radius: var(--radius-md); }
.task__head { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-1); }
.task__type { font-weight: 600; font-size: var(--font-size-sm); line-height: var(--leading-sm); color: var(--text-primary); }
.task__status { font-size: var(--font-size-xs); line-height: var(--leading-xs); padding: var(--space-1) var(--space-2); border-radius: var(--radius-full); }
.s--ok { color: var(--success); background: var(--success-soft); }
.s--warn { color: var(--warning); background: var(--warning-soft); }
.s--err { color: var(--danger); background: var(--danger-soft); }
.s--run { color: var(--accent-text); background: var(--accent-soft); }
.s--muted { color: var(--text-tertiary); background: var(--bg-subtle); }
.task__progress { height: var(--space-1); background: var(--bg-subtle); border-radius: var(--radius-full); overflow: hidden; margin: var(--space-1) 0; }
.task__progress-bar { height: 100%; background: var(--accent); transition: width 0.3s; }
.task__stage { margin-top: var(--space-1); }
.task__failures { margin-top: var(--space-2); padding: var(--space-2); background: var(--danger-soft); border: 1px solid var(--danger-border); border-radius: var(--radius-sm); }
.failure { display: flex; flex-direction: column; font-size: var(--font-size-xs); line-height: var(--leading-xs); color: var(--text-secondary); padding: var(--space-1) 0; }
.task__summary { margin-top: var(--space-1); word-break: break-all; }
</style>
