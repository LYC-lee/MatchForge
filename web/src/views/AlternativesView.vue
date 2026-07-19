<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useProcureStore } from '@/stores/procure'
import type { Alternative } from '@/types/procure'
import AlternativesList from '@/components/procure/AlternativesList.vue'
import AppButton from '@/components/ui/AppButton.vue'

const router = useRouter()
const route = useRoute()
const store = useProcureStore()

const loading = ref(false)
const error = ref<string | null>(null)

const alternatives = computed<Alternative[]>(() => store.alternatives as Alternative[])

const originalPart = computed(() => {
  const p = store.parsedSpec as Record<string, any> | null
  const n = store.normalizedSpec as Record<string, any> | null
  return n?.['型号']?.value || p?.['型号']?.value || ''
})

const originalBrand = computed(() => {
  const p = store.parsedSpec as Record<string, any> | null
  const n = store.normalizedSpec as Record<string, any> | null
  return n?.['品牌']?.value || p?.['品牌']?.value || ''
})

onMounted(async () => {
  const sessionId = route.query.session as string | undefined
  if (sessionId && alternatives.value.length === 0) {
    loading.value = true
    try {
      const ok = await store.loadFromSession(sessionId)
      if (!ok) {
        error.value = '未能加载该会话（可能已被删除）。'
      }
    } catch (e: any) {
      error.value = e?.message || '加载会话失败'
    } finally {
      loading.value = false
    }
  }
})

function goBack() {
  router.push('/chat')
}
</script>

<template>
  <div class="alt-page">
    <header class="alt-page__head">
      <div>
        <h1>替代料推荐</h1>
        <p class="alt-page__sub">基于知识图谱与规格交叉比对</p>
      </div>
      <AppButton @click="goBack">返回对话</AppButton>
    </header>

    <!-- 加载中 -->
    <div v-if="loading" class="alt-page__loading">
      <span class="alt-page__spinner" />
      <span>加载会话中…</span>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="alt-page__error">
      <p>{{ error }}</p>
      <AppButton @click="goBack">返回对话</AppButton>
    </div>

    <!-- 有数据 -->
    <div v-else-if="alternatives.length" class="alt-page__content">
      <AlternativesList
        :alternatives="alternatives"
        :original-part="originalPart"
        :original-brand="originalBrand"
      />
    </div>

    <!-- 空状态 -->
    <div v-else class="alt-page__empty">
      <div class="alt-page__empty-icon">⊘</div>
      <p class="alt-page__empty-title">暂无替代料数据</p>
      <p class="alt-page__empty-desc">请先通过对话寻源获取替代料推荐，或从历史记录加载已有会话。</p>
      <AppButton @click="goBack">前往对话寻源</AppButton>
    </div>
  </div>
</template>

<style scoped>
.alt-page {
  max-width: 960px;
  margin: 0 auto;
  padding: var(--space-6) var(--space-5);
}
.alt-page__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}
.alt-page__head h1 {
  font-size: var(--font-size-2xl);
  font-weight: 700;
}
.alt-page__sub {
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
  margin-top: var(--space-1);
}

.alt-page__loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-8) var(--space-4);
  color: var(--text-tertiary);
}
.alt-page__spinner {
  width: 18px;
  height: 18px;
  border: 2px solid var(--accent-soft);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

.alt-page__error {
  text-align: center;
  padding: var(--space-8) var(--space-4);
  color: var(--danger);
}
.alt-page__error p {
  margin-bottom: var(--space-4);
  font-size: var(--font-size-md);
}

.alt-page__empty {
  text-align: center;
  padding: var(--space-8) var(--space-4);
}
.alt-page__empty-icon {
  font-size: 40px;
  color: var(--text-tertiary);
  margin-bottom: var(--space-3);
}
.alt-page__empty-title {
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}
.alt-page__empty-desc {
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
  margin-bottom: var(--space-4);
  max-width: 360px;
  margin-left: auto;
  margin-right: auto;
}
</style>
