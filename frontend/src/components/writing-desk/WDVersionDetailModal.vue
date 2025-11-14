<template>
  <div v-if="show" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
    <div class="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[80vh] overflow-hidden">
      <!-- 弹窗头部 -->
      <div class="flex items-center justify-between p-6 border-b border-gray-200">
        <div>
          <h3 class="text-xl font-bold text-gray-900">版本详情</h3>
          <p class="text-sm text-gray-600 mt-1">
            版本 {{ detailVersionIndex + 1 }}
            <span class="text-gray-400">•</span>
            {{ version?.style || '标准' }}风格
            <span class="text-gray-400">•</span>
            约 {{ Math.round(cleanVersionContent(version?.content || '').length / 100) * 100 }} 字
          </p>
        </div>
        <button
          @click="$emit('close')"
          class="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
          </svg>
        </button>
      </div>

      <!-- 弹窗内容 -->
      <div class="p-6 overflow-y-auto max-h-[60vh]">
        <!-- 3Agent Metadata展示 -->
        <div v-if="versionMetadata" class="mb-6 space-y-4">
          <!-- 生成概览 -->
          <div class="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg p-4 border border-blue-200">
            <h4 class="font-semibold text-gray-800 mb-3 flex items-center gap-2">
              <span>🤖</span>
              <span>3Agent生成详情</span>
            </h4>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div>
                <div class="text-xs text-gray-600">迭代次数</div>
                <div class="text-lg font-bold text-blue-600">{{ versionMetadata.iterations || 'N/A' }}</div>
              </div>
              <div>
                <div class="text-xs text-gray-600">最终评分</div>
                <div class="text-lg font-bold text-green-600">{{ versionMetadata.final_score || 'N/A' }}</div>
              </div>
              <div>
                <div class="text-xs text-gray-600">生成耗时</div>
                <div class="text-lg font-bold text-purple-600">{{ formatTime(versionMetadata.total_time_seconds) }}</div>
              </div>
              <div>
                <div class="text-xs text-gray-600">对话轮次</div>
                <div class="text-lg font-bold text-orange-600">{{ versionMetadata.conversation_history?.length || 0 }}</div>
              </div>
            </div>
          </div>

          <!-- 对话历史摘要 -->
          <details v-if="versionMetadata.conversation_history" class="border rounded-lg p-3 bg-gray-50">
            <summary class="cursor-pointer font-medium text-gray-700 text-sm">
              💬 查看完整生成过程（{{ versionMetadata.conversation_history.length }}个步骤）
            </summary>
            <div class="mt-3 space-y-2 max-h-60 overflow-y-auto">
              <div
                v-for="(item, index) in versionMetadata.conversation_history"
                :key="index"
                class="text-xs border rounded p-2"
                :class="getAgentColor(item.agent)"
              >
                <div class="flex items-center gap-2 mb-1">
                  <span>{{ getAgentIcon(item.agent) }}</span>
                  <span class="font-semibold text-xs">{{ getAgentName(item.agent) }}</span>
                  <span v-if="item.iteration" class="text-xs bg-gray-200 px-1.5 py-0.5 rounded">第{{ item.iteration }}轮</span>
                </div>
                
                <!-- 简化显示 -->
                <div v-if="item.agent === 'planner' && item.content" class="text-xs text-gray-600">
                  {{ truncateText(item.content.analysis || item.content.plan || '分析完成', 80) }}
                </div>
                <div v-if="item.agent === 'writer' && item.content" class="text-xs text-gray-600">
                  字数: {{ item.content.word_count || 'N/A' }}
                </div>
                <div v-if="item.agent === 'reviewer' && item.content" class="text-xs">
                  <span :class="item.content.approved ? 'text-green-600' : 'text-red-600'">
                    {{ item.content.approved ? '✅' : '❌' }} 评分: {{ item.content.score || 'N/A' }}
                  </span>
                </div>
              </div>
            </div>
          </details>
        </div>

        <!-- 章节内容 -->
        <div class="prose max-w-none">
          <div class="whitespace-pre-wrap text-gray-700 leading-relaxed">
            {{ cleanVersionContent(version?.content || '') }}
          </div>
        </div>
      </div>

      <!-- 弹窗底部操作按钮 -->
      <div class="flex items-center justify-between p-6 border-t border-gray-200 bg-gray-50">
        <div class="text-sm text-gray-500">
          <span v-if="isCurrent" class="inline-flex items-center px-2 py-1 rounded-full bg-green-100 text-green-800 font-medium">
            <svg class="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path>
            </svg>
            当前选中版本
          </span>
          <span v-else class="text-gray-400">未选中版本</span>
        </div>

        <div class="flex gap-3">
          <button
            @click="$emit('close')"
            class="px-4 py-2 text-gray-600 hover:text-gray-800 hover:bg-gray-200 rounded-lg transition-colors"
          >
            关闭
          </button>
          <button
            v-if="!isCurrent"
            @click="$emit('selectVersion')"
            class="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
          >
            选择此版本
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ChapterVersion } from '@/api/novel'
import { computed } from 'vue'
import { cleanVersionContent } from '@/utils/textUtils'

interface Props {
  show: boolean
  detailVersionIndex: number
  version: ChapterVersion | null
  isCurrent: boolean
  versionMetadata?: Record<string, any> | null  // ✅ 新增：3Agent metadata
}

const props = defineProps<Props>()

defineEmits(['close', 'selectVersion'])

// cleanVersionContent 已移至 @/utils/textUtils

const formatTime = (seconds?: number): string => {
  if (!seconds) return 'N/A'
  if (seconds < 60) return `${seconds}秒`
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = Math.round(seconds % 60)
  return `${minutes}分${remainingSeconds}秒`
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
