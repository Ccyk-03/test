import axios from 'axios'
import { ElMessage } from 'element-plus'

import router from '../router'
import { useUserStore } from '../stores/user'

// 统一 axios 实例：baseURL=/api（开发期由 Vite 代理到后端 8000 端口）
// 超时 10 分钟：推理模型 + 复杂长提示词单次调用可能耗时 3-10 分钟
const request = axios.create({ baseURL: '/api', timeout: 600000 })

// 请求拦截器：自动注入 JWT
request.interceptors.request.use((config) => {
  const store = useUserStore()
  if (store.token) {
    config.headers.Authorization = `Bearer ${store.token}`
  }
  return config
})

// 响应拦截器：直接返回 data；统一错误提示；401 清除登录态并跳转登录页
request.interceptors.response.use(
  (resp) => resp.data,
  (error) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail
    if (status === 401) {
      const store = useUserStore()
      store.logout()
      ElMessage.warning(typeof detail === 'string' ? detail : '登录已过期，请重新登录')
      router.push('/login')
    } else if (detail) {
      ElMessage.error(typeof detail === 'string' ? detail : '请求失败')
    } else {
      ElMessage.error('网络错误，请稍后重试')
    }
    return Promise.reject(error)
  },
)

export default request
