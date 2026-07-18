<script setup lang="ts">
import { computed } from 'vue'

/**
 * 骨架屏占位。
 * 用法：
 *   <Skeleton />                       单行文本
 *   <Skeleton :lines="3" />            多行文本
 *   <Skeleton height="80px" />         卡片/图表块
 *   <Skeleton circle size="32px" />    头像
 */
const props = withDefaults(defineProps<{
  /** 文本行数（>1 时渲染多行，末行缩短 40%） */
  lines?: number
  width?: string
  height?: string
  /** 圆形模式（头像/图标位） */
  circle?: boolean
  /** 圆形直径 */
  size?: string
}>(), {
  lines: 1,
})

const rows = computed(() => Array.from({ length: Math.max(1, props.lines) }, (_, i) => i))
</script>

<template>
  <div class="skeleton-wrap" aria-hidden="true">
    <div
      v-for="i in rows"
      :key="i"
      class="skeleton"
      :class="{ 'skeleton--circle': circle }"
      :style="
        circle
          ? { width: size ?? '32px', height: size ?? '32px' }
          : {
              width: width ?? (lines > 1 && i === rows.length - 1 ? '60%' : '100%'),
              height: height ?? '14px',
            }
      "
    />
  </div>
</template>

<style scoped>
.skeleton-wrap {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.skeleton {
  background: linear-gradient(
    90deg,
    var(--bg-subtle) 25%,
    var(--border-subtle) 50%,
    var(--bg-subtle) 75%
  );
  background-size: 200% 100%;
  animation: sk-shimmer 1.5s infinite;
  border-radius: var(--radius-sm);
}
.skeleton--circle {
  border-radius: var(--radius-full);
}
@keyframes sk-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
