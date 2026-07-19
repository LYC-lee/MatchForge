<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import AppHeader from '@/components/layout/AppHeader.vue'
import DemoConsole from '@/components/demo/DemoConsole.vue'

const route = useRoute()
const blankPaths = new Set(['/', '/login', '/register'])
const showHeader = computed(() => route.meta.layout !== 'blank' && !blankPaths.has(route.path))
</script>

<template>
  <div class="app-shell">
    <AppHeader v-if="showHeader" />
    <main class="app-main" :class="{ 'app-main--blank': !showHeader }">
      <RouterView />
    </main>
    <!-- 演示场景悬浮控制台（仅 demo 登录用户可见，可拖拽） -->
    <DemoConsole />
  </div>
</template>

<style scoped>
.app-shell {
  /* 侧栏宽度为外壳级布局常量，AppHeader 通过继承该变量保持对齐 */
  --sidebar-w: 256px;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-canvas);
}
.app-main {
  flex: 1;
  min-height: 100vh;
  padding-top: var(--header-h);
  padding-left: var(--sidebar-w);
}
.app-main--blank {
  padding: 0;
}

/* ≤920px：侧栏折叠为顶部横条 + 顶栏，共两层 --header-h */
@media (max-width: 920px) {
  .app-main {
    padding-left: 0;
    padding-top: calc(var(--header-h) * 2);
  }
}
</style>
