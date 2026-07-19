<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useProcureStore } from '@/stores/procure'
import type { SpecField } from '@/types/procure'
import SpecConfirm from '@/components/procure/SpecConfirm.vue'
import AppButton from '@/components/ui/AppButton.vue'

const router = useRouter()
const route = useRoute()
const store = useProcureStore()

const loading = ref(false)
const error = ref<string | null>(null)

const spec = computed<Record<string, SpecField> | null>(() => {
  return (store.normalizedSpec || store.parsedSpec) as Record<string, SpecField> | null
})

onMounted(async () => {
  const sessionId = route.query.session as string | undefined
  if (sessionId && !spec.value) {
    loading.value = true
    try {
      const ok = await store.loadFromSession(sessionId)
      if (!ok) error.value = '未能加载该会话（可能已被删除）。'
    } catch (e: any) {
      error.value = e?.message || '加载会话失败'
    } finally {
      loading.value = false
    }
  }
})

function goBack() { router.push('/chat') }
</script>

<template>
  <div class="sc-page">
    <header class="sc-page__head">
      <div>
        <h1>规格确认</h1>
        <p class="sc-page__sub">AI 解析的物料规格参数</p>
      </div>
      <AppButton @click="goBack">返回对话</AppButton>
    </header>

    <div v-if="loading" class="sc-page__loading">
      <span class="sc-page__spinner" /><span>加载会话中…</span>
    </div>
    <div v-else-if="error" class="sc-page__error">
      <p>{{ error }}</p>
      <AppButton @click="goBack">返回对话</AppButton>
    </div>
    <div v-else-if="spec" class="sc-page__content">
      <SpecConfirm :spec="spec" :gating="false" readonly />
    </div>
    <div v-else class="sc-page__empty">
      <div class="sc-page__empty-icon">⊘</div>
      <p class="sc-page__empty-title">暂无规格数据</p>
      <p class="sc-page__empty-desc">请先通过对话寻源获取规格解析结果。</p>
      <AppButton @click="goBack">前往对话寻源</AppButton>
    </div>
  </div>
</template>

<style scoped>
.sc-page {
  max-width: 960px;
  margin: 0 auto;
  padding: var(--space-6) var(--space-5);
}
.sc-page__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}
.sc-page__head h1 { font-size: var(--font-size-2xl); font-weight: 700; }
.sc-page__sub { font-size: var(--font-size-sm); color: var(--text-tertiary); margin-top: var(--space-1); }
.sc-page__loading { display: flex; align-items: center; justify-content: center; gap: var(--space-3); padding: var(--space-8); color: var(--text-tertiary); }
.sc-page__spinner { width: 18px; height: 18px; border: 2px solid var(--accent-soft); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.sc-page__error { text-align: center; padding: var(--space-8); color: var(--danger); }
.sc-page__error p { margin-bottom: var(--space-4); font-size: var(--font-size-md); }
.sc-page__empty { text-align: center; padding: var(--space-8); }
.sc-page__empty-icon { font-size: 40px; color: var(--text-tertiary); margin-bottom: var(--space-3); }
.sc-page__empty-title { font-size: var(--font-size-lg); font-weight: 600; color: var(--text-secondary); margin-bottom: var(--space-2); }
.sc-page__empty-desc { font-size: var(--font-size-sm); color: var(--text-tertiary); margin-bottom: var(--space-4); max-width: 360px; margin-left: auto; margin-right: auto; }
</style>
