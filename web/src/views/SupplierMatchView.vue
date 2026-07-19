<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useProcureStore } from '@/stores/procure'
import type { Supplier } from '@/types/procure'
import SuppliersMatch from '@/components/procure/SuppliersMatch.vue'
import AppButton from '@/components/ui/AppButton.vue'

const router = useRouter()
const route = useRoute()
const store = useProcureStore()

const loading = ref(false)
const error = ref<string | null>(null)

const suppliers = computed<Supplier[]>(() => store.matchedSuppliers as Supplier[])
const selectedIds = computed(() => store.selectedSupplierIds)

onMounted(async () => {
  const sessionId = route.query.session as string | undefined
  if (sessionId && suppliers.value.length === 0) {
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
function goAlternatives() { router.push('/alternatives') }
</script>

<template>
  <div class="sp-page">
    <header class="sp-page__head">
      <div>
        <h1>供应商匹配</h1>
        <p class="sp-page__sub">基于规格与替代料匹配的供应商列表</p>
      </div>
      <div class="sp-page__actions">
        <AppButton variant="ghost" @click="goAlternatives">查看替代料</AppButton>
        <AppButton @click="goBack">返回对话</AppButton>
      </div>
    </header>

    <div v-if="loading" class="sp-page__loading">
      <span class="sp-page__spinner" /><span>加载会话中…</span>
    </div>
    <div v-else-if="error" class="sp-page__error">
      <p>{{ error }}</p>
      <AppButton @click="goBack">返回对话</AppButton>
    </div>
    <div v-else-if="suppliers.length" class="sp-page__content">
      <SuppliersMatch
        :suppliers="suppliers"
        :selected-ids="selectedIds"
        :streaming="false"
        :stream-progress="''"
        :error="null"
        @toggle="store.toggleSupplier($event)"
        @select-all="store.selectAllSuppliers()"
        @deselect-all="store.deselectAllSuppliers()"
      />
    </div>
    <div v-else class="sp-page__empty">
      <div class="sp-page__empty-icon">⊘</div>
      <p class="sp-page__empty-title">暂无供应商匹配数据</p>
      <p class="sp-page__empty-desc">请先通过对话寻源获取供应商匹配结果。</p>
      <AppButton @click="goBack">前往对话寻源</AppButton>
    </div>
  </div>
</template>

<style scoped>
.sp-page {
  max-width: 960px;
  margin: 0 auto;
  padding: var(--space-6) var(--space-5);
}
.sp-page__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
  flex-wrap: wrap;
}
.sp-page__head h1 { font-size: var(--font-size-2xl); font-weight: 700; }
.sp-page__sub { font-size: var(--font-size-sm); color: var(--text-tertiary); margin-top: var(--space-1); }
.sp-page__actions { display: flex; gap: var(--space-2); }
.sp-page__loading { display: flex; align-items: center; justify-content: center; gap: var(--space-3); padding: var(--space-8); color: var(--text-tertiary); }
.sp-page__spinner { width: 18px; height: 18px; border: 2px solid var(--accent-soft); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.sp-page__error { text-align: center; padding: var(--space-8); color: var(--danger); }
.sp-page__error p { margin-bottom: var(--space-4); font-size: var(--font-size-md); }
.sp-page__empty { text-align: center; padding: var(--space-8); }
.sp-page__empty-icon { font-size: 40px; color: var(--text-tertiary); margin-bottom: var(--space-3); }
.sp-page__empty-title { font-size: var(--font-size-lg); font-weight: 600; color: var(--text-secondary); margin-bottom: var(--space-2); }
.sp-page__empty-desc { font-size: var(--font-size-sm); color: var(--text-tertiary); margin-bottom: var(--space-4); max-width: 360px; margin-left: auto; margin-right: auto; }
</style>
