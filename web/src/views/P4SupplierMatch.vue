<template>
  <div class="page-container">
    <!-- 步骤指示器 -->
    <div class="steps">
      <div class="step done">1. 输入需求</div>
      <div class="step done">2. 规格确认</div>
      <div class="step done">3. 替代料</div>
      <div class="step active">4. 供应商</div>
      <div class="step">5. 询价单</div>
    </div>

    <h2 class="page-title">候选供应商</h2>

    <!-- 始终显示的提示条 -->
    <div class="alert alert-warning fixed-alert">
      ⚠️ 以下为<strong>供应能力匹配</strong>，非实时库存承诺。库存/交期/价格以供应商最终确认为准。
    </div>

    <!-- 选中替代回显 -->
    <div class="card selected-alt-card">
      <div class="card-body">
        <span class="label">替代型号：</span>
        <span class="part">{{ store.selectedAlternative?.part }}</span>
        <span class="brand">{{ store.selectedAlternative?.brand }}</span>
        <span class="tag" :class="levelTagClass(store.selectedAlternative?.level)">
          {{ store.selectedAlternative?.level }}
        </span>
      </div>
    </div>

    <!-- 加载 -->
    <div v-if="loading" class="card">
      <div class="card-body empty-state">
        <div class="loading-spinner" style="margin: 0 auto 12px" />
        <p>正在匹配供应商…</p>
      </div>
    </div>

    <!-- 错误 -->
    <div v-else-if="loadError" class="card">
      <div class="card-body error-state">
        <p>{{ loadError }}</p>
        <button class="btn btn-primary" @click="fetchSuppliers">重试</button>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="store.matchedSuppliers.length === 0" class="card">
      <div class="card-body empty-state">
        <p class="icon">🏭</p>
        <p><strong>暂无匹配该品类的核验供应商</strong></p>
        <p>系统将继续扩充供应商库</p>
      </div>
    </div>

    <!-- 供应商列表 -->
    <div v-else>
      <div
        v-for="sup in store.matchedSuppliers"
        :key="sup.id"
        class="card supplier-card"
        :class="{ selected: isSelected(sup.id) }"
      >
        <div class="card-body">
          <div class="sup-header">
            <div class="sup-title">
              <label class="checkbox-label">
                <input
                  type="checkbox"
                  :checked="isSelected(sup.id)"
                  @change="toggleSupplier(sup)"
                />
                <span class="sup-name">{{ sup.name }}</span>
              </label>
              <span class="sup-score">匹配度 {{ (sup.score * 100).toFixed(0) }}%</span>
            </div>
          </div>

          <div class="sup-meta">
            <div class="meta-row">
              <span class="meta-label">经营品类</span>
              <span class="meta-value">{{ sup.category }}</span>
            </div>
            <div class="meta-row">
              <span class="meta-label">品牌覆盖</span>
              <span class="meta-value">{{ (sup.brands || []).join('、') || '-' }}</span>
            </div>
            <div class="meta-row">
              <span class="meta-label">资质</span>
              <span class="meta-value">
                <span v-for="q in sup.qualifications" :key="q" class="tag tag-blue" style="margin-right: 4px">{{ q }}</span>
                <span v-if="!sup.qualifications?.length">-</span>
              </span>
            </div>
            <div class="meta-row">
              <span class="meta-label">地区</span>
              <span class="meta-value">{{ sup.location }}</span>
            </div>
            <div class="meta-row">
              <span class="meta-label">MOQ</span>
              <span class="meta-value">{{ sup.moq ? sup.moq + ' pcs' : '供应商自报' }}</span>
            </div>
            <div class="meta-row">
              <span class="meta-label">历史响应</span>
              <span class="meta-value">{{ sup.lead_time_weeks ? sup.lead_time_weeks + '周' : '暂无数据' }}</span>
            </div>
          </div>

          <div class="sup-footer">
            <div class="sup-source">
              <span class="meta-label">数据来源：</span>{{ sup.data_source }}
            </div>
            <div class="sup-updated">
              更新于 {{ sup.updated_at || '未知' }}
            </div>
          </div>

          <div class="sup-stock-flags">
            <span class="stock-flag">
              {{ sup.in_stock ? '📦 能力匹配' : '📦 未确认库存' }}
            </span>
            <span class="stock-flag">⏱ 未确认交期</span>
            <span class="stock-flag">💰 未确认价格</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 操作 -->
    <div class="bottom-actions">
      <button class="btn btn-ghost" @click="$router.push('/alternatives')">← 返回替代料</button>
      <button
        class="btn btn-primary"
        :disabled="store.selectedSuppliers.length === 0"
        @click="goToRfq"
      >
        生成询价单 (已选 {{ store.selectedSuppliers.length }})
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useProcureStore } from '@/stores/procure'
import { matchSuppliers } from '@/api'
import type { Supplier } from '@/api'

const router = useRouter()
const store = useProcureStore()

const loading = ref(false)
const loadError = ref('')

function isSelected(id: string) {
  return store.selectedSuppliers.some((s) => s.id === id)
}

function toggleSupplier(sup: Supplier) {
  if (isSelected(sup.id)) {
    store.selectedSuppliers = store.selectedSuppliers.filter((s) => s.id !== sup.id)
  } else {
    store.selectedSuppliers.push(sup)
  }
}

function levelTagClass(level?: string) {
  const map: Record<string, string> = {
    L1: 'tag-green', L2: 'tag-green', L3: 'tag-yellow', L4: 'tag-red', L5: 'tag-gray',
  }
  return map[level || 'L5'] || 'tag-gray'
}

function goToRfq() {
  router.push('/rfq-edit')
}

async function fetchSuppliers() {
  loading.value = true
  loadError.value = ''
  try {
    const res = await matchSuppliers(
      store.parsedSpec || {},
      store.alternatives,
      {}
    )
    store.matchedSuppliers = res.data.matched_suppliers || []
  } catch (e: any) {
    loadError.value = `供应商匹配失败: ${e.message}`
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (!store.selectedAlternative) {
    router.push('/alternatives')
    return
  }
  if (store.matchedSuppliers.length === 0) {
    fetchSuppliers()
  }
})
</script>

<style scoped>
.page-title {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 16px;
}

.fixed-alert {
  margin-bottom: 16px;
}

.selected-alt-card {
  margin-bottom: 20px;
}

.selected-alt-card .part {
  font-weight: 600;
  font-family: 'SF Mono', 'Cascadia Code', monospace;
}

.selected-alt-card .brand {
  color: var(--color-text-secondary);
  margin-left: 8px;
}

.supplier-card {
  margin-bottom: 12px;
  transition: border-color 0.15s;
}

.supplier-card.selected {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px var(--color-primary-light);
}

.sup-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.sup-name {
  font-weight: 600;
  font-size: 15px;
}

.sup-score {
  font-size: 13px;
  color: var(--color-primary);
  font-weight: 600;
}

.sup-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px 24px;
  margin-bottom: 12px;
}

.meta-row {
  display: flex;
  gap: 8px;
  font-size: 13px;
}

.meta-label {
  color: var(--color-text-muted);
  flex-shrink: 0;
}

.sup-footer {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--color-text-muted);
  margin-bottom: 8px;
}

.sup-stock-flags {
  display: flex;
  gap: 16px;
}

.stock-flag {
  font-size: 12px;
  color: var(--color-text-muted);
}

.bottom-actions {
  display: flex;
  justify-content: space-between;
  margin-top: 20px;
}
</style>