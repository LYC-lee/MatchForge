<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import {
  adminStats, adminCapabilities, adminGenerate, adminIncremental,
  adminRebuildIndex, adminListTasks, adminTaskFailures, adminCancelTask,
  getCompanies,
  type KbStats, type KbTask,
} from '@/api/kb'

const stats = ref<KbStats | null>(null)
const caps = ref<Record<string, any>>({})
const tasks = ref<KbTask[]>([])
const companies = ref<any[]>([])
const failures = ref<Record<string, any[]>>({})
const loading = ref(false)
const genForce = ref(false)
const genCompanyIds = ref('')
const incCompany = ref<string | number>('')
let pollTimer: any = null

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
    // 加载运行中任务的失败
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

async function startGenerate() {
  let ids: number[] | undefined
  if (genCompanyIds.value.trim()) {
    ids = genCompanyIds.value.split(',').map((x) => parseInt(x.trim())).filter(Boolean)
  }
  await adminGenerate(ids, genForce.value)
  await refresh()
  startPolling()
}

async function startIncremental(companyId: number) {
  await adminIncremental(companyId)
  await refresh()
  startPolling()
}

async function startRebuild() {
  if (!confirm('从 Source of Truth 重建向量索引？')) return
  await adminRebuildIndex(false)
  await refresh()
  startPolling()
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
      <button class="btn-refresh" @click="refresh" :disabled="loading">{{ loading ? '刷新中…' : '刷新' }}</button>
    </header>

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
        <div class="stat"><b>{{ stats.company_count }}</b><span class="muted small">公司总数</span></div>
        <div class="stat ok"><b>{{ stats.companies_ready }}</b><span class="muted small">知识就绪</span></div>
        <div class="stat"><b>{{ stats.manual_count }}</b><span class="muted small">手册(活跃)</span></div>
        <div class="stat"><b>{{ stats.zh_manual_count }}/{{ stats.en_manual_count }}</b><span class="muted small">中/英手册</span></div>
        <div class="stat"><b>{{ stats.product_chunk_count }}</b><span class="muted small">产品切片</span></div>
        <div class="stat"><b>{{ stats.business_chunk_count }}</b><span class="muted small">业务切片</span></div>
        <div class="stat"><b>{{ stats.zh_chunk_count }}/{{ stats.en_chunk_count }}</b><span class="muted small">中/英切片</span></div>
        <div class="stat"><b>{{ stats.product_count }}</b><span class="muted small">结构化产品</span></div>
        <div class="stat"><b>{{ stats.vector_count }}</b><span class="muted small">向量数 ({{ stats.vector_backend }})</span></div>
      </div>
    </section>

    <!-- 操作 -->
    <section class="card">
      <h3>知识生成操作</h3>
      <div class="ops">
        <div class="op">
          <label class="muted small">全量生成 / 增量生成</label>
          <div class="op-row">
            <input v-model="genCompanyIds" placeholder="公司ID逗号分隔, 留空=全部" class="input" />
            <label class="checkbox"><input type="checkbox" v-model="genForce" /> 强制重生成</label>
            <button class="btn-primary" @click="startGenerate">启动生成</button>
          </div>
        </div>
        <div class="op">
          <label class="muted small">单公司增量更新</label>
          <div class="op-row">
            <select v-model="incCompany" class="input">
              <option value="">选择公司…</option>
              <option v-for="c in companies" :key="c.id" :value="c.id">#{{ c.id }} {{ c.name }}</option>
            </select>
            <button class="btn-primary" :disabled="!incCompany" @click="startIncremental(Number(incCompany))">增量更新</button>
          </div>
        </div>
        <div class="op">
          <label class="muted small">向量索引</label>
          <div class="op-row">
            <button class="btn-secondary" @click="startRebuild">从 Source of Truth 重建索引</button>
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
            <span class="muted small">{{ t.progress }}%</span>
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
  </div>
</template>

<style scoped>
.admin-kb { padding: var(--space-5); display: flex; flex-direction: column; gap: var(--space-4); }
.page-head { display: flex; justify-content: space-between; align-items: flex-start; }
.page-head h2 { font-size: var(--font-size-2xl); }
.muted { color: var(--text-tertiary); }
.small { font-size: var(--font-size-xs); }
.card {
  background: var(--bg-1);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: var(--space-4) var(--space-5);
}
.card h3 { font-size: var(--font-size-md); margin-bottom: var(--space-3); }
.cap-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: var(--space-3); }
.cap { display: flex; flex-direction: column; gap: 2px; padding: var(--space-3); background: var(--bg-2); border-radius: var(--radius-md); }
.cap b { color: var(--text-primary); font-size: var(--font-size-sm); }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: var(--space-3); }
.stat { display: flex; flex-direction: column; padding: var(--space-3); background: var(--bg-2); border-radius: var(--radius-md); }
.stat b { font-size: var(--font-size-xl); color: var(--text-primary); }
.stat.ok b { color: var(--success); }
.ops { display: flex; flex-direction: column; gap: var(--space-4); }
.op { display: flex; flex-direction: column; gap: var(--space-2); }
.op-row { display: flex; gap: var(--space-2); align-items: center; flex-wrap: wrap; }
.input {
  background: var(--bg-2);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: 8px 12px;
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  outline: none;
  min-width: 200px;
}
.input:focus { border-color: var(--accent-border); }
.checkbox { display: flex; align-items: center; gap: 4px; font-size: var(--font-size-sm); color: var(--text-secondary); }
.btn-primary {
  padding: 8px 18px; border-radius: var(--radius-md); border: none;
  background: var(--gradient-accent); color: #fff; font-size: var(--font-size-sm);
  font-weight: 600; cursor: pointer;
}
.btn-primary:disabled { opacity: 0.5; }
.btn-secondary {
  padding: 8px 18px; border-radius: var(--radius-md); border: 1px solid var(--accent-border);
  background: var(--accent-soft); color: var(--text-primary); font-size: var(--font-size-sm);
  cursor: pointer;
}
.btn-refresh {
  padding: 7px 16px; border-radius: var(--radius-md); border: 1px solid var(--border-default);
  background: var(--bg-2); color: var(--text-secondary); cursor: pointer; font-size: var(--font-size-sm);
}
.btn-refresh:disabled { opacity: 0.5; }
.btn-cancel { padding: 2px 8px; font-size: var(--font-size-xs); border-radius: var(--radius-sm); border: 1px solid var(--border-default); background: var(--bg-2); color: var(--text-tertiary); cursor: pointer; }
.task-list { display: flex; flex-direction: column; gap: var(--space-3); }
.task { padding: var(--space-3); background: var(--bg-2); border-radius: var(--radius-md); }
.task__head { display: flex; align-items: center; gap: var(--space-3); margin-bottom: 6px; }
.task__type { font-weight: 600; font-size: var(--font-size-sm); color: var(--text-primary); }
.task__status { font-size: var(--font-size-xs); padding: 2px 8px; border-radius: var(--radius-full); }
.s--ok { color: var(--success); background: var(--success-soft); }
.s--warn { color: var(--warning); background: var(--warning-soft); }
.s--err { color: var(--danger); background: var(--danger-soft); }
.s--run { color: var(--accent-hover); background: var(--accent-soft); }
.s--muted { color: var(--text-tertiary); background: var(--bg-3); }
.task__progress { height: 4px; background: var(--bg-3); border-radius: var(--radius-full); overflow: hidden; margin: 6px 0; }
.task__progress-bar { height: 100%; background: var(--gradient-accent); transition: width 0.3s; }
.task__stage { margin-top: 4px; }
.task__failures { margin-top: var(--space-2); padding: var(--space-2); background: var(--danger-soft); border-radius: var(--radius-sm); }
.failure { display: flex; flex-direction: column; font-size: var(--font-size-xs); color: var(--text-secondary); padding: 2px 0; }
.task__summary { margin-top: 6px; word-break: break-all; }
</style>
