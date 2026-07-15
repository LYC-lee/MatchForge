<script setup lang="ts">
import { ref } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'
import Chip from '@/components/ui/Chip.vue'

const props = defineProps<{ initial?: string }>()
const emit = defineEmits<{ (e: 'submit', query: string): void }>()

const query = ref(props.initial || '')

const examples = [
  'TMK212BJ105KG-T 缺货,找替代',
  '0805 10uF X7R 50V,月用量50万,要国巨或华新科',
  '帮我生成 MLCC 替代料询价单',
]

function useExample(ex: string) {
  query.value = ex
}

function submit() {
  const q = query.value.trim()
  if (!q) return
  emit('submit', q)
}
</script>

<template>
  <div class="query">
    <div class="query__box">
      <textarea
        v-model="query"
        class="query__input"
        rows="3"
        placeholder="输入型号或描述需求,如 TMK212BJ105KG-T 缺货找替代"
        @keydown.meta.enter="submit"
        @keydown.ctrl.enter="submit"
      />
      <div class="query__bar">
        <span class="query__hint">⌘/Ctrl + Enter 提交</span>
        <AppButton size="md" :disabled="!query.trim()" @click="submit">
          开始寻源
        </AppButton>
      </div>
    </div>
    <div class="query__examples">
      <span class="query__ex-label">试试:</span>
      <Chip
        v-for="ex in examples"
        :key="ex"
        :label="ex"
        @click="useExample(ex)"
      />
    </div>
  </div>
</template>

<style scoped>
.query {
  width: 100%;
  max-width: 720px;
  margin: 0;
}
.query__box {
  background: #151924;
  border: 1px solid #343a4d;
  border-radius: 12px;
  transition: border-color var(--transition-base), box-shadow var(--transition-base);
}
.query__box:focus-within {
  border-color: var(--accent-border);
  box-shadow: var(--shadow-glow);
}
.query__input {
  display: block;
  width: 100%;
  background: transparent;
  border: none;
  outline: none;
  padding: var(--space-4) var(--space-5);
  font-size: var(--font-size-md);
  color: #f4f7ff;
  resize: none;
}
.query__input::placeholder { color: #7f8799; }
.query__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--border-subtle);
}
.query__hint { font-size: var(--font-size-xs); color: #8d95aa; }
.query__examples {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-4);
}
.query__ex-label { font-size: var(--font-size-sm); color: #9aa3b7; }
</style>
