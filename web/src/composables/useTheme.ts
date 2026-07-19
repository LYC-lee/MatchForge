import { ref } from 'vue'

export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'mf-theme'

/** 当前生效主题（响应式，全站共享） */
export const currentTheme = ref<Theme>('light')

/** 用户是否手动选择过主题（localStorage 有记录即视为手动选择） */
const hasManualChoice = ref(false)

let mediaQuery: MediaQueryList | null = null
let mediaListener: ((e: MediaQueryListEvent) => void) | null = null

function readStored(): Theme | null {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    return v === 'light' || v === 'dark' ? v : null
  } catch {
    return null
  }
}

function systemTheme(): Theme {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

/** 应用主题到 documentElement（不写存储） */
function apply(theme: Theme) {
  currentTheme.value = theme
  document.documentElement.dataset.theme = theme
}

/** 手动设置主题并持久化（此后不再跟随系统偏好） */
export function setTheme(theme: Theme) {
  hasManualChoice.value = true
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    /* 隐私模式等场景降级为仅内存态 */
  }
  apply(theme)
}

/** 切换浅色/深色并持久化 */
export function toggleTheme() {
  setTheme(currentTheme.value === 'dark' ? 'light' : 'dark')
}

/**
 * 初始化主题：
 * - 用户手动选择过 → 应用存储值
 * - 未选择过 → 跟随系统偏好（默认 light），并监听系统偏好变化
 * 在 main.ts 中调用一次；index.html 内联脚本已先行应用，避免 FOUC。
 */
export function initTheme() {
  const stored = readStored()
  hasManualChoice.value = stored !== null
  apply(stored ?? systemTheme())

  if (!mediaQuery) {
    mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    mediaListener = (e: MediaQueryListEvent) => {
      if (!hasManualChoice.value) apply(e.matches ? 'dark' : 'light')
    }
    mediaQuery.addEventListener('change', mediaListener)
  }
}

/** 组合式入口：组件内 const { theme, toggle } = useTheme() */
export function useTheme() {
  return {
    theme: currentTheme,
    hasManualChoice,
    setTheme,
    toggle: toggleTheme,
  }
}
