<script setup lang="ts">
withDefaults(defineProps<{
  /** primary 实心主色（配给制，一屏至多一个）/ secondary 描边 / ghost 无框 / danger 危险操作 */
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  /** 标准档位 sm/md；lg 仅为存量兼容保留，新代码勿用 */
  size?: 'sm' | 'md' | 'lg'
  disabled?: boolean
  loading?: boolean
  type?: 'button' | 'submit' | 'reset'
}>(), {
  variant: 'primary',
  size: 'md',
  disabled: false,
  loading: false,
  type: 'button',
})
</script>

<template>
  <button
    :type="type"
    class="btn"
    :class="[`btn--${variant}`, `btn--${size}`, { 'is-loading': loading }]"
    :disabled="disabled || loading"
  >
    <span v-if="loading" class="btn__spinner" aria-hidden="true" />
    <slot />
  </button>
</template>

<style scoped>
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  font-weight: 500;
  white-space: nowrap;
  transition: background-color var(--transition-fast), border-color var(--transition-fast),
    color var(--transition-fast);
}
.btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.btn--sm {
  height: 28px;
  padding: 0 10px;
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
}
.btn--md {
  height: 32px;
  padding: 0 14px;
  font-size: var(--font-size-base);
  line-height: var(--leading-base);
}
.btn--lg {
  height: 40px;
  padding: 0 20px;
  font-size: var(--font-size-md);
  line-height: var(--leading-md);
}

/* primary：accent 纯色（禁渐变），文字用 --on-accent */
.btn--primary {
  background: var(--accent);
  color: var(--on-accent);
}
.btn--primary:hover:not(:disabled) {
  background: var(--accent-hover);
}
.btn--primary:active:not(:disabled) {
  background: var(--accent-active);
}

/* secondary：surface 底 + 发丝描边 */
.btn--secondary {
  background: var(--bg-surface);
  color: var(--text-primary);
  border-color: var(--border-default);
}
.btn--secondary:hover:not(:disabled) {
  border-color: var(--border-strong);
  background: var(--bg-subtle);
}

/* ghost：无框低密度操作 */
.btn--ghost {
  background: transparent;
  color: var(--text-secondary);
}
.btn--ghost:hover:not(:disabled) {
  color: var(--text-primary);
  background: var(--bg-subtle);
}

/* danger：状态公式（色字 + soft 底 + border 边），hover 转实心 */
.btn--danger {
  background: var(--danger-soft);
  color: var(--danger);
  border-color: var(--danger-border);
}
.btn--danger:hover:not(:disabled) {
  background: var(--danger);
  border-color: var(--danger);
  color: var(--on-accent);
}

.btn__spinner {
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: var(--radius-full);
  opacity: 0.8;
  animation: btn-spin 0.6s linear infinite;
}
@keyframes btn-spin {
  to { transform: rotate(360deg); }
}
</style>
