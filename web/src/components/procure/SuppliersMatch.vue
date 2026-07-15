<script setup lang="ts">
import { computed } from 'vue'
import type { Supplier } from '@/types/procure'
import Card from '@/components/ui/Card.vue'
import AppButton from '@/components/ui/AppButton.vue'

const props = defineProps<{
  suppliers: Supplier[]
  selectedIds: Set<string>
}>()
const emit = defineEmits<{
  (e: 'toggle', id: string): void
  (e: 'generate'): void
}>()

const selectedCount = computed(() => props.selectedIds.size)
</script>

<template>
  <div class="sups">
    <div class="sups__notice">
      <span class="sups__notice-icon">ⓘ</span>
      <span>
        以下为<b>供应能力匹配</b>,非实时库存、报价或交期承诺,最终以供应商正式确认为准。
        本平台首期不提供交易、支付与物流服务。
      </span>
    </div>

    <div class="sups__list">
      <Card
        v-for="s in suppliers"
        :key="s.id"
        :elevated="selectedIds.has(s.id)"
      >
        <template #header>
          <label class="sup__head" :class="{ 'is-selected': selectedIds.has(s.id) }">
            <input
              type="checkbox"
              class="sup__check"
              :checked="selectedIds.has(s.id)"
              @change="emit('toggle', s.id)"
            />
            <span class="sup__name">{{ s.name }}</span>
            <span
              class="sup__score"
              :class="{ high: s.match_score >= 0.8, mid: s.match_score >= 0.65 && s.match_score < 0.8, low: s.match_score < 0.65 }"
            >
              匹配度 {{ Math.round(s.match_score * 100) }}%
            </span>
          </label>
        </template>

        <div class="sup__grid">
          <div class="sup__field"><span>地区</span><b>{{ s.region }}</b></div>
          <div class="sup__field"><span>经营品类</span><b>{{ s.categories.join(' / ') }}</b></div>
          <div class="sup__field"><span>品牌覆盖</span><b>{{ s.brands.join(' / ') }}</b></div>
          <div class="sup__field"><span>资质</span><b>{{ s.qualifications.length ? s.qualifications.join(' / ') : '未验证' }}</b></div>
          <div class="sup__field"><span>MOQ</span><b>{{ s.moq.toLocaleString() }} pcs</b></div>
          <div class="sup__field"><span>历史响应</span><b>{{ s.response_speed }}</b></div>
        </div>

        <div class="sup__confirm">
          <span class="sup__confirm-label">库存 / 交期 / 价格确认:</span>
          <span class="sup__confirm-val">均未确认(能力匹配,非实时承诺)</span>
        </div>
        <div class="sup__source">
          <span>数据来源:{{ s.data_source }}</span>
          <span>更新:{{ s.updated_at }}</span>
        </div>
      </Card>
    </div>

    <div class="sups__foot">
      <span class="sups__selected">已选 {{ selectedCount }} 家供应商</span>
      <AppButton size="lg" :disabled="!selectedCount" @click="emit('generate')">
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
.sups__notice-icon { font-size: 16px; }

.sups__list { display: flex; flex-direction: column; gap: var(--space-3); }

.sup__head { display: flex; align-items: center; gap: var(--space-3); cursor: pointer; width: 100%; }
.sup__check { width: 16px; height: 16px; accent-color: var(--accent); cursor: pointer; }
.sup__name { font-size: var(--font-size-md); font-weight: 600; color: var(--text-primary); }
.sup__score { margin-left: auto; font-size: var(--font-size-xs); font-weight: 600; padding: 3px 8px; border-radius: var(--radius-sm); font-family: var(--font-mono); }
.sup__score.high { color: var(--success); background: var(--success-soft); }
.sup__score.mid { color: var(--warning); background: var(--warning-soft); }
.sup__score.low { color: var(--text-tertiary); background: var(--bg-3); }
.is-selected .sup__name { color: var(--accent-hover); }

.sup__grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.sup__field { display: flex; flex-direction: column; gap: 2px; }
.sup__field span { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.sup__field b { font-size: var(--font-size-sm); color: var(--text-secondary); font-weight: 500; }

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
.sup__confirm-val { color: var(--text-secondary); }

.sup__source { display: flex; gap: var(--space-4); font-size: var(--font-size-xs); color: var(--text-tertiary); }

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
.sups__selected { font-size: var(--font-size-sm); color: var(--text-secondary); }

@media (max-width: 640px) {
  .sup__grid { grid-template-columns: 1fr; }
}
</style>
