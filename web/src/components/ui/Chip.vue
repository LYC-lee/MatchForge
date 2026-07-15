<script setup lang="ts">
defineProps<{ label: string }>()
const emit = defineEmits<{ (e: 'click'): void }>()
</script>

<template>
  <button class="chip" @click="emit('click')">{{ label }}</button>
</template>

<style scoped>
.chip {
  display: inline-flex;
  align-items: center;
  height: 30px;
  padding: 0 12px;
  font-size: var(--font-size-sm);
  color: #c5cada;
  background: #151924;
  border: 1px solid #343a4d;
  border-radius: var(--radius-full);
  transition: all var(--transition-fast);
}
.chip:hover {
  color: #f4f7ff;
  border-color: var(--accent-border);
  background: var(--accent-soft);
}
</style>
