<script setup lang="ts">
import { RouterLink, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <header class="header">
    <div class="header__inner">
      <RouterLink to="/" class="brand">
        <span class="brand__mark" />
        <span class="brand__name">MatchForge</span>
        <span class="brand__sub">智配</span>
      </RouterLink>
      <nav class="nav">
        <RouterLink to="/" class="nav__link">寻源</RouterLink>
        <RouterLink to="/history" class="nav__link">历史记录</RouterLink>
      </nav>
      <div class="header__right">
        <span v-if="auth.user" class="user">
          <span class="user__avatar">{{ auth.user.name.slice(0, 1).toUpperCase() }}</span>
          <span class="user__name">{{ auth.user.name }}</span>
        </span>
        <button class="logout" @click="logout">退出</button>
      </div>
    </div>
  </header>
</template>

<style scoped>
.header {
  position: sticky;
  top: 0;
  z-index: 50;
  background: rgba(15, 17, 23, 0.82);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-default);
}
.header__inner {
  max-width: 1200px;
  margin: 0 auto;
  height: 56px;
  padding: 0 var(--space-5);
  display: flex;
  align-items: center;
  gap: var(--space-6);
}
.brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-primary);
}
.brand__mark {
  width: 20px;
  height: 20px;
  border-radius: var(--radius-sm);
  background: var(--gradient-accent);
}
.brand__name { font-weight: 700; font-size: var(--font-size-md); }
.brand__sub { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.nav { display: flex; gap: var(--space-1); }
.nav__link {
  padding: 6px 12px;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
}
.nav__link:hover { color: var(--text-primary); background: var(--bg-3); }
.nav__link.router-link-exact-active { color: var(--text-primary); background: var(--bg-3); }

.header__right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.user {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.user__avatar {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--gradient-accent);
  color: #fff;
  font-size: var(--font-size-xs);
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.user__name { font-size: var(--font-size-sm); color: var(--text-secondary); }
.logout {
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
  padding: 5px 10px;
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
}
.logout:hover { color: var(--danger); background: var(--danger-soft); }
</style>
