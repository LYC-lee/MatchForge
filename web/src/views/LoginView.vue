<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AuthLayout from '@/components/ui/AuthLayout.vue'
import AppButton from '@/components/ui/AppButton.vue'
import HoloMap from '@/components/auth/HoloMap.vue'
import { DEFAULT_DEMO_COMPANY_ID, DEMO_COMPANIES } from '@/data/demoCompanies'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const account = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const demoLoading = ref(false)
const selectedDemoCompanyId = ref(DEFAULT_DEMO_COMPANY_ID)
const selectedDemoCompany = computed(
  () => DEMO_COMPANIES.find((company) => company.company_id === selectedDemoCompanyId.value) || DEMO_COMPANIES[0],
)

async function submit() {
  error.value = ''
  loading.value = true
  const r = await auth.login(account.value, password.value)
  loading.value = false
  if (r.ok) {
    const redirect = (route.query.redirect as string) || '/app'
    router.push(redirect)
  } else {
    error.value = r.msg || '登录失败'
  }
}

async function demoLogin() {
  error.value = ''
  demoLoading.value = true
  const r = await auth.loginDemoCompany(selectedDemoCompany.value)
  demoLoading.value = false
  if (r.ok) {
    const redirect = (route.query.redirect as string) || '/app'
    router.push(redirect)
  } else {
    error.value = r.msg || '演示登录失败'
  }
}

function switchAccount() {
  auth.logout()
  account.value = ''
  password.value = ''
  error.value = ''
}
</script>

<template>
  <AuthLayout>
    <template #story>
      <div class="auth-map">
        <HoloMap />
        <div class="auth-map__overlay">
          <p class="story-eyebrow">AI 替代料寻源</p>
      <h1 class="story-title">缺料不停产，找到可核验的替代料</h1>
      <p class="story-copy">
        对话提需求、规格确认、替代料推荐与供应商匹配、RFQ 询价——四步完成一次替代寻源，
        缩短交付周期，降低缺料风险，全程合规可溯源。
      </p>
      <div class="story-metrics">
        <div><b class="num">10 min</b><span>完成一次替代寻源</span></div>
        <div><b class="num">L1–L5</b><span>替代风险分级</span></div>
        <div><b class="num">RFQ</b><span>可编辑询价单</span></div>
          </div>
        </div>
      </div>
    </template>

    <RouterLink to="/" class="auth-back">← 返回产品介绍</RouterLink>
    <h2 class="auth-title">登录</h2>
    <p class="auth-sub">进入 AI 替代料寻源工作台</p>

    <div v-if="auth.isAuthenticated" class="auth-session">
      <span class="auth-session__avatar">{{ auth.user?.name.slice(0, 1).toUpperCase() }}</span>
      <div class="auth-session__info">
        <b>已登录：{{ auth.user?.name }}</b>
        <p>{{ auth.user?.account }}</p>
      </div>
      <AppButton @click="router.push('/app')">进入工作台</AppButton>
      <AppButton variant="secondary" @click="switchAccount">切换账号</AppButton>
    </div>

    <form v-else class="auth-form" @submit.prevent="submit">
      <section class="demo-login">
        <div class="demo-login__head">
          <div>
            <b>演示企业视角</b>
            <p>选择一家主视角企业进入，登录后系统内固定绑定该企业。</p>
          </div>
          <span class="demo-login__count">{{ DEMO_COMPANIES.length }} 家</span>
        </div>
        <label class="auth-field">
          <span class="auth-field__label">选择演示公司</span>
          <select v-model.number="selectedDemoCompanyId" class="auth-input">
            <option v-for="company in DEMO_COMPANIES" :key="company.company_id" :value="company.company_id">
              {{ company.name }} · {{ company.segment_name }}
            </option>
          </select>
        </label>
        <AppButton variant="secondary" :loading="demoLoading" @click="demoLogin">
          {{ demoLoading ? '进入中…' : '进入演示' }}
        </AppButton>
      </section>

      <div class="auth-divider"><span>账号登录</span></div>

      <label class="auth-field">
        <span class="auth-field__label">账号</span>
        <input v-model="account" type="text" class="auth-input" placeholder="name@company.com" autocomplete="username">
      </label>
      <label class="auth-field">
        <span class="auth-field__label">密码</span>
        <input v-model="password" type="password" class="auth-input" placeholder="输入密码" autocomplete="current-password">
      </label>

      <p v-if="error" class="auth-error" role="alert">{{ error }}</p>

      <AppButton type="submit" :loading="loading" class="auth-submit">登录</AppButton>
    </form>

    <p class="auth-hint">还没有账号？<RouterLink to="/register">免费注册</RouterLink></p>
    <p class="auth-disclaimer">演示账号：demo@matchforge.ai / demo12345</p>
  </AuthLayout>
</template>

<style scoped>
/* ---------- 故事面板（AuthLayout #story 槽） ---------- */
.auth-map {
  position: relative;
  flex: 1;
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.auth-map__overlay {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  max-width: 440px;
}
.story-eyebrow {
  color: var(--accent-text);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}
.story-title {
  max-width: 480px;
  font-size: var(--font-size-3xl);
  line-height: var(--leading-3xl);
  letter-spacing: -0.02em;
  color: var(--text-primary);
}
.story-copy {
  max-width: 440px;
  color: var(--text-secondary);
  font-size: var(--font-size-base);
  line-height: var(--leading-base);
}
.story-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
  max-width: 440px;
  margin-top: var(--space-4);
}
.story-metrics div {
  padding: var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  background: var(--bg-surface);
}
.story-metrics b {
  display: block;
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: var(--font-size-base);
  line-height: var(--leading-base);
}
.story-metrics span {
  display: block;
  margin-top: var(--space-1);
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
}

/* ---------- 表单面板 ---------- */
.auth-back {
  display: inline-flex;
  margin-bottom: var(--space-5);
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
}
.auth-back:hover {
  color: var(--text-primary);
}
.auth-title {
  font-size: var(--font-size-2xl);
  line-height: var(--leading-2xl);
  color: var(--text-primary);
}
.auth-sub {
  margin-top: var(--space-1);
  margin-bottom: var(--space-5);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
}
.auth-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.auth-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.auth-field__label {
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  font-weight: 600;
}
.auth-input {
  height: 40px;
  padding: 0 var(--space-3);
  color: var(--text-primary);
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  outline: none;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.auth-input:focus {
  border-color: var(--accent-border);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
.auth-input::placeholder {
  color: var(--text-tertiary);
}
.auth-error {
  padding: var(--space-2) var(--space-3);
  color: var(--danger);
  background: var(--danger-soft);
  border: 1px solid var(--danger-border);
  border-radius: var(--radius-md);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
}
.auth-submit {
  width: 100%;
  margin-top: var(--space-1);
}
.auth-divider {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
}
.auth-divider::before,
.auth-divider::after {
  content: '';
  height: 1px;
  flex: 1;
  background: var(--border-subtle);
}
.auth-hint {
  margin-top: var(--space-4);
  text-align: center;
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
}
.auth-hint a {
  font-weight: 700;
}
.auth-disclaimer {
  margin-top: var(--space-4);
  padding-top: var(--space-4);
  color: var(--text-tertiary);
  border-top: 1px solid var(--border-subtle);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
}

/* ---------- 演示登录 ---------- */
.demo-login {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-lg);
  background: var(--accent-soft);
}
.demo-login__head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
}
.demo-login__head b {
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
}
.demo-login__head p {
  margin-top: var(--space-1);
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
}
.demo-login__count {
  height: var(--space-5);
  padding: 0 var(--space-2);
  display: inline-flex;
  align-items: center;
  color: var(--accent-text);
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-full);
  background: var(--bg-surface);
  font-size: var(--font-size-xs);
  font-weight: 700;
  white-space: nowrap;
}

/* ---------- 已登录会话卡 ---------- */
.auth-session {
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr);
  gap: var(--space-3);
  padding: var(--space-4);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  background: var(--bg-subtle);
}
.auth-session__avatar {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: var(--on-accent);
  background: var(--accent);
  font-weight: 700;
}
.auth-session__info b {
  display: block;
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
}
.auth-session__info p {
  margin-top: var(--space-1);
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
}
.auth-session :deep(.btn) {
  grid-column: 1 / -1;
}
</style>
