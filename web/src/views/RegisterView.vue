<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AuthLayout from '@/components/ui/AuthLayout.vue'
import AppButton from '@/components/ui/AppButton.vue'
import HoloMap from '@/components/auth/HoloMap.vue'

const router = useRouter()
const auth = useAuthStore()

const name = ref('')
const company = ref('')
const account = ref('')
const password = ref('')
const confirmPassword = ref('')
const enterpriseType = ref('manufacturer')
const error = ref('')
const loading = ref(false)

// 企业类型: 供需角色由订单/RFQ/BOM/服务关系动态派生, 不在注册时固化
const ENTERPRISE_TYPES = [
  { value: 'manufacturer', label: '制造商' },
  { value: 'component_material', label: '元器件/材料' },
  { value: 'oem_brand', label: 'OEM/品牌' },
  { value: 'channel_customer', label: '渠道/客户' },
  { value: 'logistics_service', label: '物流/服务' },
  { value: 'government_park', label: '政府/园区' },
  { value: 'other', label: '其他' },
]

async function submit() {
  error.value = ''
  if (password.value !== confirmPassword.value) {
    error.value = '两次输入的密码不一致'
    return
  }
  loading.value = true
  const result = await auth.register({
    name: name.value,
    company: company.value,
    account: account.value,
    password: password.value,
    enterpriseType: enterpriseType.value,
  })
  loading.value = false
  if (result.ok) {
    router.push('/app')
  } else {
    error.value = result.msg || '注册失败'
  }
}
</script>

<template>
  <AuthLayout>
    <template #story>
      <div class="auth-map">
        <HoloMap />
        <div class="auth-map__overlay">
          <p class="story-eyebrow">AI 替代料寻源</p>
          <h1 class="story-title">创建你的寻源工作台</h1>
          <p class="story-copy">
            注册后即可使用完整的替代料寻源链路：对话提需求、规格确认、替代料分级推荐、
            供应商能力匹配与 RFQ 询价单生成。
          </p>
          <ul class="story-list">
            <li>对话式提需求，AI 结构化规格</li>
            <li>替代建议按 L1–L5 分级，风险前置暴露</li>
            <li>供应商能力匹配，不误导现货承诺</li>
            <li>RFQ 一键生成，发出前全程可编辑</li>
          </ul>
        </div>
      </div>
    </template>

    <RouterLink to="/" class="auth-back">← 返回产品介绍</RouterLink>
    <h2 class="auth-title">注册</h2>
    <p class="auth-sub">创建账号，开始第一次替代料寻源</p>

    <div v-if="auth.isAuthenticated" class="auth-session">
      <div class="auth-session__info">
        <b>当前已登录：{{ auth.user?.name }}</b>
        <p>{{ auth.user?.account }}</p>
      </div>
      <AppButton @click="router.push('/app')">进入工作台</AppButton>
      <AppButton variant="secondary" @click="auth.logout()">退出后注册新账号</AppButton>
    </div>

    <form v-else class="auth-form" @submit.prevent="submit">
      <label class="auth-field">
        <span class="auth-field__label">企业类型</span>
        <select v-model="enterpriseType" class="auth-input">
          <option v-for="t in ENTERPRISE_TYPES" :key="t.value" :value="t.value">{{ t.label }}</option>
        </select>
      </label>
      <label class="auth-field">
        <span class="auth-field__label">姓名</span>
        <input v-model="name" class="auth-input" placeholder="李明" autocomplete="name">
      </label>
      <label class="auth-field">
        <span class="auth-field__label">公司</span>
        <input v-model="company" class="auth-input" placeholder="深圳某硬件制造商" autocomplete="organization">
      </label>
      <label class="auth-field">
        <span class="auth-field__label">账号</span>
        <input v-model="account" class="auth-input" placeholder="name@company.com" autocomplete="username">
      </label>
      <label class="auth-field">
        <span class="auth-field__label">密码</span>
        <input v-model="password" type="password" class="auth-input" placeholder="至少 8 位，包含字母和数字" autocomplete="new-password">
      </label>
      <label class="auth-field">
        <span class="auth-field__label">确认密码</span>
        <input v-model="confirmPassword" type="password" class="auth-input" placeholder="再次输入密码" autocomplete="new-password">
      </label>

      <p v-if="error" class="auth-error" role="alert">{{ error }}</p>

      <AppButton type="submit" :loading="loading" class="auth-submit">创建账号</AppButton>
    </form>

    <p class="auth-hint">已有账号？<RouterLink to="/login">返回登录</RouterLink></p>
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
.story-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  max-width: 440px;
  margin-top: var(--space-2);
}
.story-list li {
  position: relative;
  padding-left: var(--space-4);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
}
.story-list li::before {
  content: '';
  position: absolute;
  left: 0;
  top: calc((var(--leading-sm) - var(--space-2)) / 2);
  width: var(--space-2);
  height: var(--space-2);
  border-radius: 50%;
  background: var(--accent);
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

/* ---------- 已登录会话卡 ---------- */
.auth-session {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  background: var(--bg-subtle);
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
</style>
