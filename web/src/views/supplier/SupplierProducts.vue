<script setup lang="ts">
import { ref, onMounted } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'

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
        <p class="page-desc">管理您的元器件产品目录</p>
      </div>
      <AppButton variant="primary" @click="showForm = !showForm">
        {{ showForm ? '取消' : '添加产品' }}
      </AppButton>
    </div>

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
            <input v-model="formData.partNumber" class="form-input" placeholder="如 CC0805KKX7R9BB103" />
          </div>
          <div class="form-group">
            <label>品牌 *</label>
            <input v-model="formData.brand" class="form-input" placeholder="如 YAGEO" />
          </div>
          <div class="form-group">
            <label>封装</label>
            <input v-model="formData.package" class="form-input" placeholder="如 0805" />
          </div>
          <div class="form-group">
            <label>最小起订量 (MOQ)</label>
            <input v-model.number="formData.moq" type="number" class="form-input" min="1" />
          </div>
          <div class="form-group">
            <label>库存量</label>
            <input v-model.number="formData.stock" type="number" class="form-input" min="0" />
          </div>
        </div>
        <div class="form-actions">
          <AppButton variant="primary" :disabled="!formData.partNumber || !formData.brand" @click="handleAdd">
            确认添加
          </AppButton>
        </div>
      </div>
    </div>

    <!-- 加载 -->
    <div v-if="loading" class="card">
      <div class="card__body">
        <div v-for="i in 3" :key="i" class="skeleton" style="height: 50px; margin-bottom: 8px" />
      </div>
    </div>

    <!-- 空态 -->
    <div v-else-if="products.length === 0" class="card">
      <div class="card__body empty-state">
        <p class="empty-icon">📦</p>
        <p>还没有产品，点击上方"添加产品"开始</p>
      </div>
    </div>

    <!-- 产品列表 -->
    <div v-else class="products-list">
      <div v-for="p in products" :key="p.id" class="product-card card">
        <div class="product-card__head">
          <div class="product-card__info">
            <span class="product-card__part mono">{{ p.partNumber }}</span>
            <span class="product-card__brand">{{ p.brand }}</span>
            <span class="tag tag-gray">{{ p.category }}</span>
          </div>
          <div class="product-card__badges">
            <span v-if="p.stock === 0" class="tag tag-yellow">缺货</span>
            <span v-else class="tag tag-green">有货</span>
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
            <span>{{ p.moq.toLocaleString() }} pcs</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">库存</span>
            <span>{{ p.stock.toLocaleString() }} pcs</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">更新</span>
            <span>{{ p.updatedAt }}</span>
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
  margin-bottom: var(--space-5);
}
.page-title { font-size: var(--font-size-xl); font-weight: 700; }
.page-desc { color: var(--text-secondary); margin-top: 4px; font-size: var(--font-size-sm); }

.card {
  background: var(--bg-2);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  margin-bottom: var(--space-3);
}
.card__head {
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-subtle);
}
.card__head h3 { font-size: var(--font-size-md); font-weight: 600; }
.card__body { padding: var(--space-5); }

/* 表单 */
.form-card { margin-bottom: var(--space-4); }
.form-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}
.form-group { display: flex; flex-direction: column; gap: 6px; }
.form-group label { font-size: var(--font-size-sm); color: var(--text-secondary); }
.form-input, .form-select {
  padding: 8px 12px;
  background: var(--bg-3);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  outline: none;
  transition: border-color var(--transition-fast);
}
.form-input:focus, .form-select:focus { border-color: var(--accent); }
.form-actions { display: flex; justify-content: flex-end; }

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
.product-card__part { font-weight: 600; font-size: var(--font-size-md); }
.product-card__brand { color: var(--text-secondary); font-size: var(--font-size-sm); }
.product-card__badges { display: flex; gap: var(--space-2); align-items: center; }
.product-card__meta {
  display: flex;
  gap: var(--space-5);
  font-size: var(--font-size-sm);
  flex-wrap: wrap;
}
.meta-item { display: flex; gap: 6px; }
.meta-label { color: var(--text-tertiary); }

.tag { font-size: var(--font-size-xs); padding: 2px 8px; border-radius: var(--radius-sm); }
.tag-gray { color: var(--text-tertiary); background: var(--bg-3); }
.tag-green { color: var(--success); background: var(--success-soft); }
.tag-yellow { color: var(--warning); background: var(--warning-soft); }

.status-toggle {
  font-size: var(--font-size-xs);
  padding: 3px 10px;
  border-radius: var(--radius-sm);
  background: var(--success-soft);
  color: var(--success);
  transition: all var(--transition-fast);
}
.status-toggle.inactive {
  background: var(--bg-3);
  color: var(--text-tertiary);
}
.status-toggle:hover { opacity: 0.8; }

.empty-state { text-align: center; padding: var(--space-8); color: var(--text-tertiary); }
.empty-icon { font-size: 40px; margin-bottom: var(--space-3); opacity: 0.4; }

.skeleton {
  background: linear-gradient(90deg, var(--bg-3) 25%, var(--border-subtle) 50%, var(--bg-3) 75%);
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
