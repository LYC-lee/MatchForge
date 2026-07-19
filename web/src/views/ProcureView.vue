<script setup lang="ts">
import { computed, ref, watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useProcureStore } from '@/stores/procure'
import { useAuthStore } from '@/stores/auth'
import { saveToLocal } from '@/composables/useHistory'
import type { SpecField } from '@/types/procure'
import Card from '@/components/ui/Card.vue'
import AppButton from '@/components/ui/AppButton.vue'
import Tag from '@/components/ui/Tag.vue'
import StepNav from '@/components/layout/StepNav.vue'
import AgentTimeline from '@/components/procure/AgentTimeline.vue'
import SpecConfirm from '@/components/procure/SpecConfirm.vue'
import AlternativesList from '@/components/procure/AlternativesList.vue'
import SuppliersMatch from '@/components/procure/SuppliersMatch.vue'
import RfqEditor from '@/components/procure/RfqEditor.vue'

const router = useRouter()
const route = useRoute()
const store = useProcureStore()
const auth = useAuthStore()
const isDemo = computed(() => !!auth.user?.is_demo)
const {
  threadId,
  rawQuery,
  phase,
  agents,
  parsedSpec,
  normalizedSpec,
  alternatives,
  matchedSuppliers,
  selectedSupplierIds,
  rfqDoc,
  rfqId,
  rfqSent,
  persistedRfqNumber,
  rfqSending,
  rfqSendError,
  leadGrade,
  errors,
  isVague,
  streamProgress,
  matchError,
} = storeToRefs(store)

// 历史会话加载状态
const sessionLoading = ref(false)
const sessionNotFound = ref(false)

// 如果路由带 thread_id（从历史记录进入），加载会话
onMounted(async () => {
  const id = route.params.id as string | undefined
  if (id) {
    sessionLoading.value = true
    const ok = await store.loadFromSession(id)
    sessionLoading.value = false
    if (!ok) {
      sessionNotFound.value = true
    }
  }
})

const originalPart = computed(
  () => normalizedSpec.value?.['型号']?.value || parsedSpec.value?.['型号']?.value || '',
)
const originalBrand = computed(
  () => normalizedSpec.value?.['品牌']?.value || parsedSpec.value?.['品牌']?.value || '',
)
const genRfqRunning = computed(
  () => agents.value.find((a) => a.name === 'gen_rfq')?.status === 'running',
)
const matchRunning = computed(
  () => agents.value.find((a) => a.name === 'match')?.status === 'running',
)

const showSpec = computed(
  () => !!normalizedSpec.value && phase.value !== 'idle' && phase.value !== 'spec',
)
const specForConfirm = computed(() => normalizedSpec.value as Record<string, SpecField>)
const showAlternatives = computed(() => alternatives.value.length > 0)
const showSuppliers = computed(
  () => matchedSuppliers.value.length > 0 || matchRunning.value,
)
const showRfq = computed(() => rfqDoc.value.length > 0 || genRfqRunning.value)

const gradeType = computed(() => {
  const g = leadGrade.value?.grade
  if (g === 'A' || g === 'B') return 'success'
  if (g === 'C') return 'warning'
  return 'danger'
})

// 寻源完成时保存到 localStorage 作为降级备份
watch(phase, (p) => {
  if (p === 'done' && !isVague.value) {
    saveToLocal({
      id: threadId.value,
      thread_id: threadId.value,
      raw_query: rawQuery.value,
      created_at: new Date().toISOString(),
      rfq_sent: rfqSent.value,
      state: {
        thread_id: threadId.value,
        raw_query: rawQuery.value,
        parsed_spec: parsedSpec.value,
        normalized_spec: normalizedSpec.value,
        alternatives: alternatives.value,
        matched_suppliers: matchedSuppliers.value,
        rfq_doc: rfqDoc.value,
        rfq_id: rfqId.value,
        lead_grade: leadGrade.value,
        errors: errors.value,
      },
    })
    // 触发历史侧边栏刷新
    store.historyVersion++
  }
})

function onGenerateRfq() {
  document.getElementById('rfq-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function newProcure() {
  store.reset()
  router.push('/chat')
}
</script>

<template>
  <div class="procure">
    <div class="procure__topbar">
      <div class="procure__topbar-inner">
        <button class="procure__back" @click="newProcure">← 新寻源</button>
        <div class="procure__query">
          <span class="procure__query-label">需求</span>
          <span class="procure__query-text">{{ rawQuery }}</span>
        </div>
        <div class="procure__steps">
          <StepNav :agents="agents" />
        </div>
      </div>
    </div>

    <div class="procure__body">
      <!-- 加载历史会话中 -->
      <div v-if="sessionLoading" class="procure__session-loading">
        <span class="history__spinner" />
        <span>加载会话中…</span>
      </div>

      <!-- 会话不存在 -->
      <div v-else-if="sessionNotFound" class="procure__vague" style="padding-top: 60px;">
        <div class="procure__vague-icon">⊘</div>
        <p class="procure__vague-title">会话不存在或已过期</p>
        <p class="procure__vague-desc">该会话可能已被删除，或后端存储服务暂时不可用。</p>
        <AppButton @click="router.push('/chat')">返回寻源</AppButton>
      </div>

      <template v-else>
      <Card v-if="isVague" elevated>
        <template #header><h3>无法完成寻源</h3></template>
        <div class="procure__vague">
          <div class="procure__vague-icon">⊘</div>
          <p class="procure__vague-title">暂无安全替代建议</p>
          <p class="procure__vague-desc">
            {{ errors[0] || '需求信息不足，无法安全推荐替代料。' }}
          </p>
          <AppButton @click="newProcure">返回补充需求</AppButton>
        </div>
      </Card>

      <template v-else>
        <div class="procure__grid">
          <section class="procure__main">
            <!-- 寻源进度 -->
            <Card title="寻源进度" subtitle="6 个智能体阶段实时推进">
              <AgentTimeline
                :agents="agents"
                :alternatives-count="alternatives.length"
                :suppliers-count="matchedSuppliers.length"
              />
            </Card>

            <!-- 规格确认 -->
            <Card
              v-if="showSpec"
              title="规格确认"
              :subtitle="
                phase === 'gating'
                  ? '请核对解析结果，缺失/低置信字段已标黄'
                  : '已确认规格'
              "
            >
              <SpecConfirm
                :spec="specForConfirm"
                :gating="phase === 'gating'"
                @confirm="store.confirmSpec"
              />
            </Card>

            <!-- 替代料推荐 -->
            <Card
              v-if="showAlternatives"
              title="替代料推荐"
              subtitle="基于知识图谱与规格交叉比对"
            >
              <AlternativesList
                :alternatives="alternatives"
                :original-part="originalPart"
                :original-brand="originalBrand"
              />
            </Card>

            <!-- 供应商匹配 -->
            <Card
              v-if="showSuppliers"
              title="供应商匹配"
              subtitle="供应能力匹配，非实时库存承诺"
            >
              <SuppliersMatch
                :suppliers="matchedSuppliers"
                :selected-ids="selectedSupplierIds"
                :streaming="matchRunning"
                :stream-progress="streamProgress"
                :error="matchError"
                @toggle="store.toggleSupplier"
                @select-all="store.selectAllSuppliers"
                @deselect-all="store.deselectAllSuppliers"
                @generate="onGenerateRfq"
                @retry="store.retryMatch"
              />
            </Card>

            <!-- 询价单 -->
            <Card
              v-if="showRfq"
              id="rfq-section"
              title="询价单 (RFQ)"
              subtitle="AI 生成，可编辑"
            >
              <RfqEditor
                :rfq-doc="rfqDoc"
                :rfq-id="rfqId"
                :spec="normalizedSpec"
                :alternatives="alternatives"
                :suppliers="matchedSuppliers"
                :selected-supplier-ids="selectedSupplierIds"
                :sent="rfqSent"
                :streaming="genRfqRunning"
                :persisted-rfq-number="persistedRfqNumber"
                :sending="rfqSending"
                :send-error="rfqSendError"
                :is-demo="isDemo"
                @update="store.setRfqDoc"
                @sent="store.sendRfqToBackend"
                @regenerate="store.regenerateRfq"
              />

              <!-- 落库成功提示 + RFQ 详情/报价对比入口 (正式模式) -->
              <div v-if="!isDemo && rfqSent && persistedRfqNumber" class="procure__rfq-persisted">
                <span class="procure__rfq-persisted-icon">✓</span>
                <span>已创建真实 RFQ <b class="mono">{{ persistedRfqNumber }}</b>，供应商线索已发送。</span>
                <AppButton
                  variant="ghost"
                  size="sm"
                  @click="router.push('/shortage-procurement')"
                >
                  查看 RFQ 与报价对比 →
                </AppButton>
              </div>
            </Card>

            <!-- 线索分级 -->
            <Card v-if="leadGrade" title="线索分级" subtitle="对该询价线索的质量评估">
              <div class="procure__grade">
                <div class="procure__grade-main">
                  <span
                    class="procure__grade-letter"
                    :class="`grade-${leadGrade.grade}`"
                  >
                    {{ leadGrade.grade }}
                  </span>
                  <span class="procure__grade-score">{{ leadGrade.score }} 分</span>
                  <Tag :type="gradeType" :value="`${leadGrade.grade} 级线索`" />
                </div>
                <ul class="procure__grade-reasons">
                  <li v-for="(r, i) in leadGrade.reasons" :key="i">{{ r }}</li>
                </ul>
              </div>
            </Card>

            <!-- 完成 -->
            <div v-if="phase === 'done'" class="procure__done">
              <AppButton variant="primary" size="lg" @click="newProcure">
                开始新的寻源
              </AppButton>
            </div>
          </section>

          <!-- 侧边栏 -->
          <aside class="procure__aside">
            <div class="aside-card">
              <span class="aside-card__label">Thread</span>
              <b>{{ threadId || '启动中' }}</b>
              <p>{{ rawQuery }}</p>
            </div>
            <div class="aside-card">
              <span class="aside-card__label">结果摘要</span>
              <div class="aside-metric">
                <span>替代料</span><b>{{ alternatives.length }}</b>
              </div>
              <div class="aside-metric">
                <span>供应商</span><b>{{ matchedSuppliers.length }}</b>
              </div>
              <div class="aside-metric">
                <span>已选供应商</span><b>{{ selectedSupplierIds.size }}</b>
              </div>
              <div class="aside-metric">
                <span>RFQ 状态</span>
                <b :class="rfqSent ? 'aside-metric--ok' : ''">
                  {{ rfqSent ? '已发送' : rfqDoc ? '已生成' : '待生成' }}
                </b>
              </div>
            </div>
            <div class="aside-card aside-card--muted">
              <span class="aside-card__label">扩展预留</span>
              <p>
                运营审核、供应商入驻、报价对比和真实库存确认可在这里继续扩展。
              </p>
            </div>
          </aside>
        </div>
      </template>
    </template>
    </div>
  </div>
</template>

<style scoped>
.procure {
  min-height: 100vh;
}
.procure__topbar {
  position: sticky;
  top: 56px;
  z-index: 40;
  background: rgba(15, 17, 23, 0.88);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-default);
}
.procure__topbar-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: var(--space-3) var(--space-5);
  display: flex;
  align-items: center;
  gap: var(--space-4);
}
.procure__back {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  padding: 6px 10px;
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
  flex-shrink: 0;
  background: none;
  border: none;
  cursor: pointer;
}
.procure__back:hover {
  color: var(--text-primary);
  background: var(--bg-3);
}
.procure__query {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  flex: 1;
}
.procure__query-label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  flex-shrink: 0;
}
.procure__query-text {
  font-size: var(--font-size-sm);
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.procure__steps {
  flex-shrink: 0;
}

.procure__body {
  max-width: 1240px;
  margin: 0 auto;
  padding: var(--space-5);
}
.procure__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: var(--space-4);
  align-items: start;
}
.procure__main {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.procure__aside {
  position: sticky;
  top: 128px;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.aside-card {
  padding: var(--space-4);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  background: linear-gradient(
      180deg,
      rgba(255, 255, 255, 0.035),
      rgba(255, 255, 255, 0.01)
    ),
    var(--bg-1);
}
.aside-card--muted {
  border-style: dashed;
}
.aside-card__label {
  display: block;
  margin-bottom: var(--space-2);
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.aside-card b {
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
}
.aside-card p {
  margin-top: var(--space-2);
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: 1.6;
  word-break: break-word;
}
.aside-metric {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) 0;
  border-top: 1px solid var(--border-subtle);
}
.aside-metric span {
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
}
.aside-metric--ok {
  color: var(--success) !important;
}

.procure__vague {
  text-align: center;
  padding: var(--space-6) var(--space-4);
}
.procure__vague-icon {
  font-size: 40px;
  color: var(--text-tertiary);
  margin-bottom: var(--space-3);
}
.procure__vague-title {
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}
.procure__vague-desc {
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
  margin-bottom: var(--space-4);
}

.procure__grade-main {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.procure__rfq-persisted {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-3);
  padding: var(--space-2) var(--space-3);
  background: var(--success-soft, #f0fdf4);
  border: 1px solid var(--success, #16a34a);
  border-radius: var(--radius-sm, 4px);
  color: var(--success, #16a34a);
  font-size: var(--font-size-sm);
  flex-wrap: wrap;
}
.procure__rfq-persisted-icon { font-weight: 700; }
.procure__grade-letter {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: var(--font-size-xl);
  font-weight: 700;
  border-radius: var(--radius-md);
  font-family: var(--font-mono);
}
.grade-A,
.grade-B {
  color: var(--success);
  background: var(--success-soft);
}
.grade-C {
  color: var(--warning);
  background: var(--warning-soft);
}
.grade-D {
  color: var(--danger);
  background: var(--danger-soft);
}
.procure__grade-score {
  font-size: var(--font-size-md);
  color: var(--text-secondary);
  font-family: var(--font-mono);
}
.procure__grade-reasons {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.procure__grade-reasons li {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  padding-left: var(--space-4);
  position: relative;
}
.procure__grade-reasons li::before {
  content: '·';
  position: absolute;
  left: var(--space-2);
  color: var(--text-tertiary);
}

.procure__done {
  text-align: center;
  padding: var(--space-4) 0;
}

.procure__session-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: 80px var(--space-4);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}
.procure__session-loading .history__spinner {
  width: 18px; height: 18px;
  border: 2px solid var(--accent-soft);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 768px) {
  .procure__topbar-inner {
    flex-wrap: wrap;
  }
  .procure__steps {
    width: 100%;
    overflow-x: auto;
  }
  .procure__grid {
    grid-template-columns: 1fr;
  }
  .procure__aside {
    position: static;
  }
}
</style>