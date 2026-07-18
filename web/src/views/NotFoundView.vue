<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import EmptyState from '@/components/ui/EmptyState.vue'
import AppButton from '@/components/ui/AppButton.vue'
import { useAuthStore } from '@/stores/auth'
import { homePathForRole } from '@/router'

const router = useRouter()
const auth = useAuthStore()

/** 回到当前角色有权限的首页（未登录按采购方首页，守卫会再引导去登录） */
const homePath = computed(() => homePathForRole(auth.user?.role))

function goHome() {
  router.push(homePath.value)
}
</script>

<template>
  <div class="not-found">
    <EmptyState title="页面不存在" description="你访问的地址有误，或该页面已被移除。">
      <template #icon>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="9" />
          <path d="M9 9.5a3 3 0 0 1 5.8 1c0 2-2.8 2.3-2.8 4" />
          <circle cx="12" cy="17.5" r="0.5" fill="currentColor" />
        </svg>
      </template>
      <template #action>
        <AppButton variant="secondary" @click="goHome">返回首页</AppButton>
      </template>
    </EmptyState>
  </div>
</template>

<style scoped>
.not-found {
  min-height: 60vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
