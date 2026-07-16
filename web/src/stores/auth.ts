import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

const SESSION_KEY = 'matchforge:session'
const USER_KEY = 'matchforge:user'
const SESSION_TTL_MS = 8 * 60 * 60 * 1000

export interface AuthUser {
  id?: string
  name: string
  account: string
  company?: string
  role?: 'buyer' | 'supplier' | 'admin'
}

interface AuthSession {
  token: string
  expiresAt: number
}

export const useAuthStore = defineStore('auth', () => {
  const session = ref<AuthSession | null>(readJson<AuthSession | null>(SESSION_KEY, null))
  const user = ref<AuthUser | null>(readJson<AuthUser | null>(USER_KEY, null))

  // 过期 session 自动清除
  if (session.value && session.value.expiresAt <= Date.now()) clearSession()

  const token = computed(() => session.value?.token || null)
  const isAuthenticated = computed(
    () => !!session.value?.token && !!user.value && (session.value.expiresAt || 0) > Date.now(),
  )
  const role = computed(() => user.value?.role || '')

  async function login(
    account: string,
    password: string,
  ): Promise<{ ok: boolean; msg?: string }> {
    if (!account.trim() || !password.trim()) {
      return { ok: false, msg: '请输入账号和密码' }
    }
    try {
      const res = await axios.post('/api/v1/auth/login', {
        account: account.trim().toLowerCase(),
        password,
      })
      const data = res.data
      const userInfo: AuthUser = {
        name: data.name,
        account: data.account || account,
        role: data.role,
      }
      persistSession(data.token, userInfo)
      return { ok: true }
    } catch (e: any) {
      const status = e?.response?.status
      const msg = e?.response?.data?.detail || '登录失败，请检查网络'
      if (status === 401) return { ok: false, msg: '账号或密码不正确' }
      return { ok: false, msg }
    }
  }

  async function register(payload: {
    name: string
    account: string
    password: string
    company: string
    role: string
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
      const data = res.data
      const userInfo: AuthUser = {
        name: data.name,
        account: data.account || account,
        role: data.role,
      }
      persistSession(data.token, userInfo)
      return { ok: true }
    } catch (e: any) {
      const status = e?.response?.status
      const msg = e?.response?.data?.detail || '注册失败，请检查网络'
      if (status === 400) return { ok: false, msg }
      return { ok: false, msg }
    }
  }

  async function validateSession(): Promise<boolean> {
    if (!session.value || !session.value.token || session.value.expiresAt <= Date.now()) {
      clearSession()
      return false
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

  function persistSession(newToken: string, userInfo: AuthUser) {
    session.value = { token: newToken, expiresAt: Date.now() + SESSION_TTL_MS }
    user.value = userInfo
    localStorage.setItem(SESSION_KEY, JSON.stringify(session.value))
    localStorage.setItem(USER_KEY, JSON.stringify(userInfo))
  }

  return { token, user, isAuthenticated, role, login, register, validateSession, logout }
})

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}
