<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AppButton from '@/components/ui/AppButton.vue'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const account = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

function submit() {
  error.value = ''
  loading.value = true
  // mock:模拟一点网络延迟,演示 loading 态
  setTimeout(() => {
    const r = auth.login(account.value, password.value)
    loading.value = false
    if (r.ok) {
      const redirect = (route.query.redirect as string) || '/'
      router.push(redirect)
    } else {
      error.value = r.msg || '登录失败'
    }
  }, 400)
}

function demoLogin() {
  account.value = 'demo'
  password.value = 'demo'
  submit()
}
</script>

<template>
  <div class="login">
    <div class="login__glow" />
    <div class="login__card">
      <div class="login__brand">
        <span class="login__mark" />
        <span class="login__name">MatchForge · 智配</span>
      </div>

      <h1 class="login__title">登录</h1>
      <p class="login__sub">AI 元器件替代料寻源平台</p>

      <form class="login__form" @submit.prevent="submit">
        <label class="login__field">
          <span class="login__label">账号</span>
          <input
            v-model="account"
            type="text"
            class="login__input"
            placeholder="输入账号"
            autocomplete="username"
          />
        </label>
        <label class="login__field">
          <span class="login__label">密码</span>
          <input
            v-model="password"
            type="password"
            class="login__input"
            placeholder="输入密码"
            autocomplete="current-password"
          />
        </label>
        <p v-if="error" class="login__error">{{ error }}</p>
        <AppButton type="submit" size="lg" :loading="loading" :disabled="loading" class="login__submit">
          登录
        </AppButton>
        <button type="button" class="login__demo" @click="demoLogin">
          演示登录(一键体验)
        </button>
      </form>

      <p class="login__hint">Spike 演示版,任意账号密码均可登录,无需注册。</p>

      <div class="login__disclaimer">
        本平台为寻源辅助工具,替代料推荐仅供参考,最终可替代性须由工程师确认;
        供应商匹配为供应能力匹配,非实时库存/报价/交期承诺。
      </div>
    </div>
  </div>
</template>

<style scoped>
.login {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-5);
  position: relative;
  overflow: hidden;
  background: var(--bg-0);
}
.login__glow {
  position: absolute;
  width: 600px;
  height: 600px;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: radial-gradient(circle, rgba(99, 102, 241, 0.18) 0%, transparent 60%);
  pointer-events: none;
}

.login__card {
  position: relative;
  width: 100%;
  max-width: 380px;
  background: var(--bg-2);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  box-shadow: var(--shadow-lg);
}

.login__brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-6);
}
.login__mark {
  width: 24px;
  height: 24px;
  border-radius: var(--radius-sm);
  background: var(--gradient-accent);
}
.login__name { font-weight: 700; font-size: var(--font-size-md); color: var(--text-primary); }

.login__title { font-size: var(--font-size-2xl); font-weight: 700; margin-bottom: var(--space-1); }
.login__sub { font-size: var(--font-size-sm); color: var(--text-tertiary); margin-bottom: var(--space-5); }

.login__form { display: flex; flex-direction: column; gap: var(--space-3); }
.login__field { display: flex; flex-direction: column; gap: var(--space-1); }
.login__label { font-size: var(--font-size-xs); color: var(--text-tertiary); font-weight: 500; }
.login__input {
  background: var(--bg-3);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: 10px 12px;
  font-size: var(--font-size-sm);
  color: var(--text-primary);
  outline: none;
  transition: border-color var(--transition-fast);
}
.login__input:focus { border-color: var(--accent); }
.login__input::placeholder { color: var(--text-tertiary); }

.login__error {
  font-size: var(--font-size-xs);
  color: var(--danger);
  background: var(--danger-soft);
  padding: 6px 10px;
  border-radius: var(--radius-sm);
}

.login__submit { width: 100%; margin-top: var(--space-2); }
.login__demo {
  width: 100%;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  padding: 8px;
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
}
.login__demo:hover { color: var(--accent-hover); background: var(--accent-soft); }

.login__hint {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  text-align: center;
  margin-top: var(--space-4);
}

.login__disclaimer {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  line-height: 1.6;
  margin-top: var(--space-4);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-subtle);
}
</style>
