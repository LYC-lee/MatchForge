<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="app">
    <header class="navbar">
      <RouterLink to="/" class="brand">MatchForge · 智配</RouterLink>
      <nav class="nav-links">
        <RouterLink to="/">首页</RouterLink>
        <RouterLink to="/rfq">智能寻源</RouterLink>
        <RouterLink to="/suppliers">供应商</RouterLink>
      </nav>
    </header>
    <main class="content">
      <RouterView />
    </main>
  </div>
</template>
