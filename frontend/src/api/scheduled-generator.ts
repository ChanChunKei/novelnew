/**
 * 定时自动生成器 API
 */
import { API_BASE_URL, API_PREFIX } from './novel'

const SCHEDULED_GEN_BASE = `${API_BASE_URL}${API_PREFIX}/scheduled-generator`

// ========== 类型定义 ==========

export interface ScheduledGeneratorConfig {
  id: number
  user_id: number
  name: string
  enabled: boolean
  trigger_hour: number
  trigger_minute: number
  generation_mode: 'basic' | 'enhanced'
  auto_upload_fanqie: boolean
  upload_interval_seconds: number
  concurrent_books: number
  max_duration_per_book: number
  status: 'idle' | 'running' | 'paused'
  total_runs: number
  total_books_processed: number
  total_books_success: number
  total_books_failed: number
  last_run_at: string | null
  next_run_at: string | null
  created_at: string
  updated_at: string
}

export interface QueueItem {
  id: number
  config_id: number
  novel_id: string
  priority: number
  position: number
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
  auto_generator_task_id: number | null
  started_at: string | null
  completed_at: string | null
  duration_seconds: number | null
  chapters_generated: number
  chapters_target: number
  uploaded_to_fanqie: boolean
  upload_result: string | null
  error_message: string | null
  retry_count: number
  created_at: string
  updated_at: string
}

export interface SchedulerStatus {
  config_id: number
  status: string
  enabled: boolean
  next_run_at: string | null
  last_run_at: string | null
  queue_stats: {
    pending: number
    running: number
    completed: number
    failed: number
    total: number
  }
  currently_running: Array<{
    novel_id: string
    started_at: string | null
    chapters_generated: number
    chapters_target: number
  }>
  total_stats: {
    total_runs: number
    total_books_processed: number
    total_books_success: number
    total_books_failed: number
  }
}

export interface ExecutionLog {
  id: number
  config_id: number
  trigger_type: string
  trigger_time: string
  status: string
  books_processed: number
  books_success: number
  books_failed: number
  books_skipped: number
  total_chapters: number
  total_duration_seconds: number
  details: string | null
  error_message: string | null
  completed_at: string | null
  created_at: string
}

export interface ConfigCreateRequest {
  name: string
  trigger_hour: number
  trigger_minute: number
  generation_mode?: 'basic' | 'enhanced'
  auto_upload_fanqie?: boolean
  upload_interval_seconds?: number
  concurrent_books?: number
  max_duration_per_book?: number
}

export interface ConfigUpdateRequest {
  name?: string
  trigger_hour?: number
  trigger_minute?: number
  generation_mode?: 'basic' | 'enhanced'
  auto_upload_fanqie?: boolean
  upload_interval_seconds?: number
  concurrent_books?: number
  max_duration_per_book?: number
}

export interface AddToQueueRequest {
  novel_ids: string[]
  priority?: number
}

// ========== API 函数 ==========

const request = async (url: string, options: RequestInit = {}) => {
  const token = localStorage.getItem('token')
  const headers = new Headers({
    'Content-Type': 'application/json',
    ...options.headers
  })

  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(url, { ...options, headers })

  if (response.status === 401) {
    throw new Error('未授权，请重新登录')
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `请求失败，状态码: ${response.status}`)
  }

  if (response.status === 204) {
    return null
  }

  return response.json()
}

export const scheduledGeneratorApi = {
  // ========== 配置管理 ==========

  async createConfig(data: ConfigCreateRequest): Promise<ScheduledGeneratorConfig> {
    return request(`${SCHEDULED_GEN_BASE}/config`, {
      method: 'POST',
      body: JSON.stringify(data)
    })
  },

  async getConfig(): Promise<ScheduledGeneratorConfig> {
    return request(`${SCHEDULED_GEN_BASE}/config`)
  },

  async updateConfig(configId: number, data: ConfigUpdateRequest): Promise<ScheduledGeneratorConfig> {
    return request(`${SCHEDULED_GEN_BASE}/config/${configId}`, {
      method: 'PUT',
      body: JSON.stringify(data)
    })
  },

  async deleteConfig(configId: number): Promise<void> {
    return request(`${SCHEDULED_GEN_BASE}/config/${configId}`, {
      method: 'DELETE'
    })
  },

  // ========== 队列管理 ==========

  async addToQueue(data: AddToQueueRequest): Promise<QueueItem[]> {
    return request(`${SCHEDULED_GEN_BASE}/queue/add`, {
      method: 'POST',
      body: JSON.stringify(data)
    })
  },

  async getQueue(): Promise<QueueItem[]> {
    return request(`${SCHEDULED_GEN_BASE}/queue`)
  },

  async removeFromQueue(itemId: number): Promise<void> {
    return request(`${SCHEDULED_GEN_BASE}/queue/${itemId}`, {
      method: 'DELETE'
    })
  },

  // ========== 任务控制 ==========

  async start(): Promise<{ status: string; message: string }> {
    return request(`${SCHEDULED_GEN_BASE}/start`, {
      method: 'POST'
    })
  },

  async pause(): Promise<{ status: string; message: string }> {
    return request(`${SCHEDULED_GEN_BASE}/pause`, {
      method: 'POST'
    })
  },

  async resume(): Promise<{ status: string; message: string }> {
    return request(`${SCHEDULED_GEN_BASE}/resume`, {
      method: 'POST'
    })
  },

  async stop(): Promise<{ status: string; message: string }> {
    return request(`${SCHEDULED_GEN_BASE}/stop`, {
      method: 'POST'
    })
  },

  async triggerNow(): Promise<{ status: string; message: string }> {
    return request(`${SCHEDULED_GEN_BASE}/trigger-now`, {
      method: 'POST'
    })
  },

  // ========== 状态查询 ==========

  async getStatus(): Promise<SchedulerStatus> {
    return request(`${SCHEDULED_GEN_BASE}/status`)
  },

  async getLogs(limit: number = 20): Promise<ExecutionLog[]> {
    return request(`${SCHEDULED_GEN_BASE}/logs?limit=${limit}`)
  }
}
