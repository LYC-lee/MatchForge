<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import AppHeader from '@/components/layout/AppHeader.vue'

const route = useRoute()
// 登录页等标记 layout: 'blank' 的路由不显示顶栏
const showHeader = computed(() => route.meta.layout !== 'blank')
</script>

<template>
  <div class="app-shell">
    <AppHeader v-if="showHeader" />
    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
.app-main {
  flex: 1;
}
</style>
