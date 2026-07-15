<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useAuthStore, type AuthUser } from '@/stores/auth'
import AppButton from '@/components/ui/AppButton.vue'

const router = useRouter()
const auth = useAuthStore()

const name = ref('')
const company = ref('')
const account = ref('')
const password = ref('')
const confirmPassword = ref('')
const role = ref<AuthUser['role']>('buyer')
const error = ref('')
const loading = ref(false)

function submit() {
  error.value = ''
  if (password.value !== confirmPassword.value) {
    error.value = '两次输入的密码不一致'
    return
  }
  loading.value = true
  setTimeout(() => {
    const result = auth.register({
      name: name.value,
      company: company.value,
      account: account.value,
      password: password.value,
      role: role.value,
    })
    loading.value = false
    if (result.ok) {
      router.push('/app')
    } else {
      error.value = result.msg || '注册失败'
    }
  }, 300)
}
</script>

<template>
  <div class="register-page">
    <section class="register-story">
      <div class="register-brand">
        <span class="register-brand__mark" />
        <span class="register-brand__text">MatchForge · 智配</span>
      </div>
      <h1>创建你的采购寻源工作区</h1>
      <p>
        Spike 阶段注册为本地 mock 流程，后续可直接替换为 FastAPI 的 `/api/v1/auth/register`。
      </p>
      <div class="register-roadmap">
        <span>采购端 AI 寻源</span>
        <span>供应商能力匹配</span>
        <span>运营审核后台留白</span>
      </div>
    </section>

    <section class="register-panel">
      <div class="register-card">
        <RouterLink to="/" class="register-back">← 返回产品介绍</RouterLink>
        <div class="register-card__head">
          <h2>注册</h2>
          <p>创建本地演示账号，后续可替换为真实后端鉴权</p>
        </div>

        <div v-if="auth.isAuthenticated" class="register-session">
          <b>当前已登录：{{ auth.user?.name }}</b>
          <p>{{ auth.user?.account }}</p>
          <RouterLink to="/app" class="register-session__cta">进入工作台</RouterLink>
          <button type="button" class="register-session__switch" @click="auth.logout()">退出后注册新账号</button>
        </div>

        <form v-else class="register-form" @submit.prevent="submit">
          <div class="role-tabs" role="radiogroup" aria-label="账号角色">
            <button
              type="button"
              class="role-tab"
              :class="{ 'is-active': role === 'buyer' }"
              @click="role = 'buyer'"
            >
              采购方
            </button>
            <button
              type="button"
              class="role-tab"
              :class="{ 'is-active': role === 'supplier' }"
              @click="role = 'supplier'"
            >
              供应商
            </button>
          </div>

          <label class="register-field">
            <span>姓名</span>
            <input v-model="name" class="register-input" placeholder="李明" autocomplete="name" />
          </label>
          <label class="register-field">
            <span>公司</span>
            <input v-model="company" class="register-input" placeholder="深圳某硬件制造商" autocomplete="organization" />
          </label>
          <label class="register-field">
            <span>账号</span>
            <input v-model="account" class="register-input" placeholder="name@company.com" autocomplete="username" />
          </label>
          <label class="register-field">
            <span>密码</span>
            <input v-model="password" type="password" class="register-input" placeholder="至少 8 位，包含字母和数字" autocomplete="new-password" />
          </label>
          <label class="register-field">
            <span>确认密码</span>
            <input v-model="confirmPassword" type="password" class="register-input" placeholder="再次输入密码" autocomplete="new-password" />
          </label>

          <p v-if="error" class="register-error">{{ error }}</p>

          <AppButton type="submit" size="lg" :loading="loading" :disabled="loading" class="register-submit">
            创建工作台
          </AppButton>
          <p class="register-security">本地演示会话有效期 8 小时。生产环境建议使用后端密码哈希、CSRF 防护和 HttpOnly Cookie。</p>
        </form>

        <p class="register-hint">
          已有账号?
          <RouterLink to="/login">返回登录</RouterLink>
        </p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.register-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(0, 0.82fr) minmax(420px, 0.58fr);
  background:
    radial-gradient(circle at 18% 15%, rgba(99, 102, 241, 0.2), transparent 28%),
    linear-gradient(90deg, rgba(255, 255, 255, 0.035) 1px, transparent 1px),
    linear-gradient(180deg, rgba(255, 255, 255, 0.035) 1px, transparent 1px),
    var(--bg-0);
  background-size: auto, 48px 48px, 48px 48px, auto;
}
.register-story {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: clamp(40px, 8vw, 96px);
  border-right: 1px solid var(--border-default);
}
.register-brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-8);
}
.register-brand__mark {
  width: 26px;
  height: 26px;
  border-radius: var(--radius-md);
  background: var(--gradient-accent);
}
.register-brand__text {
  color: #f4f7ff;
  font-weight: 700;
}
.register-story h1 {
  max-width: 640px;
  color: #f4f7ff;
  font-size: clamp(36px, 5vw, 58px);
  line-height: 1.05;
  letter-spacing: -0.05em;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.04);
}
.register-story p {
  max-width: 520px;
  margin-top: var(--space-5);
  color: #c2c7d4;
  font-size: var(--font-size-lg);
}
.register-roadmap {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-8);
}
.register-roadmap span {
  position: relative;
  padding: 8px 12px 8px 28px;
  color: #edf1f8;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.075), rgba(255, 255, 255, 0.028)),
    #121622;
  border: 1px solid rgba(129, 140, 248, 0.34);
  border-radius: var(--radius-full);
  font-size: var(--font-size-xs);
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.24);
}
.register-roadmap span::before {
  content: '';
  position: absolute;
  left: 11px;
  top: 50%;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent-hover);
  box-shadow: 0 0 18px rgba(129, 140, 248, 0.45);
  transform: translateY(-50%);
}
.register-panel {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-5);
}
.register-card {
  width: 100%;
  max-width: 400px;
  padding: var(--space-6);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.045), rgba(255, 255, 255, 0.015)),
    #10131b;
  border: 1px solid #343a4d;
  border-radius: 14px;
  box-shadow: var(--shadow-lg);
}
.register-back {
  display: inline-flex;
  margin-bottom: var(--space-5);
  color: #aeb5c4;
  font-size: var(--font-size-sm);
}
.register-back:hover {
  color: #f4f7ff;
}
.register-card__head {
  margin-bottom: var(--space-5);
}
.register-card__head h2 {
  color: #f4f7ff;
  font-size: var(--font-size-2xl);
}
.register-card__head p {
  margin-top: var(--space-1);
  color: #aeb5c4;
  font-size: var(--font-size-sm);
}
.register-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.register-session {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-4);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.045);
}
.register-session b {
  color: #f4f7ff;
  font-size: var(--font-size-sm);
}
.register-session p {
  color: #aeb5c4;
  font-size: var(--font-size-xs);
}
.register-session__cta,
.register-session__switch {
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  font-weight: 600;
}
.register-session__cta {
  margin-top: var(--space-2);
  color: #fff;
  background: var(--accent);
}
.register-session__switch {
  color: #c5cada;
  background: #151924;
  border: 1px solid #343a4d;
}
.role-tabs {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-1);
  padding: 4px;
  background: #0d1017;
  border: 1px solid #343a4d;
  border-radius: var(--radius-md);
}
.role-tab {
  height: 32px;
  color: #aeb5c4;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  transition: all var(--transition-fast);
}
.role-tab.is-active {
  color: #f4f7ff;
  background: #1c2030;
  box-shadow: var(--shadow-sm);
}
.register-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.register-field span {
  color: #c5cada;
  font-size: var(--font-size-xs);
  font-weight: 600;
}
.register-input {
  height: 40px;
  padding: 0 12px;
  color: #f4f7ff;
  background: #151924;
  border: 1px solid #343a4d;
  border-radius: var(--radius-md);
  outline: none;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.register-input:focus {
  border-color: var(--accent-border);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
.register-input::placeholder {
  color: #7f8799;
}
.register-error {
  padding: 6px 10px;
  color: var(--danger);
  background: var(--danger-soft);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
}
.register-submit {
  width: 100%;
  margin-top: var(--space-2);
}
.register-security {
  color: #9aa3b7;
  font-size: var(--font-size-xs);
  line-height: 1.6;
}
.register-hint {
  margin-top: var(--space-4);
  color: #aeb5c4;
  text-align: center;
  font-size: var(--font-size-xs);
}
.register-hint a {
  font-weight: 700;
}

@media (max-width: 960px) {
  .register-page {
    grid-template-columns: 1fr;
  }
  .register-story {
    display: none;
  }
}
</style>
