<script setup lang="ts">
import { ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const { query, results, loading } = storeToRefs(store)

const error = ref('')

async function submit() {
  if (!query.value.trim()) return
  loading.value = true
  error.value = ''
  store.setResults([])
  try {
    const res = await fetch('/api/rfq', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: query.value }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    store.setResults(data.results ?? [])
  } catch (e) {
    error.value = '寻源失败,请确认后端服务已启动(/api)。' + (e as Error).message
  } finally {
    loading.value = false
  }
}

function scoreColor(score: number) {
  if (score >= 0.8) return 'high'
  if (score >= 0.5) return 'mid'
  return 'low'
}
</script>

<template>
  <section class="rfq">
    <h2>智能寻源</h2>
    <p class="hint">
      用自然语言描述你的元器件需求,例如:100uF 16V 铝电解电容,贴片封装,工作温度 -40~105℃
    </p>

    <textarea
      v-model="query"
      rows="4"
      placeholder="描述你的元器件需求..."
      @keydown.ctrl.enter="submit"
    />

    <div class="actions">
      <button class="btn-primary" :disabled="loading" @click="submit">
        {{ loading ? 'AI 寻源中...' : '开始寻源' }}
      </button>
      <span class="shortcut">Ctrl + Enter 提交</span>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="results.length" class="results">
      <h3>匹配结果 ({{ results.length }})</h3>
      <table>
        <thead>
          <tr><th>型号</th><th>供应商</th><th>库存</th><th>匹配度</th></tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in results" :key="i">
            <td>{{ r.partName }}</td>
            <td>{{ r.supplier }}</td>
            <td>{{ r.stock }}</td>
            <td>
              <span class="score" :class="scoreColor(r.score)">
                {{ (r.score * 100).toFixed(0) }}%
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
