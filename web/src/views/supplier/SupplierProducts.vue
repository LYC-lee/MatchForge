<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'
import Tag from '@/components/ui/Tag.vue'
import EmptyState from '@/components/ui/EmptyState.vue'

interface Product {
  id: string
  category: string
  partNumber: string
  brand: string
  package: string
  moq: number
  stock: number
  status: 'active' | 'inactive'
  updatedAt: string
}

const products = ref<Product[]>([])
const loading = ref(true)
const showForm = ref(false)
const searchText = ref('')

// 内联编辑：stock / moq 可即时改
const editId = ref<string | null>(null)
const editForm = ref({ moq: 0, stock: 0 })

const formData = ref({
  category: 'MLCC',
  partNumber: '',
  brand: '',
  package: '',
  moq: 1000,
  stock: 0,
})

function handleAdd() {
  if (!formData.value.partNumber.trim() || !formData.value.brand.trim()) return
  products.value.unshift({
    id: `P${Date.now()}`,
    ...formData.value,
    status: 'active',
    updatedAt: new Date().toISOString().slice(0, 10),
  })
  showForm.value = false
  formData.value = { category: 'MLCC', partNumber: '', brand: '', package: '', moq: 1000, stock: 0 }
}

function toggleStatus(p: Product) {
  p.status = p.status === 'active' ? 'inactive' : 'active'
}

function startEdit(p: Product) {
  editId.value = p.id
  editForm.value = { moq: p.moq, stock: p.stock }
}
function saveEdit(p: Product) {
  p.moq = editForm.value.moq
  p.stock = editForm.value.stock
  p.updatedAt = new Date().toISOString().slice(0, 10)
  editId.value = null
}
function cancelEdit() {
  editId.value = null
}

const filteredProducts = computed(() => {
  const q = searchText.value.trim().toLowerCase()
  if (!q) return products.value
  return products.value.filter(
    (p) =>
      p.partNumber.toLowerCase().includes(q) ||
      p.brand.toLowerCase().includes(q) ||
      p.category.toLowerCase().includes(q),
  )
})

onMounted(() => {
  setTimeout(() => {
    products.value = [
      { id: 'P001', category: 'MLCC', partNumber: 'CC0805KKX7R9BB103', brand: 'YAGEO', package: '0805', moq: 3000, stock: 50000, status: 'active', updatedAt: '2026-07-14' },
      { id: 'P002', category: 'MLCC', partNumber: '0805F105Z500NT', brand: 'Walsin', package: '0805', moq: 5000, stock: 100000, status: 'active', updatedAt: '2026-07-13' },
      { id: 'P003', category: 'MLCC', partNumber: 'GRM21BR61E105KA12L', brand: 'Murata', package: '0805', moq: 4000, stock: 20000, status: 'active', updatedAt: '2026-07-10' },
      { id: 'P004', category: 'MLCC', partNumber: 'CL21B105KAFNNNE', brand: 'Samsung EM', package: '0805', moq: 5000, stock: 0, status: 'inactive', updatedAt: '2026-06-28' },
    ]
    loading.value = false
  }, 400)
})

const categories = ['MLCC', '贴片电阻', '钽电容', '连接器', '分立器件']
</script>

<template>
  <div class="supplier-page">
    <div class="page-head">
      <div>
        <h2 class="page-title">产品管理</h2>
        <p class="page-desc">
          管理您的元器件产品目录
          <Tag type="notice" value="演示数据" />
        </p>
      </div>
      <AppButton @click="showForm = !showForm">
        {{ showForm ? '取消' : '添加产品' }}
      </AppButton>
    </div>

    <p class="demo-hint">本页为前端演示数据，刷新后重置；后续接入真实产品接口后自动切换。</p>

    <!-- 添加表单 -->
    <div v-if="showForm" class="form-card card">
      <div class="card__head"><h3>添加产品</h3></div>
      <div class="card__body">
        <div class="form-grid">
          <div class="form-group">
            <label>品类</label>
            <select v-model="formData.category" class="form-select">
              <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
            </select>
          </div>
          <div class="form-group">
            <label>型号 *</label>
            <input v-model="formData.partNumber" class="form-input" placeholder="如 CC0805KKX7R9BB103">
          </div>
          <div class="form-group">
            <label>品牌 *</label>
            <input v-model="formData.brand" class="form-input" placeholder="如 YAGEO">
          </div>
          <div class="form-group">
            <label>封装</label>
            <input v-model="formData.package" class="form-input" placeholder="如 0805">
          </div>
          <div class="form-group">
            <label>最小起订量 (MOQ)</label>
            <input v-model.number="formData.moq" type="number" class="form-input" min="1">
          </div>
          <div class="form-group">
            <label>库存量</label>
            <input v-model.number="formData.stock" type="number" class="form-input" min="0">
          </div>
        </div>
        <div class="form-actions">
          <AppButton :disabled="!formData.partNumber || !formData.brand" @click="handleAdd">确认添加</AppButton>
        </div>
      </div>
    </div>

    <!-- 搜索 -->
    <div v-if="!loading && products.length" class="search-bar">
      <input v-model="searchText" type="text" class="form-input" placeholder="搜索型号 / 品牌 / 品类…">
    </div>

    <!-- 加载 -->
    <div v-if="loading" class="card">
      <div class="card__body">
        <div v-for="i in 3" :key="i" class="skeleton" style="height: 50px; margin-bottom: 8px" />
      </div>
    </div>

    <!-- 空态 -->
    <EmptyState
      v-else-if="products.length === 0"
      title="还没有产品"
      description='点击上方"添加产品"开始维护产品目录。'
    />
    <EmptyState
      v-else-if="!filteredProducts.length"
      title="没有匹配的产品"
      description="换个关键词试试。"
      compact
    />

    <!-- 产品列表 -->
    <div v-else class="products-list">
      <div v-for="p in filteredProducts" :key="p.id" class="product-card card">
        <div class="product-card__head">
          <div class="product-card__info">
            <span class="product-card__part mono">{{ p.partNumber }}</span>
            <span class="product-card__brand">{{ p.brand }}</span>
            <Tag type="neutral" :value="p.category" />
          </div>
          <div class="product-card__badges">
            <Tag v-if="p.stock === 0" type="warning" value="缺货" />
            <Tag v-else type="success" value="有货" />
            <button
              class="status-toggle"
              :class="{ inactive: p.status === 'inactive' }"
              @click="toggleStatus(p)"
            >
              {{ p.status === 'active' ? '已上架' : '已下架' }}
            </button>
          </div>
        </div>
        <div class="product-card__meta">
          <div class="meta-item">
            <span class="meta-label">封装</span>
            <span>{{ p.package || '-' }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">MOQ</span>
            <span v-if="editId !== p.id" class="num">{{ p.moq.toLocaleString() }} pcs</span>
            <input v-else v-model.number="editForm.moq" type="number" class="form-input meta-edit" min="0">
          </div>
          <div class="meta-item">
            <span class="meta-label">库存</span>
            <span v-if="editId !== p.id" class="num">{{ p.stock.toLocaleString() }} pcs</span>
            <input v-else v-model.number="editForm.stock" type="number" class="form-input meta-edit" min="0">
          </div>
          <div class="meta-item">
            <span class="meta-label">更新</span>
            <span>{{ p.updatedAt }}</span>
          </div>
          <div class="meta-item meta-item--actions">
            <template v-if="editId === p.id">
              <AppButton variant="ghost" size="sm" @click="cancelEdit">取消</AppButton>
              <AppButton variant="secondary" size="sm" @click="saveEdit(p)">保存</AppButton>
            </template>
            <AppButton v-else variant="ghost" size="sm" @click="startEdit(p)">编辑</AppButton>
          </div>
        </div>
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
  margin-bottom: var(--space-3);
}
.page-title { font-size: var(--font-size-xl); line-height: var(--leading-xl); font-weight: 700; }
.page-desc { color: var(--text-secondary); margin-top: var(--space-1); font-size: var(--font-size-sm); line-height: var(--leading-sm); display: flex; align-items: center; gap: var(--space-2); }
.demo-hint { color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: var(--leading-xs); margin-bottom: var(--space-4); }

.card {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  margin-bottom: var(--space-3);
}
.card__head {
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-subtle);
}
.card__head h3 { font-size: var(--font-size-md); line-height: var(--leading-md); font-weight: 600; }
.card__body { padding: var(--space-5); }

/* 表单 */
.form-card { margin-bottom: var(--space-4); }
.form-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}
.form-group { display: flex; flex-direction: column; gap: var(--space-1); }
.form-group label { font-size: var(--font-size-sm); line-height: var(--leading-sm); color: var(--text-secondary); }
.form-input, .form-select {
  padding: var(--space-2) var(--space-3);
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  outline: none;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.form-input:focus, .form-select:focus { border-color: var(--accent-border); box-shadow: 0 0 0 3px var(--accent-soft); }
.form-actions { display: flex; justify-content: flex-end; }

.search-bar { margin-bottom: var(--space-3); }
.search-bar .form-input { width: 100%; box-sizing: border-box; }

/* 产品卡片 */
.products-list { display: flex; flex-direction: column; gap: var(--space-3); }
.product-card { padding: var(--space-4); }
.product-card__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.product-card__info { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.product-card__part { font-weight: 600; font-size: var(--font-size-md); line-height: var(--leading-md); }
.product-card__brand { color: var(--text-secondary); font-size: var(--font-size-sm); line-height: var(--leading-sm); }
.product-card__badges { display: flex; gap: var(--space-2); align-items: center; }
.product-card__meta {
  display: flex;
  gap: var(--space-5);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  flex-wrap: wrap;
  align-items: center;
}
.meta-item { display: flex; gap: var(--space-1); align-items: center; }
.meta-item--actions { gap: var(--space-2); margin-left: auto; }
.meta-label { color: var(--text-tertiary); }
.meta-edit { width: 110px; }

.status-toggle {
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
  background: var(--success-soft);
  color: var(--success);
  border: 1px solid var(--success-border);
  transition: opacity var(--transition-fast);
}
.status-toggle.inactive {
  background: var(--bg-subtle);
  color: var(--text-tertiary);
  border-color: var(--border-default);
}
.status-toggle:hover { opacity: 0.8; }

.skeleton {
  background: linear-gradient(90deg, var(--bg-subtle) 25%, var(--border-subtle) 50%, var(--bg-subtle) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-sm);
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
@media (max-width: 768px) {
  .form-grid { grid-template-columns: 1fr; }
}
</style>
