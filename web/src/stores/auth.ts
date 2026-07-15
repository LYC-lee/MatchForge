import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const SESSION_KEY = 'matchforge:session'
const USER_KEY = 'matchforge:user'
const USERS_KEY = 'matchforge:users'
const FAILED_KEY = 'matchforge:failed-logins'
const SESSION_TTL_MS = 8 * 60 * 60 * 1000

export interface AuthUser {
  name: string
  account: string
  company?: string
  role?: 'buyer' | 'supplier' | 'admin'
}

interface StoredUser extends AuthUser {
  passwordHash: string
  salt: string
  createdAt: string
}

interface AuthSession {
  token: string
  expiresAt: number
}

interface FailedLogin {
  count: number
  lockedUntil?: number
}

const DEMO_ACCOUNT = 'demo@matchforge.ai'
const DEMO_PASSWORD = 'demo12345'

export const useAuthStore = defineStore('auth', () => {
  const session = ref<AuthSession | null>(readJson<AuthSession | null>(SESSION_KEY, null))
  const user = ref<AuthUser | null>(
    (() => {
      const stored = readJson<AuthUser | null>(USER_KEY, null)
      return stored
    })(),
  )

  seedDemoUser()
  if (session.value && session.value.expiresAt <= Date.now()) {
    clearSession()
  }

  const token = computed(() => session.value?.token || null)
  const isAuthenticated = computed(() => !!session.value?.token && !!user.value && session.value.expiresAt > Date.now())

  function login(account: string, password: string): { ok: boolean; msg?: string } {
    const normalized = normalizeAccount(account)
    if (!normalized || !password.trim()) {
      return { ok: false, msg: '请输入账号和密码' }
    }
    const failed = getFailedMap()
    const record = failed[normalized]
    if (record?.lockedUntil && record.lockedUntil > Date.now()) {
      return { ok: false, msg: '登录尝试过多，请稍后再试' }
    }

    const found = getUsers().find((u) => u.account === normalized)
    if (!found || found.passwordHash !== hashPassword(password, found.salt)) {
      failed[normalized] = nextFailedRecord(record)
      saveFailedMap(failed)
      return { ok: false, msg: '账号或密码不正确' }
    }

    delete failed[normalized]
    saveFailedMap(failed)
    createSession(found)
    return { ok: true }
  }

  function register(payload: {
    name: string
    account: string
    password: string
    company: string
    role: AuthUser['role']
  }): { ok: boolean; msg?: string } {
    const account = normalizeAccount(payload.account)
    if (!payload.name.trim() || !account || !payload.password.trim() || !payload.company.trim()) {
      return { ok: false, msg: '请完整填写注册信息' }
    }
    if (!isValidEmail(account)) {
      return { ok: false, msg: '请输入有效邮箱作为账号' }
    }
    const passwordError = validatePassword(payload.password)
    if (passwordError) {
      return { ok: false, msg: passwordError }
    }
    const users = getUsers()
    if (users.some((u) => u.account === account)) {
      return { ok: false, msg: '该账号已注册，请直接登录' }
    }

    const salt = createToken(12)
    const u: StoredUser = {
      name: payload.name.trim(),
      account,
      company: payload.company.trim(),
      role: payload.role,
      salt,
      passwordHash: hashPassword(payload.password, salt),
      createdAt: new Date().toISOString(),
    }
    saveUsers([...users, u])
    createSession(u)
    return { ok: true }
  }

  function validateSession(): boolean {
    if (!session.value || !user.value || session.value.expiresAt <= Date.now()) {
      clearSession()
      return false
    }
    return true
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

  function createSession(storedUser: StoredUser) {
    const publicUser: AuthUser = {
      name: storedUser.name,
      account: storedUser.account,
      company: storedUser.company,
      role: storedUser.role,
    }
    const nextSession: AuthSession = {
      token: createToken(24),
      expiresAt: Date.now() + SESSION_TTL_MS,
    }
    session.value = nextSession
    user.value = publicUser
    localStorage.setItem(SESSION_KEY, JSON.stringify(nextSession))
    localStorage.setItem(USER_KEY, JSON.stringify(publicUser))
  }

  return { token, user, isAuthenticated, login, register, validateSession, logout }
})

function normalizeAccount(account: string) {
  return account.trim().toLowerCase()
}

function isValidEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
}

function validatePassword(password: string) {
  if (password.length < 8) return '密码至少 8 位'
  if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) return '密码需同时包含字母和数字'
  return ''
}

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}

function getUsers(): StoredUser[] {
  return readJson<StoredUser[]>(USERS_KEY, [])
}

function saveUsers(users: StoredUser[]) {
  localStorage.setItem(USERS_KEY, JSON.stringify(users))
}

function seedDemoUser() {
  const users = getUsers()
  if (users.some((u) => u.account === DEMO_ACCOUNT)) return
  const salt = 'demo-salt'
  saveUsers([
    ...users,
    {
      name: 'Demo Buyer',
      account: DEMO_ACCOUNT,
      company: 'MatchForge Demo',
      role: 'buyer',
      salt,
      passwordHash: hashPassword(DEMO_PASSWORD, salt),
      createdAt: new Date().toISOString(),
    },
  ])
}

function createToken(bytes = 16) {
  const values = new Uint8Array(bytes)
  crypto.getRandomValues(values)
  return Array.from(values, (v) => v.toString(16).padStart(2, '0')).join('')
}

function hashPassword(password: string, salt: string) {
  let hash = 2166136261
  const input = `${salt}:${password}`
  for (let i = 0; i < input.length; i += 1) {
    hash ^= input.charCodeAt(i)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0).toString(16)
}

function getFailedMap(): Record<string, FailedLogin> {
  return readJson<Record<string, FailedLogin>>(FAILED_KEY, {})
}

function saveFailedMap(value: Record<string, FailedLogin>) {
  localStorage.setItem(FAILED_KEY, JSON.stringify(value))
}

function nextFailedRecord(current?: FailedLogin): FailedLogin {
  const count = (current?.count || 0) + 1
  return {
    count,
    lockedUntil: count >= 5 ? Date.now() + 5 * 60 * 1000 : undefined,
  }
}
