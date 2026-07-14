<script setup lang="ts">
withDefaults(defineProps<{
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  disabled?: boolean
  loading?: boolean
}>(), {
  variant: 'primary',
  size: 'md',
  disabled: false,
  loading: false,
})
</script>

<template>
  <button
    class="btn"
    :class="[`btn--${variant}`, `btn--${size}`, { 'is-disabled': disabled, 'is-loading': loading }]"
    :disabled="disabled || loading"
  >
    <span v-if="loading" class="spinner" />
    <slot />
  </button>
</template>

<style scoped>
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  border-radius: var(--radius-md);
  font-weight: 500;
  white-space: nowrap;
  transition: all var(--transition-fast);
  border: 1px solid transparent;
}
.btn--sm { font-size: var(--font-size-sm); padding: 5px 10px; height: 28px; }
.btn--md { font-size: var(--font-size-base); padding: 7px 14px; height: 34px; }
.btn--lg { font-size: var(--font-size-md); padding: 10px 20px; height: 42px; }

.btn--primary { background: var(--accent); color: #fff; }
.btn--primary:hover:not(.is-disabled) { background: var(--accent-hover); }
.btn--primary:active:not(.is-disabled) { background: var(--accent-active); }

.btn--secondary {
  background: var(--bg-3);
  color: var(--text-primary);
  border-color: var(--border-default);
}
.btn--secondary:hover:not(.is-disabled) { border-color: var(--border-strong); background: var(--bg-elevated); }

.btn--ghost { background: transparent; color: var(--text-secondary); }
.btn--ghost:hover:not(.is-disabled) { color: var(--text-primary); background: var(--bg-3); }

.btn--danger {
  background: var(--danger-soft);
  color: var(--danger);
  border-color: rgba(239, 68, 68, 0.3);
}
.btn--danger:hover:not(.is-disabled) { background: rgba(239, 68, 68, 0.2); }

.is-disabled { opacity: 0.45; cursor: not-allowed; }
.is-loading { cursor: progress; }

.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
