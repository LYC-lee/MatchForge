import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const TOKEN_KEY = 'matchforge:token'
const USER_KEY = 'matchforge:user'

export interface AuthUser {
  name: string
  account: string
}

/**
 * 鉴权 store(Spike mock 版)。
 * 后端未就绪,任意非空账号密码即可登录;真实后端就绪后替换 login 为 /auth/login 调用。
 */
export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const user = ref<AuthUser | null>(
    (() => {
      try {
        return JSON.parse(localStorage.getItem(USER_KEY) || 'null') as AuthUser | null
      } catch {
        return null
      }
    })(),
  )

  const isAuthenticated = computed(() => !!token.value)

  function login(account: string, password: string): { ok: boolean; msg?: string } {
    if (!account.trim() || !password.trim()) {
      return { ok: false, msg: '请输入账号和密码' }
    }
    // mock:不发请求,直接签发本地 token
    const t = `mock-${Date.now()}`
    const u: AuthUser = { name: account.trim(), account: account.trim() }
    token.value = t
    user.value = u
    localStorage.setItem(TOKEN_KEY, t)
    localStorage.setItem(USER_KEY, JSON.stringify(u))
    return { ok: true }
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  }

  return { token, user, isAuthenticated, login, logout }
})
