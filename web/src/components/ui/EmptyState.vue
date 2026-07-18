<script setup lang="ts">
/**
 * 空状态。
 * 用法：
 *   <EmptyState title="暂无历史记录" description="发起一次寻源后会出现在这里">
 *     <template #icon><SomeIcon /></template>
 *     <template #action><AppButton @click="go">去寻源</AppButton></template>
 *   </EmptyState>
 */
withDefaults(defineProps<{
  title?: string
  description?: string
  /** 紧凑模式：减小留白（卡片内嵌空态） */
  compact?: boolean
}>(), {
  title: '暂无数据',
  compact: false,
})
</script>

<template>
  <div class="empty" :class="{ 'empty--compact': compact }">
    <div v-if="$slots.icon" class="empty__icon"><slot name="icon" /></div>
    <p class="empty__title">{{ title }}</p>
    <p v-if="description" class="empty__desc">{{ description }}</p>
    <div v-if="$slots.action" class="empty__action"><slot name="action" /></div>
  </div>
</template>

<style scoped>
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: var(--space-8) var(--space-5);
}
.empty--compact {
  padding: var(--space-5) var(--space-4);
}
.empty__icon {
  color: var(--text-tertiary);
  opacity: 0.5;
  margin-bottom: var(--space-3);
}
.empty__icon :deep(svg) {
  width: 32px;
  height: 32px;
}
.empty__title {
  font-size: var(--font-size-base);
  line-height: var(--leading-base);
  font-weight: 500;
  color: var(--text-secondary);
}
.empty__desc {
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  color: var(--text-tertiary);
  margin-top: var(--space-1);
  max-width: 320px;
}
.empty__action {
  margin-top: var(--space-4);
}
</style>
