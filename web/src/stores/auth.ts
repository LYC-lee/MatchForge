import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'
import { DEFAULT_DEMO_COMPANY_ID, findDemoCompany, type DemoCompany } from '@/data/demoCompanies'

const SESSION_KEY = 'matchforge:session'
const USER_KEY = 'matchforge:user'

export interface AuthUser {
  name: string
  account: string
  company?: string
  company_id?: number
  company_name?: string
  company_role?: string
  company_segment?: string
  is_demo?: boolean
  role?: 'buyer' | 'supplier' | 'admin'
}

interface AuthSession {
  token: string
  expiresAt: number
}

// session 有效期 8 小时
const SESSION_TTL_MS = 8 * 60 * 60 * 1000

export const useAuthStore = defineStore('auth', () => {
  const session = ref<AuthSession | null>(readJson<AuthSession | null>(SESSION_KEY, null))
  const user = ref<AuthUser | null>(readJson<AuthUser | null>(USER_KEY, null))

  // 过期 session 自动清除
  if (session.value && session.value.expiresAt <= Date.now()) {
    clearSession()
  }

  const token = computed(() => session.value?.token || null)
  const isAuthenticated = computed(
    () => !!session.value?.token && !!user.value && session.value.expiresAt > Date.now(),
  )

  async function login(
    account: string,
    password: string,
  ): Promise<{ ok: boolean; msg?: string }> {
    const normalized = account.trim().toLowerCase()
    if (!normalized || !password.trim()) {
      return { ok: false, msg: '请输入账号和密码' }
    }

    try {
      const res = await axios.post('/api/v1/auth/login', {
        account: normalized,
        password: password,
      })

      const { token: newToken, name, role, account: acc, company_id, company_name, company } = res.data
      persistSession(newToken, {
        name,
        account: acc,
        role,
        company,
        company_id,
        company_name: company_name || company,
      })
      return { ok: true }
    } catch (err: any) {
      const status = err?.response?.status
      const msg = err?.response?.data?.detail || '登录失败，请检查网络'
      if (status === 401) return { ok: false, msg: '账号或密码不正确' }
      return { ok: false, msg }
    }
  }

  async function loginDemoCompany(
    company: DemoCompany,
  ): Promise<{ ok: boolean; msg?: string }> {
    const selected = company || findDemoCompany(DEFAULT_DEMO_COMPANY_ID)
    if (!selected) return { ok: false, msg: '未找到演示企业' }

    persistSession('demo-token', {
      name: 'Demo Buyer',
      account: 'demo@matchforge.ai',
      role: 'buyer',
      company: selected.name,
      company_id: selected.company_id,
      company_name: selected.name,
      company_role: selected.role,
      company_segment: selected.segment_name,
      is_demo: true,
    })
    return { ok: true }
  }

  async function register(payload: {
    name: string
    account: string
    password: string
    company: string
    role: AuthUser['role']
  }): Promise<{ ok: boolean; msg?: string }> {
    const account = payload.account.trim().toLowerCase()
    if (!payload.name.trim() || !account || !payload.password.trim() || !payload.company.trim()) {
      return { ok: false, msg: '请完整填写注册信息' }
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(account)) {
      return { ok: false, msg: '请输入有效邮箱作为账号' }
    }
    if (payload.password.length < 8) {
      return { ok: false, msg: '密码至少 8 位' }
    }
    if (!/[A-Za-z]/.test(payload.password) || !/\d/.test(payload.password)) {
      return { ok: false, msg: '密码需同时包含字母和数字' }
    }

    try {
      const res = await axios.post('/api/v1/auth/register', {
        name: payload.name.trim(),
        account,
        password: payload.password,
        company: payload.company.trim(),
        role: payload.role || 'buyer',
      })

      const { token: newToken, name, role, account: acc } = res.data
      persistSession(newToken, { name, account: acc, company: payload.company.trim(), role })
      return { ok: true }
    } catch (err: any) {
      const status = err?.response?.status
      const msg = err?.response?.data?.detail || '注册失败，请检查网络'
      if (status === 400) return { ok: false, msg }
      return { ok: false, msg }
    }
  }

  async function validateSession(): Promise<boolean> {
    if (!session.value || !session.value.token || session.value.expiresAt <= Date.now()) {
      clearSession()
      return false
    }
    if (user.value?.is_demo) {
      return true
    }
    try {
      const res = await axios.get('/api/v1/auth/me', {
        headers: { Authorization: `Bearer ${session.value.token}` },
      })
      if (res.data) {
        user.value = {
          name: res.data.name,
          account: res.data.account,
          role: res.data.role,
          company: res.data.company || user.value?.company,
          company_id: res.data.company_id || user.value?.company_id,
          company_name: res.data.company_name || res.data.company || user.value?.company_name,
        }
        localStorage.setItem(USER_KEY, JSON.stringify(user.value))
        return true
      }
      return false
    } catch {
      clearSession()
      return false
    }
  }

  function logout() {
    clearSession()
  }

  function clearSession() {
    session.value = null
    user.value = null
    localStorage.removeItem(SESSION_KEY)
    localStorage.removeItem(USER_KEY)
  }

  function persistSession(newToken: string, publicUser: AuthUser) {
    const nextSession: AuthSession = {
      token: newToken,
      expiresAt: Date.now() + SESSION_TTL_MS,
    }
    session.value = nextSession
    user.value = publicUser
    localStorage.setItem(SESSION_KEY, JSON.stringify(nextSession))
    localStorage.setItem(USER_KEY, JSON.stringify(publicUser))
  }

  return { token, user, isAuthenticated, login, loginDemoCompany, register, validateSession, logout }
})

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}
