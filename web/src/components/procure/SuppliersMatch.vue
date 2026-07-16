<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Supplier } from '@/types/procure'
import Card from '@/components/ui/Card.vue'
import AppButton from '@/components/ui/AppButton.vue'
import Tag from '@/components/ui/Tag.vue'

const props = defineProps<{
  suppliers: Supplier[]
  selectedIds: Set<string>
  streaming: boolean
  streamProgress: string
  error: string | null
}>()
const emit = defineEmits<{
  (e: 'toggle', id: string): void
  (e: 'selectAll'): void
  (e: 'deselectAll'): void
  (e: 'generate'): void
  (e: 'retry'): void
}>()

// ── 排序 ──
type SortKey = 'score' | 'name' | 'region'
const sortKey = ref<SortKey>('score')
const sortOptions: { key: SortKey; label: string }[] = [
  { key: 'score', label: '匹配度' },
  { key: 'name', label: '名称' },
  { key: 'region', label: '地区' },
]

// ── 筛选 ──
const searchText = ref('')
const filterRegion = ref('')
const filterQualification = ref('')

const allRegions = computed(() => [...new Set(props.suppliers.map((s) => s.region).filter(Boolean))].sort())
const allQualifications = computed(() =>
  [...new Set(props.suppliers.flatMap((s) => s.qualifications))].filter(Boolean).sort(),
)

const filteredSuppliers = computed(() => {
  let list = [...props.suppliers]

  if (searchText.value) {
    const q = searchText.value.toLowerCase()
    list = list.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        s.categories.some((c) => c.toLowerCase().includes(q)) ||
        s.brands.some((b) => b.toLowerCase().includes(q)),
    )
  }
  if (filterRegion.value) {
    list = list.filter((s) => s.region === filterRegion.value)
  }
  if (filterQualification.value) {
    list = list.filter((s) => s.qualifications.includes(filterQualification.value))
  }

  // 排序
  if (sortKey.value === 'score') {
    list.sort((a, b) => b.match_score - a.match_score)
  } else if (sortKey.value === 'name') {
    list.sort((a, b) => a.name.localeCompare(b.name))
  } else if (sortKey.value === 'region') {
    list.sort((a, b) => a.region.localeCompare(b.region))
  }

  return list
})

// ── 对比模式 ──
const compareMode = ref(false)
const compareIds = computed(() => {
  if (!compareMode.value) return new Set<string>()
  return new Set(props.selectedIds)
})

function toggleCompare() {
  compareMode.value = !compareMode.value
}

// ── 全选/反选 ──
const allSelected = computed(() => {
  if (!filteredSuppliers.value.length) return false
  return filteredSuppliers.value.every((s) => props.selectedIds.has(s.id))
})
const noneSelected = computed(() => props.selectedIds.size === 0)

function toggleSelectAll() {
  if (allSelected.value) {
    emit('deselectAll')
  } else {
    emit('selectAll')
  }
}

// ── 匹配度可视化 ──
function scoreClass(score: number) {
  if (score >= 0.8) return 'high'
  if (score >= 0.65) return 'mid'
  return 'low'
}

function scoreLabel(score: number) {
  if (score >= 0.8) return '高度匹配'
  if (score >= 0.65) return '中度匹配'
  return '低度匹配'
}

// ── 工具函数 ──
function formatPct(n: number) {
  return Math.round(n * 100) + '%'
}
</script>

<template>
  <div class="sups">
    <!-- 免责声明 -->
    <div class="sups__notice">
      <span class="sups__notice-icon">ⓘ</span>
      <span>
        以下为<b>供应能力匹配</b>，非实时库存、报价或交期承诺，最终以供应商正式确认为准。
        本平台首期不提供交易、支付与物流服务。
      </span>
    </div>

    <!-- 流式进度 -->
    <div v-if="streaming" class="sups__streaming">
      <span class="sups__streaming-spinner" />
      <span>{{ streamProgress || '正在匹配供应商…' }}</span>
    </div>

    <!-- 错误重试 -->
    <div v-if="error && !streaming" class="sups__error">
      <span class="sups__error-icon">⚠</span>
      <span>{{ error }}</span>
      <AppButton variant="secondary" size="sm" @click="emit('retry')">重试</AppButton>
    </div>

    <!-- 工具栏 -->
    <div v-if="!streaming && suppliers.length > 0" class="sups__toolbar">
      <div class="sups__toolbar-left">
        <input
          v-model="searchText"
          type="text"
          class="sups__search"
          placeholder="搜索供应商名称 / 品类 / 品牌…"
        />
        <select v-model="filterRegion" class="sups__select">
          <option value="">全部地区</option>
          <option v-for="r in allRegions" :key="r" :value="r">{{ r }}</option>
        </select>
        <select v-model="filterQualification" class="sups__select">
          <option value="">全部资质</option>
          <option v-for="q in allQualifications" :key="q" :value="q">{{ q }}</option>
        </select>
      </div>
      <div class="sups__toolbar-right">
        <span class="sups__sort-label">排序:</span>
        <button
          v-for="opt in sortOptions"
          :key="opt.key"
          class="sups__sort-btn"
          :class="{ active: sortKey === opt.key }"
          @click="sortKey = opt.key"
        >
          {{ opt.label }}
        </button>
        <button
          class="sups__compare-toggle"
          :class="{ active: compareMode }"
          @click="toggleCompare"
        >
          {{ compareMode ? '退出对比' : '对比选中' }}
        </button>
      </div>
    </div>

    <!-- 对比视图 -->
    <div v-if="compareMode && compareIds.size > 0" class="sups__compare">
      <h4 class="sups__compare-title">
        供应商横向对比 ({{ compareIds.size }} 家)
      </h4>
      <div class="sups__compare-table-wrap">
        <table class="sups__compare-table">
          <thead>
            <tr>
              <th>维度</th>
              <th v-for="s in suppliers.filter((x) => compareIds.has(x.id))" :key="s.id">
                {{ s.name }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>匹配度</td>
              <td v-for="s in suppliers.filter((x) => compareIds.has(x.id))" :key="s.id">
                <span class="sup__score" :class="scoreClass(s.match_score)">
                  {{ formatPct(s.match_score) }}
                </span>
              </td>
            </tr>
            <tr>
              <td>地区</td>
              <td v-for="s in suppliers.filter((x) => compareIds.has(x.id))" :key="s.id">{{ s.region }}</td>
            </tr>
            <tr>
              <td>经营品类</td>
              <td v-for="s in suppliers.filter((x) => compareIds.has(x.id))" :key="s.id">{{ s.categories.join(' / ') }}</td>
            </tr>
            <tr>
              <td>品牌覆盖</td>
              <td v-for="s in suppliers.filter((x) => compareIds.has(x.id))" :key="s.id">{{ s.brands.join(' / ') }}</td>
            </tr>
            <tr>
              <td>资质</td>
              <td v-for="s in suppliers.filter((x) => compareIds.has(x.id))" :key="s.id">
                <span v-if="s.qualifications.length">{{ s.qualifications.join(' / ') }}</span>
                <span v-else class="sups__muted">未验证</span>
              </td>
            </tr>
            <tr>
              <td>MOQ</td>
              <td v-for="s in suppliers.filter((x) => compareIds.has(x.id))" :key="s.id">{{ s.moq.toLocaleString() }} pcs</td>
            </tr>
            <tr>
              <td>历史响应</td>
              <td v-for="s in suppliers.filter((x) => compareIds.has(x.id))" :key="s.id">{{ s.response_speed }}</td>
            </tr>
            <tr>
              <td>数据来源</td>
              <td v-for="s in suppliers.filter((x) => compareIds.has(x.id))" :key="s.id">{{ s.data_source }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="!streaming && !error && suppliers.length === 0" class="sups__empty">
      <span class="sups__empty-icon">🏭</span>
      <p><strong>暂无匹配供应商</strong></p>
      <p>系统将继续扩充供应商库</p>
    </div>

    <!-- 供应商列表 -->
    <div v-if="filteredSuppliers.length > 0" class="sups__list">
      <div class="sups__list-header">
        <label class="sups__select-all">
          <input
            type="checkbox"
            class="sups__check"
            :checked="allSelected"
            :indeterminate="!allSelected && !noneSelected"
            @change="toggleSelectAll"
          />
          <span>{{ allSelected ? '取消全选' : '全选' }} ({{ selectedIds.size }}/{{ suppliers.length }})</span>
        </label>
        <span v-if="filteredSuppliers.length !== suppliers.length" class="sups__filtered-count">
          筛选结果: {{ filteredSuppliers.length }} 家
        </span>
      </div>

      <Card
        v-for="s in filteredSuppliers"
        :key="s.id"
        :elevated="selectedIds.has(s.id)"
        class="sup__card"
      >
        <template #header>
          <label class="sup__head" :class="{ 'is-selected': selectedIds.has(s.id) }">
            <input
              type="checkbox"
              class="sups__check"
              :checked="selectedIds.has(s.id)"
              @change="emit('toggle', s.id)"
            />
            <span class="sup__name">{{ s.name }}</span>
            <!-- 匹配度仪表盘 -->
            <div class="sup__score-wrap">
              <div class="sup__score-bar">
                <div
                  class="sup__score-fill"
                  :class="scoreClass(s.match_score)"
                  :style="{ width: formatPct(s.match_score) }"
                />
              </div>
              <span class="sup__score" :class="scoreClass(s.match_score)">
                {{ formatPct(s.match_score) }}
              </span>
              <span class="sup__score-label" :class="scoreClass(s.match_score)">
                {{ scoreLabel(s.match_score) }}
              </span>
            </div>
          </label>
        </template>

        <div class="sup__grid">
          <div class="sup__field"><span>地区</span><b>{{ s.region }}</b></div>
          <div class="sup__field"><span>经营品类</span><b>{{ s.categories.join(' / ') }}</b></div>
          <div class="sup__field"><span>品牌覆盖</span><b>{{ s.brands.join(' / ') }}</b></div>
          <div class="sup__field"><span>资质</span>
            <b v-if="s.qualifications.length">
              <Tag
                v-for="q in s.qualifications"
                :key="q"
                type="neutral"
                :value="q"
              />
            </b>
            <b v-else class="sups__muted">未验证</b>
          </div>
          <div class="sup__field"><span>MOQ</span><b>{{ s.moq ? s.moq.toLocaleString() + ' pcs' : '供应商自报' }}</b></div>
          <div class="sup__field"><span>历史响应</span><b>{{ s.response_speed }}</b></div>
        </div>

        <!-- RAG 知识库洞察 -->
        <div v-if="(s as any).rag_insights" class="sup__insights">
          <span class="sup__insights-label">📊 知识库洞察</span>
          <p>{{ (s as any).rag_insights }}</p>
        </div>

        <!-- 库存/交期/价格 确认标识 -->
        <div class="sup__confirm">
          <span class="sup__confirm-label">库存 / 交期 / 价格确认:</span>
          <span class="sup__confirm-val">
            <span :class="s.confirmed_stock ? 'sup__confirmed' : 'sup__unconfirmed'">
              {{ s.confirmed_stock ? '✓ 已确认' : '✗ 未确认库存' }}
            </span>
            <span class="sup__confirm-sep">|</span>
            <span :class="s.confirmed_lead ? 'sup__confirmed' : 'sup__unconfirmed'">
              {{ s.confirmed_lead ? '✓ 已确认' : '✗ 未确认交期' }}
            </span>
            <span class="sup__confirm-sep">|</span>
            <span :class="s.confirmed_price ? 'sup__confirmed' : 'sup__unconfirmed'">
              {{ s.confirmed_price ? '✓ 已确认' : '✗ 未确认价格' }}
            </span>
          </span>
        </div>
        <div class="sup__source">
          <span>数据来源: {{ s.data_source }}</span>
          <span>更新: {{ s.updated_at }}</span>
        </div>
      </Card>
    </div>

    <!-- 底部固定操作栏 -->
    <div class="sups__foot">
      <div class="sups__foot-left">
        <span class="sups__selected">已选 {{ selectedIds.size }} 家供应商</span>
        <span v-if="selectedIds.size > 0" class="sups__selected-detail">
          {{ suppliers.filter((s) => selectedIds.has(s.id)).map((s) => s.name).join('、') }}
        </span>
      </div>
      <AppButton size="lg" :disabled="!selectedIds.size" @click="emit('generate')">
        生成询价单
      </AppButton>
    </div>
  </div>
</template>

<style scoped>
.sups__notice {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--notice-soft);
  border: 1px solid rgba(249, 115, 22, 0.3);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  color: var(--notice);
  margin-bottom: var(--space-4);
}
.sups__notice b { color: var(--notice); }
.sups__notice-icon { font-size: 16px; flex-shrink: 0; }

/* 流式进度 */
.sups__streaming {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--bg-2);
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-md);
  color: var(--accent-hover);
  font-size: var(--font-size-sm);
  margin-bottom: var(--space-4);
}
.sups__streaming-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid var(--accent-soft);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* 错误 */
.sups__error {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--danger-soft);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  color: var(--danger);
  margin-bottom: var(--space-4);
}
.sups__error-icon { font-size: 18px; }

/* 工具栏 */
.sups__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
}
.sups__toolbar-left,
.sups__toolbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.sups__search {
  width: 220px;
  padding: 6px 10px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  background: var(--bg-2);
  color: var(--text-primary);
  font-size: var(--font-size-xs);
  outline: none;
}
.sups__search:focus { border-color: var(--accent); }
.sups__search::placeholder { color: var(--text-tertiary); }
.sups__select {
  padding: 6px 8px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  background: var(--bg-2);
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  outline: none;
}
.sups__sort-label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.sups__sort-btn {
  padding: 4px 10px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  background: var(--bg-2);
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.sups__sort-btn:hover { color: var(--text-secondary); border-color: var(--border-default); }
.sups__sort-btn.active {
  color: var(--accent-hover);
  border-color: var(--accent-border);
  background: var(--accent-soft);
}
.sups__compare-toggle {
  padding: 4px 12px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  background: var(--bg-2);
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  cursor: pointer;
  margin-left: var(--space-2);
  transition: all var(--transition-fast);
}
.sups__compare-toggle:hover { border-color: var(--accent-border); }
.sups__compare-toggle.active {
  color: var(--accent-hover);
  border-color: var(--accent-border);
  background: var(--accent-soft);
}

/* 对比表格 */
.sups__compare {
  margin-bottom: var(--space-4);
  padding: var(--space-4);
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-md);
  background: var(--bg-2);
}
.sups__compare-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-3);
}
.sups__compare-table-wrap {
  overflow-x: auto;
}
.sups__compare-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-xs);
}
.sups__compare-table th,
.sups__compare-table td {
  padding: 8px 12px;
  text-align: left;
  border-bottom: 1px solid var(--border-subtle);
  white-space: nowrap;
}
.sups__compare-table th {
  color: var(--text-tertiary);
  font-weight: 600;
  background: var(--bg-3);
}
.sups__compare-table td {
  color: var(--text-secondary);
}
.sups__compare-table td:first-child {
  color: var(--text-tertiary);
  font-weight: 500;
}
.sups__muted { color: var(--text-tertiary); font-style: italic; }

/* 空状态 */
.sups__empty {
  text-align: center;
  padding: var(--space-6);
  color: var(--text-tertiary);
}
.sups__empty-icon { font-size: 40px; display: block; margin-bottom: var(--space-3); }
.sups__empty p { margin-top: var(--space-1); font-size: var(--font-size-sm); }

/* 列表 */
.sups__list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) 0;
  margin-bottom: var(--space-2);
}
.sups__select-all {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  cursor: pointer;
}
.sups__filtered-count {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.sups__list { display: flex; flex-direction: column; gap: var(--space-3); }

.sups__check {
  width: 16px;
  height: 16px;
  accent-color: var(--accent);
  cursor: pointer;
}

/* 供应商卡片 */
.sup__card { transition: border-color var(--transition-fast); }
.sup__head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  cursor: pointer;
  width: 100%;
  flex-wrap: wrap;
}
.sup__name {
  font-size: var(--font-size-md);
  font-weight: 600;
  color: var(--text-primary);
  min-width: 120px;
}
.is-selected .sup__name { color: var(--accent-hover); }

/* 匹配度仪表盘 */
.sup__score-wrap {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-left: auto;
}
.sup__score-bar {
  width: 80px;
  height: 6px;
  border-radius: 3px;
  background: var(--bg-3);
  overflow: hidden;
}
.sup__score-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
}
.sup__score-fill.high { background: var(--success); }
.sup__score-fill.mid { background: var(--warning); }
.sup__score-fill.low { background: var(--text-tertiary); }
.sup__score {
  font-size: var(--font-size-xs);
  font-weight: 700;
  font-family: var(--font-mono);
  min-width: 40px;
  text-align: right;
}
.sup__score.high { color: var(--success); }
.sup__score.mid { color: var(--warning); }
.sup__score.low { color: var(--text-tertiary); }
.sup__score-label {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-weight: 600;
}
.sup__score-label.high { color: var(--success); background: var(--success-soft); }
.sup__score-label.mid { color: var(--warning); background: var(--warning-soft); }
.sup__score-label.low { color: var(--text-tertiary); background: var(--bg-3); }

/* 字段网格 */
.sup__grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.sup__field { display: flex; flex-direction: column; gap: 2px; }
.sup__field span { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.sup__field b { font-size: var(--font-size-sm); color: var(--text-secondary); font-weight: 500; }

/* RAG 洞察 */
.sup__insights {
  padding: var(--space-3);
  margin-bottom: var(--space-3);
  background: var(--bg-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
}
.sup__insights-label {
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--text-secondary);
  display: block;
  margin-bottom: var(--space-1);
}
.sup__insights p {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  line-height: 1.5;
  margin: 0;
}

/* 确认状态 */
.sup__confirm {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--bg-3);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
  margin-bottom: var(--space-3);
}
.sup__confirm-label { color: var(--text-tertiary); }
.sup__confirm-val { display: flex; align-items: center; gap: var(--space-2); }
.sup__confirm-sep { color: var(--border-default); }
.sup__confirmed { color: var(--success); }
.sup__unconfirmed { color: var(--text-tertiary); }

/* 数据来源 */
.sup__source { display: flex; gap: var(--space-4); font-size: var(--font-size-xs); color: var(--text-tertiary); }

/* 底部固定栏 */
.sups__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  margin-top: var(--space-5);
  padding: var(--space-4);
  background: var(--bg-2);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  position: sticky;
  bottom: var(--space-3);
}
.sups__foot-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.sups__selected { font-size: var(--font-size-sm); color: var(--text-secondary); font-weight: 600; }
.sups__selected-detail {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 420px;
}

@media (max-width: 640px) {
  .sup__grid { grid-template-columns: 1fr; }
  .sup__head { flex-direction: column; align-items: flex-start; }
  .sup__score-wrap { margin-left: 0; }
  .sups__toolbar { flex-direction: column; align-items: stretch; }
  .sups__toolbar-right { justify-content: flex-end; }
  .sups__search { width: 100%; }
  .sups__foot { flex-direction: column; }
  .sups__selected-detail { max-width: 100%; }
}
</style>