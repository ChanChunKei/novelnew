import { useAuthStore } from '@/stores/auth'
import router from '@/router'

// API 配置
// 在生产环境中使用相对路径，在开发环境中使用绝对路径
export const API_BASE_URL = import.meta.env.MODE === 'production' ? '' : 'http://127.0.0.1:8000'
export const API_PREFIX = '/api'

// ✅ 修复：统一的 API 路由配置，避免硬编码
export const API_ROUTES = {
  NOVELS: `${API_PREFIX}/novels`,
  WRITER: `${API_PREFIX}/writer`,
  ADMIN: `${API_PREFIX}/admin`,
  AUTH: `${API_PREFIX}/auth`,
  UPDATES: `${API_PREFIX}/updates`,
  LLM_CONFIG: `${API_PREFIX}/llm-config`,
  AI_ROUTING: `${API_PREFIX}/ai-routing`,
  AUTO_GENERATOR: `${API_PREFIX}/auto-generator`,
  ASYNC_ANALYSIS: `${API_PREFIX}/async-analysis`,
} as const

// 统一的请求处理函数
const request = async (url: string, options: RequestInit = {}) => {
  const authStore = useAuthStore()
  const headers = new Headers({
    'Content-Type': 'application/json',
    ...options.headers
  })

  if (authStore.isAuthenticated && authStore.token) {
    headers.set('Authorization', `Bearer ${authStore.token}`)
  }

  const response = await fetch(url, { ...options, headers })

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

// 类型定义
export interface NovelProject {
  id: string
  title: string
  initial_prompt: string
  fanqie_book_id?: string | null
  blueprint?: Blueprint
  chapters: Chapter[]
  conversation_history: ConversationMessage[]
}

export interface NovelProjectSummary {
  id: string
  title: string
  genre: string
  last_edited: string
  completed_chapters: number
  total_chapters: number
}

export interface WorldSetting {
  description?: string
  rules?: string[]
  key_locations?: Array<{
    name: string
    description: string
  }>
  factions?: Array<{
    name: string
    description: string
  }>
  [key: string]: unknown // 允许其他自定义字段
}

export interface Relationship {
  from_character?: string
  to_character?: string
  relationship_type?: string
  description?: string
  character_from?: string
  character_to?: string
  source?: string
  target?: string
  [key: string]: string | undefined
}

export interface Volume {
  id?: number
  volume_number: number
  title: string
  description?: string
}

export interface Blueprint {
  title?: string
  target_audience?: string
  genre?: string
  style?: string
  tone?: string
  one_sentence_summary?: string
  full_synopsis?: string
  world_setting?: WorldSetting
  characters?: Character[]
  relationships?: Relationship[]
  volumes?: Volume[]
  chapter_outline?: ChapterOutline[]
}

export interface Character {
  name: string
  description?: string | Record<string, string | undefined>
  identity?: string
  personality?: string
  goals?: string
  abilities?: string
  relationship_to_protagonist?: string
  role?: string
  [key: string]: string | Record<string, string | undefined> | undefined
}

export interface ChapterOutline {
  chapter_number: number
  title: string
  summary: string
  volume_id?: number
  volume_number?: number
}

export interface ChapterVersion {
  content: string
  style?: string
}

export interface Chapter {
  chapter_number: number
  title: string
  summary: string
  content: string | null
  versions: string[] | null  // versions是字符串数组，不是对象数组
  evaluation: string | null
  generation_status: 'not_generated' | 'generating' | 'evaluating' | 'selecting' | 'failed' | 'evaluation_failed' | 'waiting_for_confirm' | 'successful'
  word_count?: number  // 字数统计
  selected_version_metadata?: Record<string, any> | null  // ✅ 新增：3Agent的metadata
}

export interface ConversationMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface UserInput {
  id: string | null
  value: string | null
}

export interface ConversationState {
  [key: string]: unknown
}

export interface ConverseResponse {
  ai_message: string
  ui_control: UIControl
  conversation_state: ConversationState
  is_complete: boolean
  ready_for_blueprint?: boolean  // 新增：表示准备生成蓝图
}

export interface BlueprintGenerationResponse {
  blueprint: Blueprint
  ai_message: string
}

export interface UIControl {
  type: 'single_choice' | 'text_input'
  options?: Array<{ id: string; label: string }>
  placeholder?: string
}

export interface ChapterGenerationResponse {
  versions: ChapterVersion[] // Renamed from chapter_versions for consistency
  evaluation: string | null
  ai_message: string
  chapter_number: number
}

export interface DeleteNovelsResponse {
  status: string
  message: string
}

export type NovelSectionType = 'overview' | 'world_setting' | 'characters' | 'relationships' | 'chapter_outline' | 'chapters' | 'auto_generator' | 'fanqie_upload'

export interface NovelSectionData {
  title?: string
  updated_at?: string | null
  fanqie_book_id?: string | null
  world_setting?: WorldSetting
  characters?: Character[]
  relationships?: Relationship[]
  chapter_outline?: ChapterOutline[]
  chapters?: Chapter[]
  volumes?: unknown[]
  project_title?: string
  [key: string]: unknown
}

export interface NovelSectionResponse {
  section: NovelSectionType
  data: NovelSectionData
}

// API 函数 - 使用统一的路由配置
const NOVELS_BASE = `${API_BASE_URL}${API_ROUTES.NOVELS}`
const WRITER_PREFIX = API_ROUTES.WRITER
const WRITER_BASE = `${API_BASE_URL}${WRITER_PREFIX}/novels`

export class NovelAPI {
  static async createNovel(title: string, initialPrompt: string): Promise<NovelProject> {
    return request(NOVELS_BASE, {
      method: 'POST',
      body: JSON.stringify({ title, initial_prompt: initialPrompt })
    })
  }

  static async getNovel(projectId: string): Promise<NovelProject> {
    return request(`${NOVELS_BASE}/${projectId}`)
  }

  static async getChapter(projectId: string, chapterNumber: number): Promise<Chapter> {
    return request(`${NOVELS_BASE}/${projectId}/chapters/${chapterNumber}`)
  }

  static async getSection(projectId: string, section: NovelSectionType): Promise<NovelSectionResponse> {
    return request(`${NOVELS_BASE}/${projectId}/sections/${section}`)
  }

  static async converseConcept(
    projectId: string,
    userInput: UserInput | null,
    conversationState: ConversationState = {}
  ): Promise<ConverseResponse> {
    const formattedUserInput = userInput || { id: null, value: null }
    return request(`${NOVELS_BASE}/${projectId}/concept/converse`, {
      method: 'POST',
      body: JSON.stringify({
        user_input: formattedUserInput,
        conversation_state: conversationState
      })
    })
  }

  static async generateBlueprint(projectId: string): Promise<BlueprintGenerationResponse> {
    return request(`${NOVELS_BASE}/${projectId}/blueprint/generate`, {
      method: 'POST'
    })
  }

  static async saveBlueprint(projectId: string, blueprint: Blueprint): Promise<NovelProject> {
    return request(`${NOVELS_BASE}/${projectId}/blueprint/save`, {
      method: 'POST',
      body: JSON.stringify(blueprint)
    })
  }

  static async generateChapter(projectId: string, chapterNumber: number): Promise<NovelProject> {
    return request(`${WRITER_BASE}/${projectId}/chapters/generate`, {
      method: 'POST',
      body: JSON.stringify({ chapter_number: chapterNumber })
    })
  }

  static async evaluateChapter(projectId: string, chapterNumber: number): Promise<NovelProject> {
    return request(`${WRITER_BASE}/${projectId}/chapters/evaluate`, {
      method: 'POST',
      body: JSON.stringify({ chapter_number: chapterNumber })
    })
  }

  static async selectChapterVersion(
    projectId: string,
    chapterNumber: number,
    versionIndex: number
  ): Promise<NovelProject> {
    return request(`${WRITER_BASE}/${projectId}/chapters/select`, {
      method: 'POST',
      body: JSON.stringify({
        chapter_number: chapterNumber,
        version_index: versionIndex
      })
    })
  }

  static async getAllNovels(): Promise<NovelProjectSummary[]> {
    return request(NOVELS_BASE)
  }

  static async deleteNovels(projectIds: string[]): Promise<DeleteNovelsResponse> {
    return request(NOVELS_BASE, {
      method: 'DELETE',
      body: JSON.stringify(projectIds)
    })
  }

  static async updateChapterOutline(
    projectId: string,
    chapterOutline: ChapterOutline
  ): Promise<NovelProject> {
    return request(`${WRITER_BASE}/${projectId}/chapters/update-outline`, {
      method: 'POST',
      body: JSON.stringify(chapterOutline)
    })
  }

  static async deleteChapter(
    projectId: string,
    chapterNumbers: number[]
  ): Promise<NovelProject> {
    return request(`${WRITER_BASE}/${projectId}/chapters/delete`, {
      method: 'POST',
      body: JSON.stringify({ chapter_numbers: chapterNumbers })
    })
  }

  static async generateChapterOutline(
    projectId: string,
    startChapter: number,
    numChapters: number,
    versionCount: number = 3
  ): Promise<NovelProject> {
    return request(`${WRITER_BASE}/${projectId}/chapters/outline`, {
      method: 'POST',
      body: JSON.stringify({
        start_chapter: startChapter,
        num_chapters: numChapters,
        version_count: versionCount
      })
    })
  }

  static async updateBlueprint(projectId: string, data: Record<string, any>): Promise<NovelProject> {
    return request(`${NOVELS_BASE}/${projectId}/blueprint`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    })
  }

  static async editChapterContent(
    projectId: string,
    chapterNumber: number,
    content: string
  ): Promise<NovelProject> {
    return request(`${WRITER_BASE}/${projectId}/chapters/edit`, {
      method: 'POST',
      body: JSON.stringify({
        chapter_number: chapterNumber,
        content: content
      })
    })
  }

  static async updateProjectTitle(projectId: string, title: string): Promise<NovelProject> {
    return request(`${NOVELS_BASE}/${projectId}/title`, {
      method: 'PUT',
      body: JSON.stringify({ title })
    })
  }

  static async updateFanqieBookId(projectId: string, fanqieBookId: string): Promise<NovelProject> {
    return request(`${NOVELS_BASE}/${projectId}/fanqie-book-id`, {
      method: 'PUT',
      body: JSON.stringify({ fanqie_book_id: fanqieBookId })
    })
  }
}

// 番茄小说上传 API
export const novelApi = {
  async uploadToFanqie(
    projectId: string,
    account: string = 'default',
    headless: boolean = true,
    uploadInterval: number = 20,
    signal?: AbortSignal
  ): Promise<{
    success: boolean
    error?: string
    hint?: string
    book_id?: string
    book_name?: string
    volume_count?: number
    chapter_count?: number
  }> {
    return request(`${NOVELS_BASE}/${projectId}/upload-to-fanqie`, {
      method: 'POST',
      body: JSON.stringify({
        account,
        headless,
        upload_interval: uploadInterval
      }),
      signal
    })
  },

  async fanqieLogin(
    account: string = 'default'
  ): Promise<{
    success: boolean
    error?: string
    account?: string
    message?: string
  }> {
    return request(`${NOVELS_BASE}/fanqie/login`, {
      method: 'POST',
      body: JSON.stringify({
        account
      })
    })
  },

  async fanqieSaveCookies(
    account: string = 'default'
  ): Promise<{
    success: boolean
    error?: string
    account?: string
    message?: string
  }> {
    return request(`${NOVELS_BASE}/fanqie/save-cookies`, {
      method: 'POST',
      body: JSON.stringify({
        account
      })
    })
  },

  async fanqieManualSaveCookies(
    account: string = 'default',
    cookieString: string
  ): Promise<{
    success: boolean
    error?: string
    account?: string
    message?: string
  }> {
    return request(`${NOVELS_BASE}/fanqie/manual-save-cookies`, {
      method: 'POST',
      body: JSON.stringify({
        account,
        cookie_string: cookieString
      })
    })
  }
}

// AI 配置管理 API
export const aiConfigApi = {
  // 获取所有 AI 供应商
  async getProviders(): Promise<any[]> {
    return request(`${API_BASE_URL}${API_PREFIX}/ai/providers`)
  },

  // 添加 AI 供应商
  async addProvider(provider: any): Promise<any> {
    return request(`${API_BASE_URL}${API_PREFIX}/ai/providers`, {
      method: 'POST',
      body: JSON.stringify(provider)
    })
  },

  // 更新 AI 供应商
  async updateProvider(providerId: string, provider: any): Promise<any> {
    return request(`${API_BASE_URL}${API_PREFIX}/ai/providers/${providerId}`, {
      method: 'PUT',
      body: JSON.stringify(provider)
    })
  },

  // 删除 AI 供应商
  async deleteProvider(providerId: string): Promise<void> {
    return request(`${API_BASE_URL}${API_PREFIX}/ai/providers/${providerId}`, {
      method: 'DELETE'
    })
  },

  // 获取 AI 功能配置
  async getFunctionConfigs(): Promise<any[]> {
    return request(`${API_BASE_URL}${API_PREFIX}/ai/function-configs`)
  },

  // 更新 AI 功能配置
  async updateFunctionConfig(functionName: string, config: any): Promise<any> {
    return request(`${API_BASE_URL}${API_PREFIX}/ai/function-configs/${functionName}`, {
      method: 'PUT',
      body: JSON.stringify(config)
    })
  },

  // 获取 AI 调用统计
  async getCallStats(startDate?: string, endDate?: string): Promise<any> {
    const params = new URLSearchParams()
    if (startDate) params.append('start_date', startDate)
    if (endDate) params.append('end_date', endDate)
    return request(`${API_BASE_URL}${API_PREFIX}/ai/stats?${params}`)
  }
}

// 异步分析任务 API
export const asyncAnalysisApi = {
  // 获取任务列表
  async getTasks(status?: string): Promise<any[]> {
    const params = status ? `?status=${status}` : ''
    return request(`${API_BASE_URL}${API_PREFIX}/async-analysis/tasks${params}`)
  },

  // 获取任务详情
  async getTask(taskId: string): Promise<any> {
    return request(`${API_BASE_URL}${API_PREFIX}/async-analysis/tasks/${taskId}`)
  },

  // 取消任务
  async cancelTask(taskId: string): Promise<void> {
    return request(`${API_BASE_URL}${API_PREFIX}/async-analysis/tasks/${taskId}/cancel`, {
      method: 'POST'
    })
  }
}

// 分卷管理 API
export const volumeApi = {
  // 获取剧情指标
  async getStoryMetrics(projectId: string): Promise<any[]> {
    return request(`${API_BASE_URL}${API_PREFIX}/novels/${projectId}/story-metrics`)
  },

  // 触发自动分卷
  async triggerAutoSplit(projectId: string, threshold?: number): Promise<any> {
    return request(`${API_BASE_URL}${API_PREFIX}/novels/${projectId}/auto-split`, {
      method: 'POST',
      body: JSON.stringify({ threshold })
    })
  },

  // 获取分卷配置
  async getSplitConfig(projectId: string): Promise<any> {
    return request(`${API_BASE_URL}${API_PREFIX}/novels/${projectId}/split-config`)
  },

  // 更新分卷配置
  async updateSplitConfig(projectId: string, config: any): Promise<any> {
    return request(`${API_BASE_URL}${API_PREFIX}/novels/${projectId}/split-config`, {
      method: 'PUT',
      body: JSON.stringify(config)
    })
  }
}
