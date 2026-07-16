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
    <DemoConsole v-if="showHeader" />
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(circle at 20% 0%, rgba(99, 102, 241, 0.11), transparent 28%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.02), rgba(255, 255, 255, 0)),
    var(--bg-0);
}
.app-main {
  flex: 1;
  min-height: 100vh;
  padding-top: 56px;
  padding-left: 256px;
}
.app-main--blank {
  padding: 0;
}

@media (max-width: 920px) {
  .app-main {
    padding-left: 0;
    padding-top: 104px;
  }
}
</style>
