<script setup lang="ts">
import { useTheme } from '@/composables/useTheme'

/** 主题切换按钮（日/月 inline SVG，1.5px stroke） */
const { theme, toggle } = useTheme()
</script>

<template>
  <button
    type="button"
    class="theme-toggle"
    :title="theme === 'dark' ? '切换为浅色模式' : '切换为深色模式'"
    :aria-label="theme === 'dark' ? '切换为浅色模式' : '切换为深色模式'"
    :aria-pressed="theme === 'dark'"
    @click="toggle"
  >
    <!-- 太阳（深色模式下显示，点击回到浅色） -->
    <svg
      v-if="theme === 'dark'"
      class="theme-toggle__icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="1.5"
      stroke-linecap="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32 1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
    </svg>
    <!-- 月亮（浅色模式下显示，点击切到深色） -->
    <svg
      v-else
      class="theme-toggle__icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="1.5"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79Z" />
    </svg>
  </button>
</template>

<style scoped>
.theme-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  color: var(--text-secondary);
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  transition: color var(--transition-fast), background-color var(--transition-fast),
    border-color var(--transition-fast);
}
.theme-toggle:hover {
  color: var(--text-primary);
  background: var(--bg-subtle);
  border-color: var(--border-default);
}
.theme-toggle__icon {
  width: 18px;
  height: 18px;
}
</style>
