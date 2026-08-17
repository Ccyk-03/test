import { defineStore } from 'pinia'

// 登录态管理：token 与用户信息持久化到 localStorage
// 课程项目简化：JWT 存 localStorage（生产环境建议改用 httpOnly cookie 防 XSS）
const STORAGE_KEY = 'prompt_opt_auth'

export const useUserStore = defineStore('user', {
  state: () => {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null')
    return {
      token: saved?.token || '',
      user: saved?.user || null, // {id, username, role, is_active, created_at}
    }
  },
  getters: {
    isLoggedIn: (state) => !!state.token,
    isAdmin: (state) => state.user?.role === 'admin',
    username: (state) => state.user?.username || '',
  },
  actions: {
    setLogin(token, user) {
      this.token = token
      this.user = user
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ token, user }))
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem(STORAGE_KEY)
    },
  },
})
