<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useProcureStore } from '@/stores/procure'
import type { Alternative, Supplier, SpecField } from '@/types/procure'
import RfqEditor from '@/components/procure/RfqEditor.vue'
import AppButton from '@/components/ui/AppButton.vue'

const router = useRouter()
const route = useRoute()
const store = useProcureStore()

const loading = ref(false)
const error = ref<string | null>(null)

const rfqDoc = computed(() => store.rfqDoc)
const rfqId = computed(() => store.rfqId)
const spec = computed<Record<string, SpecField> | null>(() => store.normalizedSpec as Record<string, SpecField> | null || store.parsedSpec as Record<string, SpecField> | null)
const alternatives = computed<Alternative[]>(() => store.alternatives as Alternative[])
const suppliers = computed<Supplier[]>(() => store.matchedSuppliers as Supplier[])
const selectedIds = computed(() => store.selectedSupplierIds)
const isSent = computed(() => store.rfqSent)
const isStreaming = computed(() => false)

onMounted(async () => {
  const sessionId = route.query.session as string | undefined
  if (sessionId && !rfqDoc.value) {
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
function onUpdate(text: string) { store.setRfqDoc(text) }
function onSent() { store.markRfqSent() }
function onRegenerate() { store.regenerateRfq() }
</script>

<template>
  <div class="rfq-page">
    <header class="rfq-page__head">
      <div>
        <h1>询价单</h1>
        <p class="rfq-page__sub">RFQ 文档编辑与发送</p>
      </div>
      <AppButton @click="goBack">返回对话</AppButton>
    </header>

    <div v-if="loading" class="rfq-page__loading">
      <span class="rfq-page__spinner" /><span>加载会话中…</span>
    </div>
    <div v-else-if="error" class="rfq-page__error">
      <p>{{ error }}</p>
      <AppButton @click="goBack">返回对话</AppButton>
    </div>
    <div v-else-if="rfqDoc" class="rfq-page__content">
      <RfqEditor
        :rfq-doc="rfqDoc"
        :rfq-id="rfqId"
        :spec="spec"
        :alternatives="alternatives"
        :suppliers="suppliers"
        :selected-supplier-ids="selectedIds"
        :sent="isSent"
        :streaming="isStreaming"
        @update="onUpdate"
        @sent="onSent"
        @regenerate="onRegenerate"
      />
    </div>
    <div v-else class="rfq-page__empty">
      <div class="rfq-page__empty-icon">⊘</div>
      <p class="rfq-page__empty-title">暂无询价单</p>
      <p class="rfq-page__empty-desc">请先通过对话寻源生成 RFQ。</p>
      <AppButton @click="goBack">前往对话寻源</AppButton>
    </div>
  </div>
</template>

<style scoped>
.rfq-page {
  max-width: 960px;
  margin: 0 auto;
  padding: var(--space-6) var(--space-5);
}
.rfq-page__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}
.rfq-page__head h1 { font-size: var(--font-size-2xl); font-weight: 700; }
.rfq-page__sub { font-size: var(--font-size-sm); color: var(--text-tertiary); margin-top: var(--space-1); }
.rfq-page__loading { display: flex; align-items: center; justify-content: center; gap: var(--space-3); padding: var(--space-8); color: var(--text-tertiary); }
.rfq-page__spinner { width: 18px; height: 18px; border: 2px solid var(--accent-soft); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.rfq-page__error { text-align: center; padding: var(--space-8); color: var(--danger); }
.rfq-page__error p { margin-bottom: var(--space-4); font-size: var(--font-size-md); }
.rfq-page__empty { text-align: center; padding: var(--space-8); }
.rfq-page__empty-icon { font-size: 40px; color: var(--text-tertiary); margin-bottom: var(--space-3); }
.rfq-page__empty-title { font-size: var(--font-size-lg); font-weight: 600; color: var(--text-secondary); margin-bottom: var(--space-2); }
.rfq-page__empty-desc { font-size: var(--font-size-sm); color: var(--text-tertiary); margin-bottom: var(--space-4); max-width: 360px; margin-left: auto; margin-right: auto; }
</style>
