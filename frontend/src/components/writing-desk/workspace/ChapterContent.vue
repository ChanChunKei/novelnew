<template>
  <div class="space-y-6">
    <div class="bg-green-50 border border-green-200 rounded-xl p-4 mb-6">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2 text-green-800">
          <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path>
          </svg>
          <span class="font-medium">这个章节已经完成</span>
        </div>

        <div class="flex items-center gap-2">
          <button
            v-if="hasMetadata"
            @click="showMetadataModal = true"
            class="text-blue-600 hover:text-blue-800 text-sm font-medium flex items-center gap-1"
          >
            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z"></path>
              <path fill-rule="evenodd" d="M4 5a2 2 0 012-2 3 3 0 003 3h2a3 3 0 003-3 2 2 0 012 2v11a2 2 0 01-2 2H6a2 2 0 01-2-2V5zm3 4a1 1 0 000 2h.01a1 1 0 100-2H7zm3 0a1 1 0 000 2h3a1 1 0 100-2h-3zm-3 4a1 1 0 100 2h.01a1 1 0 100-2H7zm3 0a1 1 0 100 2h3a1 1 0 100-2h-3z" clip-rule="evenodd"></path>
            </svg>
            生成详情
          </button>
          <button
            v-if="selectedChapter.versions && selectedChapter.versions.length > 0"
            @click="$emit('showVersionSelector', true)"
            class="text-green-700 hover:text-green-800 text-sm font-medium flex items-center gap-1"
          >
            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"></path>
              <path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd"></path>
            </svg>
            查看所有版本
          </button>
        </div>
      </div>
    </div>

    <div class="bg-gray-50 rounded-xl p-6">
      <div class="flex items-center justify-between mb-4 gap-3">
        <h4 class="font-semibold text-gray-800">章节内容</h4>
        <div class="flex items-center gap-3">
          <div class="text-sm text-gray-500">
            约 {{ Math.round(cleanVersionContent(selectedChapter.content || '').length / 100) * 100 }} 字
          </div>
          <button
            class="inline-flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg border transition-colors duration-200"
            :class="selectedChapter.content ? 'border-indigo-200 text-indigo-600 hover:bg-indigo-50' : 'border-gray-200 text-gray-400 cursor-not-allowed'"
            :disabled="!selectedChapter.content"
            @click="exportChapterAsTxt(selectedChapter)"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v16h16V4m-4 4l-4-4-4 4m4-4v12" />
            </svg>
            导出TXT
          </button>
        </div>
      </div>
      <div class="prose max-w-none">
        <div class="whitespace-pre-wrap text-gray-700 leading-relaxed">{{ cleanVersionContent(selectedChapter.content || '') }}</div>
      </div>
    </div>

    <!-- Metadata查看模态框 -->
    <div v-if="showMetadataModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div class="bg-white rounded-2xl shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col">
        <!-- 模态框头部 -->
        <div class="flex items-center justify-between p-6 border-b border-gray-200">
          <h3 class="text-lg font-semibold text-gray-900">
            生成详情 - 第{{ selectedChapter.chapter_number }}章
          </h3>
          <button
            @click="showMetadataModal = false"
            class="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
            </svg>
          </button>
        </div>

        <!-- 模态框内容 -->
        <div class="flex-1 p-6 overflow-y-auto">
          <div v-if="metadata" class="space-y-6">
            <!-- 概览信息 -->
            <div class="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg p-4 border border-blue-200">
              <h4 class="font-semibold text-gray-800 mb-3">📊 生成概览</h4>
              <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <div class="text-sm text-gray-600">迭代次数</div>
                  <div class="text-2xl font-bold text-blue-600">{{ metadata.iterations || 'N/A' }}</div>
                </div>
                <div>
                  <div class="text-sm text-gray-600">最终评分</div>
                  <div class="text-2xl font-bold text-green-600">{{ metadata.final_score || 'N/A' }}</div>
                </div>
                <div>
                  <div class="text-sm text-gray-600">生成耗时</div>
                  <div class="text-2xl font-bold text-purple-600">{{ formatTime(metadata.total_time_seconds) }}</div>
                </div>
                <div>
                  <div class="text-sm text-gray-600">对话轮次</div>
                  <div class="text-2xl font-bold text-orange-600">{{ metadata.conversation_history?.length || 0 }}</div>
                </div>
              </div>
            </div>

            <!-- 对话历史 -->
            <div v-if="metadata.conversation_history && metadata.conversation_history.length > 0">
              <h4 class="font-semibold text-gray-800 mb-3">💬 生成过程</h4>
              <div class="space-y-3">
                <div
                  v-for="(item, index) in metadata.conversation_history"
                  :key="index"
                  class="border rounded-lg p-4"
                  :class="getAgentColor(item.agent)"
                >
                  <div class="flex items-center justify-between mb-2">
                    <div class="flex items-center gap-2">
                      <span class="text-lg">{{ getAgentIcon(item.agent) }}</span>
                      <span class="font-semibold">{{ getAgentName(item.agent) }}</span>
                      <span v-if="item.iteration" class="text-xs bg-gray-200 px-2 py-1 rounded">第{{ item.iteration }}轮</span>
                    </div>
                    <span class="text-xs text-gray-500">{{ formatTimestamp(item.timestamp) }}</span>
                  </div>
                  
                  <!-- Planner内容 -->
                  <div v-if="item.agent === 'planner' && item.content" class="text-sm space-y-2">
                    <div v-if="item.content.analysis" class="bg-white bg-opacity-50 p-2 rounded">
                      <span class="font-medium">分析：</span>
                      <p class="text-gray-700 mt-1">{{ truncateText(item.content.analysis, 200) }}</p>
                    </div>
                    <div v-if="item.content.plan" class="bg-white bg-opacity-50 p-2 rounded">
                      <span class="font-medium">规划：</span>
                      <p class="text-gray-700 mt-1">{{ truncateText(item.content.plan, 200) }}</p>
                    </div>
                    <div v-if="item.content.notes_for_writer" class="bg-white bg-opacity-50 p-2 rounded">
                      <span class="font-medium">给Writer的建议：</span>
                      <p class="text-gray-700 mt-1">{{ truncateText(item.content.notes_for_writer, 200) }}</p>
                    </div>
                  </div>

                  <!-- Writer内容 -->
                  <div v-if="item.agent === 'writer' && item.content" class="text-sm space-y-2">
                    <div class="bg-white bg-opacity-50 p-2 rounded">
                      <span class="font-medium">字数：</span>
                      <span class="text-gray-700">{{ item.content.word_count || 'N/A' }}</span>
                    </div>
                    <div v-if="item.content.preview" class="bg-white bg-opacity-50 p-2 rounded">
                      <span class="font-medium">内容预览：</span>
                      <p class="text-gray-700 mt-1 italic">{{ item.content.preview }}</p>
                    </div>
                  </div>

                  <!-- Reviewer内容 -->
                  <div v-if="item.agent === 'reviewer' && item.content" class="text-sm space-y-2">
                    <div class="flex items-center gap-4 bg-white bg-opacity-50 p-2 rounded">
                      <div>
                        <span class="font-medium">评分：</span>
                        <span class="text-lg font-bold" :class="item.content.score >= 80 ? 'text-green-600' : 'text-orange-600'">
                          {{ item.content.score || 'N/A' }}
                        </span>
                      </div>
                      <div>
                        <span class="font-medium">状态：</span>
                        <span :class="item.content.approved ? 'text-green-600' : 'text-red-600'">
                          {{ item.content.approved ? '✅ 通过' : '❌ 未通过' }}
                        </span>
                      </div>
                    </div>
                    <div v-if="item.content.feedback" class="bg-white bg-opacity-50 p-2 rounded">
                      <span class="font-medium">反馈：</span>
                      <p class="text-gray-700 mt-1">{{ truncateText(item.content.feedback, 200) }}</p>
                    </div>
                    <div v-if="item.content.suggestions && item.content.suggestions.length > 0" class="bg-white bg-opacity-50 p-2 rounded">
                      <span class="font-medium">修改建议：</span>
                      <ul class="list-disc list-inside mt-1 text-gray-700">
                        <li v-for="(suggestion, idx) in item.content.suggestions.slice(0, 3)" :key="idx">
                          {{ truncateText(suggestion, 100) }}
                        </li>
                      </ul>
                    </div>
                  </div>

                  <!-- Summarizer内容 -->
                  <div v-if="item.agent === 'summarizer' && item.content" class="text-sm">
                    <div class="bg-white bg-opacity-50 p-2 rounded">
                      <span class="font-medium">摘要：</span>
                      <p class="text-gray-700 mt-1">{{ truncateText(item.content.summary, 200) }}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 原始JSON -->
            <details class="border rounded-lg p-4">
              <summary class="cursor-pointer font-semibold text-gray-800">🔍 查看原始JSON</summary>
              <pre class="mt-3 text-xs bg-gray-100 p-4 rounded overflow-auto max-h-96">{{ JSON.stringify(metadata, null, 2) }}</pre>
            </details>
          </div>

          <div v-else class="text-center py-12 text-gray-500">
            <svg class="w-16 h-16 mx-auto mb-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
            </svg>
            <p>该章节没有生成详情</p>
            <p class="text-sm mt-2">（可能是手动编辑的章节或使用旧版本生成）</p>
          </div>
        </div>

        <!-- 模态框底部 -->
        <div class="flex items-center justify-end gap-3 p-6 border-t border-gray-200">
          <button
            @click="showMetadataModal = false"
            class="px-4 py-2 text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 rounded-lg transition-colors"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Chapter } from '@/api/novel'

interface Props {
  selectedChapter: Chapter
}

const props = defineProps<Props>()

defineEmits(['showVersionSelector'])

const showMetadataModal = ref(false)

const metadata = computed(() => {
  // 获取选中版本的metadata
  if (props.selectedChapter.selected_version_metadata) {
    return props.selectedChapter.selected_version_metadata
  }
  // 如果没有，尝试从versions中获取
  if (props.selectedChapter.versions && props.selectedChapter.versions.length > 0) {
    const selectedVersion = props.selectedChapter.versions.find(v => v.id === props.selectedChapter.selected_version_id)
    return selectedVersion?.metadata || null
  }
  return null
})

const hasMetadata = computed(() => {
  return metadata.value && Object.keys(metadata.value).length > 0
})

const cleanVersionContent = (content: string): string => {
  if (!content) return ''
  try {
    const parsed = JSON.parse(content)
    if (parsed && typeof parsed === 'object' && parsed.content) {
      content = parsed.content
    }
  } catch (error) {
    // not a json
  }
  let cleaned = content.replace(/^"|"$/g, '')
  cleaned = cleaned.replace(/\\n/g, '\n')
  cleaned = cleaned.replace(/\\"/g, '"')
  cleaned = cleaned.replace(/\\t/g, '\t')
  cleaned = cleaned.replace(/\\\\/g, '\\')
  return cleaned
}

const sanitizeFileName = (name: string): string => {
  return name.replace(/[\\/:*?"<>|]/g, '_')
}

const exportChapterAsTxt = (chapter?: Chapter | null) => {
  if (!chapter) return

  const title = chapter.title?.trim() || `第${chapter.chapter_number}章`
  const safeTitle = sanitizeFileName(title) || `chapter-${chapter.chapter_number}`
  const content = cleanVersionContent(chapter.content || '')
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${safeTitle}.txt`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

const formatTime = (seconds?: number): string => {
  if (!seconds) return 'N/A'
  if (seconds < 60) return `${seconds}秒`
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = Math.round(seconds % 60)
  return `${minutes}分${remainingSeconds}秒`
}

const formatTimestamp = (timestamp?: string): string => {
  if (!timestamp) return ''
  try {
    const date = new Date(timestamp)
    return date.toLocaleString('zh-CN', { 
      month: '2-digit', 
      day: '2-digit', 
      hour: '2-digit', 
      minute: '2-digit' 
    })
  } catch {
    return ''
  }
}

const getAgentIcon = (agent: string): string => {
  const icons: Record<string, string> = {
    'planner': '🤔',
    'writer': '✍️',
    'reviewer': '📝',
    'summarizer': '📄'
  }
  return icons[agent] || '🤖'
}

const getAgentName = (agent: string): string => {
  const names: Record<string, string> = {
    'planner': '思考Agent',
    'writer': '写作Agent',
    'reviewer': '审批Agent',
    'summarizer': '总结Agent'
  }
  return names[agent] || agent
}

const getAgentColor = (agent: string): string => {
  const colors: Record<string, string> = {
    'planner': 'bg-blue-50 border-blue-200',
    'writer': 'bg-green-50 border-green-200',
    'reviewer': 'bg-orange-50 border-orange-200',
    'summarizer': 'bg-purple-50 border-purple-200'
  }
  return colors[agent] || 'bg-gray-50 border-gray-200'
}

const truncateText = (text: string | undefined, maxLength: number): string => {
  if (!text) return ''
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}
</script>
