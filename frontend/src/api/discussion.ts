import { api } from '@/api/base'

export interface DiscussionModeConfig {
  max_iterations?: number
  approval_threshold?: number
  discussion_threshold?: number
  timeout_seconds?: number
  enable_tools?: boolean
  verbose?: boolean
  enable_volume_decision?: boolean
  min_chapters_per_volume?: number
  max_chapters_per_volume?: number
}

export interface DiscussionChapterRequest {
  project_id: number
  chapter_number: number
  genre?: string
  word_count?: number
  previous_summary?: string
  character_states?: string
  blueprint_summary?: string
  volumes_snapshot?: any[]
  current_volume_chapters?: number
  current_volume_number?: number
  auto_upload?: boolean
  fanqie_account?: string
  config?: DiscussionModeConfig
}

export interface DiscussionChapterResponse {
  success: boolean
  content?: string
  title?: string
  final_score?: number
  iterations?: number
  total_duration_seconds?: number
  volume_decision?: any
  dialogue_summary?: any
  decisions?: any[]
  dialogue_export?: any
  error?: string
}

export class DiscussionAPI {
  static async generateChapter(req: DiscussionChapterRequest): Promise<DiscussionChapterResponse> {
    return api.post('/api/discussion-mode/generate-chapter', req)
  }
}
