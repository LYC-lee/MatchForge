<script setup lang="ts">
/**
 * 认证页布局骨架（登录/注册共用）：左故事面板 + 右表单面板。
 * 表单面板独立滚动，矮视口不会裁切表单；<=920px 折叠为单列（隐藏故事面板）。
 *
 * 用法：
 *   <AuthLayout brand="MatchForge 智配">
 *     <template #story>
 *       <h1>AI 替代料寻源</h1><p>卖点文案 / 数据可视化 / 客户证言…</p>
 *     </template>
 *     <LoginForm />
 *   </AuthLayout>
 */
withDefaults(defineProps<{
  /** 品牌名（故事面板顶部，logo 旁） */
  brand?: string
}>(), {
  brand: 'MatchForge 智配',
})
</script>

<template>
  <div class="auth">
    <aside class="auth__story">
      <div class="auth__brand">
        <span class="auth__logo" aria-hidden="true">MF</span>
        <span class="auth__brand-name">{{ brand }}</span>
      </div>
      <div class="auth__story-body">
        <slot name="story" />
      </div>
    </aside>
    <main class="auth__panel">
      <div class="auth__form">
        <slot />
      </div>
    </main>
  </div>
</template>

<style scoped>
.auth {
  display: grid;
  grid-template-columns: minmax(400px, 5fr) 7fr;
  min-height: 100vh;
  background: var(--bg-canvas);
}

/* 左：故事面板（允许使用 --gradient-accent 之外无渐变；仅品牌叙事） */
.auth__story {
  display: flex;
  flex-direction: column;
  padding: var(--space-6);
  background: var(--bg-subtle);
  border-right: 1px solid var(--border-subtle);
  overflow: hidden;
}
.auth__brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.auth__logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  font-weight: 700;
  color: var(--on-accent);
  background: var(--gradient-accent);
  border-radius: var(--radius-md);
}
.auth__brand-name {
  font-size: var(--font-size-md);
  line-height: var(--leading-md);
  font-weight: 600;
  color: var(--text-primary);
}
.auth__story-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: var(--space-4);
  min-height: 0;
  overflow-y: auto;
}

/* 右：表单面板（独立滚动，矮视口防裁切） */
.auth__panel {
  overflow-y: auto;
  max-height: 100vh;
}
.auth__form {
  width: 100%;
  max-width: 400px;
  margin: 0 auto;
  padding: var(--space-8) var(--space-5);
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 100%;
}

@media (max-width: 920px) {
  .auth {
    grid-template-columns: 1fr;
  }
  .auth__story {
    display: none;
  }
}
</style>
