<template>
  <div class="scheduled-generator p-6 bg-gray-50 min-h-screen">
    <div class="max-w-7xl mx-auto">
      <!-- 头部 -->
      <div class="mb-6 flex justify-between items-center">
        <div>
          <h1 class="text-3xl font-bold text-gray-900">定时自动生成器</h1>
          <p class="text-gray-600 mt-1">批量自动生成小说，支持定时调度和番茄上传</p>
        </div>
        <div class="flex gap-3">
          <button
            v-if="config && config.enabled"
            @click="handlePause"
            :disabled="loading || config.status === 'paused'"
            class="px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 disabled:opacity-50"
          >
            {{ config.status === 'paused' ? '已暂停' : '暂停任务' }}
          </button>
          <button
            v-if="config && config.status === 'paused'"
            @click="handleResume"
            :disabled="loading"
            class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
          >
            恢复任务
          </button>
          <button
            v-if="config && !config.enabled"
            @click="handleStart"
            :disabled="loading || queueItems.length === 0"
            class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
          >
            启动定时任务
          </button>
          <button
            v-if="config && config.enabled"
            @click="handleStop"
            :disabled="loading"
            class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
          >
            停止任务
          </button>
          <button
            v-if="config"
            @click="handleTriggerNow"
            :disabled="loading || config.status === 'running' || queueItems.length === 0"
            class="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
          >
            立即触发
          </button>
        </div>
      </div>

      <!-- 加载状态 -->
      <div v-if="initialLoading" class="text-center py-20">
        <div class="w-12 h-12 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mx-auto mb-4"></div>
        <p class="text-gray-600">加载中...</p>
      </div>

      <!-- 主要内容 -->
      <div v-else class="space-y-6">
        <!-- 配置卡片 -->
        <div class="bg-white rounded-lg shadow p-6">
          <h2 class="text-xl font-semibold mb-4">定时配置</h2>
          <div v-if="!config || !config.id">
            <p class="text-gray-600 mb-4">尚未创建配置，请先完成配置并添加书籍到队列。</p>
            <button
              @click="showConfigModal = true"
              class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
            >
              创建配置
            </button>
          </div>
          <div v-else class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p class="text-sm text-gray-600">触发时间（太平洋时间）</p>
              <p class="text-lg font-semibold">
                {{ String(config.trigger_hour).padStart(2, '0') }}:{{String(config.trigger_minute).padStart(2, '0') }}
              </p>
              <p class="text-xs text-gray-500 mt-1">本地时间（根据下次运行）: {{ formatLocalNextRun(config.next_run_at) }}</p>
            </div>
            <div>
              <p class="text-sm text-gray-600">生成模式</p>
              <p class="text-lg font-semibold">{{ config.generation_mode === 'enhanced' ? '增强模式' : '基础模式' }}</p>
            </div>
            <div>
              <p class="text-sm text-gray-600">并发数量</p>
              <p class="text-lg font-semibold">{{ config.concurrent_books }} 本</p>
            </div>
            <div>
              <p class="text-sm text-gray-600">单本时长</p>
              <p class="text-lg font-semibold">{{ config.max_duration_per_book }} 分钟</p>
            </div>
            <div>
              <p class="text-sm text-gray-600">自动上传番茄</p>
              <p class="text-lg font-semibold">{{ config.auto_upload_fanqie ? '是' : '否' }}</p>
            </div>
            <div>
              <p class="text-sm text-gray-600">下次运行</p>
              <p class="text-lg font-semibold">{{ formatDateTime(config.next_run_at) }}</p>
            </div>
            <div>
              <p class="text-sm text-gray-600">上次运行</p>
              <p class="text-lg font-semibold">{{ formatDateTime(config.last_run_at) }}</p>
            </div>
            <div>
              <p class="text-sm text-gray-600">状态</p>
              <p class="text-lg font-semibold">
                <span
                  :class="{
                    'text-green-600': config.status === 'idle' && config.enabled,
                    'text-blue-600': config.status === 'running',
                    'text-yellow-600': config.status === 'paused',
                    'text-gray-600': !config.enabled
                  }"
                >
                  {{ getStatusText(config) }}
                </span>
              </p>
            </div>
            <div class="col-span-2 md:col-span-4 flex gap-2">
              <button
                @click="showConfigModal = true"
                class="px-3 py-1 text-sm bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
              >
                编辑配置
              </button>
            </div>
          </div>
        </div>

        <!-- 状态卡片 -->
        <div class="bg-white rounded-lg shadow p-6">
          <h2 class="text-xl font-semibold mb-4">运行状态</h2>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p class="text-sm text-gray-600">总运行次数</p>
              <p class="text-2xl font-bold text-indigo-600">{{ status?.total_stats.total_runs || 0 }}</p>
            </div>
            <div>
              <p class="text-sm text-gray-600">已处理书籍</p>
              <p class="text-2xl font-bold text-green-600">{{ status?.total_stats.total_books_processed || 0 }}</p>
            </div>
            <div>
              <p class="text-sm text-gray-600">成功</p>
              <p class="text-2xl font-bold text-blue-600">{{ status?.total_stats.total_books_success || 0 }}</p>
            </div>
            <div>
              <p class="text-sm text-gray-600">失败</p>
              <p class="text-2xl font-bold text-red-600">{{ status?.total_stats.total_books_failed || 0 }}</p>
            </div>
          </div>

          <p v-if="!status" class="text-sm text-gray-500 mt-3">启动定时任务后，将在此显示运行进度与统计。</p>

          <!-- 当前运行中的书籍 -->
          <div v-if="status?.currently_running && status.currently_running.length > 0" class="mt-6">
            <h3 class="text-lg font-semibold mb-3">正在生成</h3>
            <div class="space-y-2">
              <div
                v-for="item in status.currently_running"
                :key="item.novel_id"
                class="p-3 bg-blue-50 rounded border border-blue-200"
              >
                <p class="font-medium">小说 ID: {{ item.novel_id }}</p>
                <p class="text-sm text-gray-600">
                  进度: {{ item.chapters_generated }} / {{ item.chapters_target }} 章
                  <span v-if="item.started_at" class="ml-2">
                    开始于: {{ formatDateTime(item.started_at) }}
                  </span>
                </p>
              </div>
            </div>
          </div>
        </div>

        <!-- 队列管理 -->
        <div class="bg-white rounded-lg shadow p-6">
          <div class="flex justify-between items-center mb-4">
            <h2 class="text-xl font-semibold">书籍队列</h2>
            <button
              @click="showAddBookModal = true"
              class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
            >
              添加书籍
            </button>
          </div>

          <!-- 队列统计 -->
          <div v-if="status" class="grid grid-cols-5 gap-4 mb-4">
            <div class="text-center">
              <p class="text-sm text-gray-600">待处理</p>
              <p class="text-xl font-bold text-gray-700">{{ status.queue_stats.pending }}</p>
            </div>
            <div class="text-center">
              <p class="text-sm text-gray-600">处理中</p>
              <p class="text-xl font-bold text-blue-600">{{ status.queue_stats.running }}</p>
            </div>
            <div class="text-center">
              <p class="text-sm text-gray-600">已完成</p>
              <p class="text-xl font-bold text-green-600">{{ status.queue_stats.completed }}</p>
            </div>
            <div class="text-center">
              <p class="text-sm text-gray-600">失败</p>
              <p class="text-xl font-bold text-red-600">{{ status.queue_stats.failed }}</p>
            </div>
            <div class="text-center">
              <p class="text-sm text-gray-600">总计</p>
              <p class="text-xl font-bold text-indigo-600">{{ status.queue_stats.total }}</p>
            </div>
          </div>

          <!-- 队列列表 -->
          <div class="space-y-2">
            <div
              v-for="item in queueItems"
              :key="item.id"
              class="p-4 border rounded-lg hover:bg-gray-50"
              :class="{
                'border-blue-300 bg-blue-50': item.status === 'running',
                'border-green-300 bg-green-50': item.status === 'completed',
                'border-red-300 bg-red-50': item.status === 'failed',
                'border-gray-300': item.status === 'pending'
              }"
            >
              <div class="flex justify-between items-center">
                <div class="flex-1">
                  <p class="font-medium">小说 ID: {{ item.novel_id }}</p>
                  <p class="text-sm text-gray-600 mt-1">
                    状态: <span :class="getStatusClass(item.status)">{{ getQueueStatusText(item.status) }}</span>
                    | 优先级: {{ item.priority }}
                    | 位置: {{ item.position }}
                  </p>
                  <p v-if="item.status === 'running' || item.status === 'completed'" class="text-sm text-gray-600">
                    进度: {{ item.chapters_generated }} / {{ item.chapters_target }} 章
                    <span v-if="item.duration_seconds"> | 耗时: {{ formatDuration(item.duration_seconds) }}</span>
                  </p>
                  <p v-if="item.error_message" class="text-sm text-red-600 mt-1">
                    错误: {{ item.error_message }}
                  </p>
                  <p v-if="item.uploaded_to_fanqie" class="text-sm text-green-600 mt-1">
                    ✓ 已上传番茄小说
                  </p>
                </div>
                <div>
                  <button
                    v-if="item.status === 'pending'"
                    @click="removeFromQueue(item.id)"
                    class="px-3 py-1 text-sm bg-red-500 text-white rounded hover:bg-red-600"
                  >
                    移除
                  </button>
                </div>
              </div>
            </div>
            <div v-if="queueItems.length === 0" class="text-center py-10 text-gray-500">
              队列为空，请添加书籍
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 配置编辑 Modal -->
    <ConfigModal
      v-if="showConfigModal"
      :config="config"
      @close="showConfigModal = false"
      @saved="handleConfigSaved"
    />

    <!-- 添加书籍 Modal -->
    <AddBookModal
      v-if="showAddBookModal"
      @close="showAddBookModal = false"
      @added="handleBooksAdded"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { scheduledGeneratorApi, type ScheduledGeneratorConfig, type QueueItem, type SchedulerStatus } from '@/api/scheduled-generator'
import ConfigModal from './ScheduledGenerator/ConfigModal.vue'
import AddBookModal from './ScheduledGenerator/AddBookModal.vue'

const initialLoading = ref(true)
const loading = ref(false)
const config = ref<ScheduledGeneratorConfig | null>(null)
const queueItems = ref<QueueItem[]>([])
const status = ref<SchedulerStatus | null>(null)
const showConfigModal = ref(false)
const showAddBookModal = ref(false)

let statusInterval: number | null = null

// 加载配置
const loadConfig = async () => {
  try {
    config.value = await scheduledGeneratorApi.getConfig()
  } catch (error) {
    console.log('No config found, will create one')
  }
}

// 加载队列
const loadQueue = async () => {
  try {
    queueItems.value = await scheduledGeneratorApi.getQueue()
  } catch (error) {
    console.error('Failed to load queue:', error)
  }
}

// 加载状态
const loadStatus = async () => {
  try {
    status.value = await scheduledGeneratorApi.getStatus()
  } catch (error) {
    console.error('Failed to load status:', error)
  }
}

// 刷新所有数据
const refreshAll = async () => {
  await Promise.all([loadConfig(), loadQueue(), loadStatus()])
}

// 启动任务
const handleStart = async () => {
  loading.value = true
  try {
    await scheduledGeneratorApi.start()
    await refreshAll()
    alert('定时任务已启动')
  } catch (error: any) {
    alert(`启动失败: ${error.message}`)
  } finally {
    loading.value = false
  }
}

// 暂停任务
const handlePause = async () => {
  loading.value = true
  try {
    await scheduledGeneratorApi.pause()
    await refreshAll()
    alert('任务已暂停')
  } catch (error: any) {
    alert(`暂停失败: ${error.message}`)
  } finally {
    loading.value = false
  }
}

// 恢复任务
const handleResume = async () => {
  loading.value = true
  try {
    await scheduledGeneratorApi.resume()
    await refreshAll()
    alert('任务已恢复')
  } catch (error: any) {
    alert(`恢复失败: ${error.message}`)
  } finally {
    loading.value = false
  }
}

// 停止任务
const handleStop = async () => {
  if (!confirm('确定要停止定时任务吗？')) return
  loading.value = true
  try {
    await scheduledGeneratorApi.stop()
    await refreshAll()
    alert('任务已停止')
  } catch (error: any) {
    alert(`停止失败: ${error.message}`)
  } finally {
    loading.value = false
  }
}

// 立即触发
const handleTriggerNow = async () => {
  if (!confirm('确定要立即触发一次生成吗？')) return
  loading.value = true
  try {
    await scheduledGeneratorApi.triggerNow()
    await refreshAll()
    alert('已触发生成任务')
  } catch (error: any) {
    alert(`触发失败: ${error.message}`)
  } finally {
    loading.value = false
  }
}

// 移除队列项
const removeFromQueue = async (itemId: number) => {
  if (!confirm('确定要移除这本书吗？')) return
  try {
    await scheduledGeneratorApi.removeFromQueue(itemId)
    await loadQueue()
  } catch (error: any) {
    alert(`移除失败: ${error.message}`)
  }
}

// 配置保存回调
const handleConfigSaved = async () => {
  showConfigModal.value = false
  await refreshAll()
}

// 书籍添加回调
const handleBooksAdded = async () => {
  showAddBookModal.value = false
  await loadQueue()
}

// 格式化日期时间
const formatDateTime = (dt: string | null) => {
  if (!dt) return '-'
  return new Date(dt).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 将 next_run_at 转成本地时间展示
const formatLocalNextRun = (dt: string | null) => {
  if (!dt) return '启动后显示'
  return formatDateTime(dt)
}

// 格式化时长
const formatDuration = (seconds: number) => {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60
  if (hours > 0) {
    return `${hours}小时${minutes}分钟`
  } else if (minutes > 0) {
    return `${minutes}分钟${secs}秒`
  } else {
    return `${secs}秒`
  }
}

// 获取状态文本
const getStatusText = (config: ScheduledGeneratorConfig) => {
  if (!config.enabled) return '未启动'
  if (config.status === 'running') return '运行中'
  if (config.status === 'paused') return '已暂停'
  return '等待中'
}

// 获取队列状态文本
const getQueueStatusText = (status: string) => {
  const map: Record<string, string> = {
    pending: '待处理',
    running: '处理中',
    completed: '已完成',
    failed: '失败',
    skipped: '已跳过'
  }
  return map[status] || status
}

// 获取状态样式
const getStatusClass = (status: string) => {
  const map: Record<string, string> = {
    pending: 'text-gray-600',
    running: 'text-blue-600',
    completed: 'text-green-600',
    failed: 'text-red-600',
    skipped: 'text-yellow-600'
  }
  return map[status] || 'text-gray-600'
}

// 初始化
onMounted(async () => {
  await refreshAll()
  initialLoading.value = false

  // 每10秒刷新状态
  statusInterval = window.setInterval(async () => {
    await loadStatus()
    await loadQueue()
  }, 10000)
})

// 清理
onUnmounted(() => {
  if (statusInterval) {
    clearInterval(statusInterval)
  }
})
</script>

<style scoped>
/* 自定义样式 */
</style>
