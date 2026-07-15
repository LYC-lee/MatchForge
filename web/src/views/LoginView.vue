<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
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
  setTimeout(() => {
    const r = auth.login(account.value, password.value)
    loading.value = false
    if (r.ok) {
      const redirect = (route.query.redirect as string) || '/app'
      router.push(redirect)
    } else {
      error.value = r.msg || '登录失败'
    }
  }, 300)
}

function demoLogin() {
  account.value = 'demo@matchforge.ai'
  password.value = 'demo12345'
  submit()
}

function switchAccount() {
  auth.logout()
  account.value = ''
  password.value = ''
  error.value = ''
}
</script>

<template>
  <div class="auth-page">
    <section class="auth-story">
      <div class="auth-brand">
        <span class="auth-brand__mark" />
        <span class="auth-brand__text">MatchForge · 智配</span>
      </div>
      <p class="auth-story__eyebrow">AI Sourcing Workspace</p>
      <h1 class="auth-story__title">把缺货寻源拆成可追踪的采购工作流</h1>
      <p class="auth-story__copy">
        规格解析、替代料分级、供应商能力匹配和 RFQ 生成被清晰分隔在一个 Linear 风格工作台里。
      </p>
      <div class="auth-story__metrics">
        <div><b>6</b><span>智能体阶段</span></div>
        <div><b>L1-L5</b><span>替代风险分级</span></div>
        <div><b>RFQ</b><span>可编辑询价单</span></div>
      </div>
    </section>

    <section class="auth-panel">
      <div class="auth-card">
        <RouterLink to="/" class="auth-back">← 返回产品介绍</RouterLink>
        <div class="auth-brand auth-card__brand">
          <span class="auth-brand__mark" />
          <span class="auth-brand__text">MatchForge · 智配</span>
        </div>

        <h2 class="auth-card__title">登录</h2>
        <p class="auth-card__sub">进入 AI 元器件替代料寻源工作台</p>

        <div v-if="auth.isAuthenticated" class="auth-session">
          <span class="auth-session__avatar">{{ auth.user?.name.slice(0, 1).toUpperCase() }}</span>
          <div>
            <b>已登录：{{ auth.user?.name }}</b>
            <p>{{ auth.user?.account }}</p>
          </div>
          <RouterLink to="/app" class="auth-session__cta">进入工作台</RouterLink>
          <button type="button" class="auth-session__switch" @click="switchAccount">切换账号</button>
        </div>

        <form v-else class="auth-form" @submit.prevent="submit">
          <label class="auth-field">
            <span class="auth-field__label">账号</span>
            <input
              v-model="account"
              type="text"
              class="auth-input"
              placeholder="name@company.com"
              autocomplete="username"
            />
          </label>
          <label class="auth-field">
            <span class="auth-field__label">密码</span>
            <input
              v-model="password"
              type="password"
              class="auth-input"
              placeholder="输入密码"
              autocomplete="current-password"
            />
          </label>
          <p v-if="error" class="auth-error">{{ error }}</p>
          <AppButton type="submit" size="lg" :loading="loading" :disabled="loading" class="auth-submit">
            登录
          </AppButton>
          <button type="button" class="auth-demo" @click="demoLogin">
            使用演示账号登录
          </button>
        </form>

        <p class="auth-hint">
          还没有账号?
          <RouterLink to="/register">创建采购工作台</RouterLink>
        </p>

        <div class="auth-disclaimer">
          演示账号：demo@matchforge.ai / demo12345。本地 mock 认证仅用于 Spike 演示，生产环境应由后端签发 HttpOnly Cookie 或短期 Token。
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 440px;
  overflow: hidden;
  background:
    radial-gradient(circle at 22% 22%, rgba(99, 102, 241, 0.22), transparent 28%),
    linear-gradient(90deg, rgba(255, 255, 255, 0.035) 1px, transparent 1px),
    linear-gradient(180deg, rgba(255, 255, 255, 0.035) 1px, transparent 1px),
    var(--bg-0);
  background-size: auto, 48px 48px, 48px 48px, auto;
}
.auth-story {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: clamp(40px, 8vw, 96px);
  border-right: 1px solid var(--border-default);
}
.auth-brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.auth-brand__mark {
  width: 26px;
  height: 26px;
  border-radius: var(--radius-md);
  background: var(--gradient-accent);
  box-shadow: 0 0 28px rgba(99, 102, 241, 0.24);
}
.auth-brand__text {
  color: #f4f7ff;
  font-weight: 700;
}
.auth-story .auth-brand {
  margin-bottom: var(--space-8);
}
.auth-story__eyebrow {
  margin-bottom: var(--space-3);
  color: var(--accent-hover);
  font-size: var(--font-size-xs);
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}
.auth-story__title {
  max-width: 680px;
  color: #f4f7ff;
  font-size: clamp(36px, 6vw, 64px);
  line-height: 1.04;
  letter-spacing: -0.05em;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.04);
}
.auth-story__copy {
  max-width: 560px;
  margin-top: var(--space-5);
  color: #c2c7d4;
  font-size: var(--font-size-lg);
}
.auth-story__metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
  max-width: 680px;
  margin-top: var(--space-8);
}
.auth-story__metrics div {
  position: relative;
  overflow: hidden;
  min-height: 86px;
  padding: var(--space-4);
  border: 1px solid rgba(129, 140, 248, 0.34);
  border-radius: 12px;
  background:
    radial-gradient(circle at 12% 16%, rgba(129, 140, 248, 0.22), transparent 34%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.075), rgba(255, 255, 255, 0.028)),
    #121622;
  box-shadow: 0 12px 34px rgba(0, 0, 0, 0.28);
}
.auth-story__metrics div::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  background: var(--gradient-accent);
}
.auth-story__metrics div::after {
  content: '';
  position: absolute;
  right: 12px;
  top: 12px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(129, 140, 248, 0.24);
  box-shadow: 0 0 26px rgba(129, 140, 248, 0.3);
}
.auth-story__metrics b {
  display: block;
  margin-bottom: var(--space-1);
  font-family: var(--font-mono);
  color: #f4f7ff;
  font-size: var(--font-size-xl);
  line-height: 1.1;
}
.auth-story__metrics span {
  color: #c5cada;
  font-size: var(--font-size-sm);
  line-height: 1.45;
}
.auth-panel {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-5);
}
.auth-card {
  width: 100%;
  max-width: 380px;
  padding: var(--space-6);
  border: 1px solid #343a4d;
  border-radius: 14px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.045), rgba(255, 255, 255, 0.015)),
    #10131b;
  box-shadow: var(--shadow-lg);
}
.auth-back {
  display: inline-flex;
  margin-bottom: var(--space-5);
  color: #aeb5c4;
  font-size: var(--font-size-sm);
}
.auth-back:hover {
  color: #f4f7ff;
}
.auth-card__brand {
  margin-bottom: var(--space-6);
}
.auth-card__title {
  margin-bottom: var(--space-1);
  color: #f4f7ff;
  font-size: var(--font-size-2xl);
}
.auth-card__sub {
  margin-bottom: var(--space-5);
  color: #aeb5c4;
  font-size: var(--font-size-sm);
}
.auth-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.auth-session {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: var(--space-3);
  padding: var(--space-4);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.045);
}
.auth-session__avatar {
  width: 42px;
  height: 42px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: #fff;
  background: var(--gradient-accent);
  font-weight: 700;
}
.auth-session b {
  display: block;
  color: #f4f7ff;
  font-size: var(--font-size-sm);
}
.auth-session p {
  margin-top: 2px;
  color: #aeb5c4;
  font-size: var(--font-size-xs);
}
.auth-session__cta,
.auth-session__switch {
  grid-column: 1 / -1;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  font-weight: 600;
}
.auth-session__cta {
  color: #fff;
  background: var(--accent);
}
.auth-session__switch {
  color: #c5cada;
  background: #151924;
  border: 1px solid #343a4d;
}
.auth-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.auth-field__label {
  color: #c5cada;
  font-size: var(--font-size-xs);
  font-weight: 600;
}
.auth-input {
  height: 40px;
  padding: 0 12px;
  color: #f4f7ff;
  background: #151924;
  border: 1px solid #343a4d;
  border-radius: var(--radius-md);
  outline: none;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.auth-input:focus {
  border-color: var(--accent-border);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
.auth-input::placeholder {
  color: #7f8799;
}
.auth-error {
  padding: 6px 10px;
  color: var(--danger);
  background: var(--danger-soft);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
}
.auth-submit {
  width: 100%;
  margin-top: var(--space-2);
}
.auth-demo {
  width: 100%;
  padding: 8px;
  color: #c5cada;
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  transition: all var(--transition-fast);
}
.auth-demo:hover {
  color: #f4f7ff;
  background: var(--accent-soft);
}
.auth-hint {
  margin-top: var(--space-4);
  text-align: center;
  color: #aeb5c4;
  font-size: var(--font-size-xs);
}
.auth-hint a {
  font-weight: 700;
}
.auth-disclaimer {
  margin-top: var(--space-4);
  padding-top: var(--space-4);
  color: #9aa3b7;
  border-top: 1px solid var(--border-subtle);
  font-size: var(--font-size-xs);
  line-height: 1.6;
}

@media (max-width: 960px) {
  .auth-page {
    grid-template-columns: 1fr;
  }
  .auth-story {
    display: none;
  }
}
</style>
