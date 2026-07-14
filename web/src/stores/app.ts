import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface MatchResult {
  partName: string
  supplier: string
  stock: string
  score: number
}

export const useAppStore = defineStore('app', () => {
  // 用户输入的自然语言寻源需求
  const query = ref('')
  // AI 返回的匹配结果
  const results = ref<MatchResult[]>([])
  // 是否正在请求后端
  const loading = ref(false)

  function setQuery(q: string) {
    query.value = q
  }

  function setResults(r: MatchResult[]) {
    results.value = r
  }

  function reset() {
    query.value = ''
    results.value = []
  }

  return { query, results, loading, setQuery, setResults, reset }
})
