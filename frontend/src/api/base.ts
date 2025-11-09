import { useAuthStore } from '@/stores/auth'
import router from '@/router'

// API 配置
// 使用环境变量配置 API Base URL，支持不同部署环境
// @ts-ignore - Vite 环境变量
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.MODE === 'production' ? '' : 'http://127.0.0.1:8000')

// 统一的 API 请求类
class APIClient {
  private baseURL: string

  constructor(baseURL: string) {
    this.baseURL = baseURL
  }

  private async request(url: string, options: RequestInit = {}) {
    const authStore = useAuthStore()
    const headers = new Headers({
      'Content-Type': 'application/json',
      ...options.headers
    })

    if (authStore.isAuthenticated && authStore.token) {
      headers.set('Authorization', `Bearer ${authStore.token}`)
    }

    const fullURL = url.startsWith('http') ? url : `${this.baseURL}${url}`
    const response = await fetch(fullURL, { ...options, headers })

    if (response.status === 401) {
      // Token 失效或未授权
      authStore.logout()
      router.push('/login')
      throw new Error('会话已过期，请重新登录')
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `请求失败，状态码: ${response.status}`)
    }

    return response.json()
  }

  async get(url: string, options: RequestInit = {}) {
    return this.request(url, { ...options, method: 'GET' })
  }

  async post(url: string, data?: any, options: RequestInit = {}) {
    return this.request(url, {
      ...options,
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined
    })
  }

  async put(url: string, data?: any, options: RequestInit = {}) {
    return this.request(url, {
      ...options,
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined
    })
  }

  async patch(url: string, data?: any, options: RequestInit = {}) {
    return this.request(url, {
      ...options,
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined
    })
  }

  async delete(url: string, options: RequestInit = {}) {
    return this.request(url, { ...options, method: 'DELETE' })
  }
}

// 导出 API 实例
export const api = new APIClient(API_BASE_URL)

// 导出默认实例
export default api
