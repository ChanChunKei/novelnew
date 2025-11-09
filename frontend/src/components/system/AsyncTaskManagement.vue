<template>
  <div class="async-task-management">
    <div class="header">
      <h2 class="title">异步分析任务</h2>
      <div class="filters">
        <select v-model="statusFilter" @change="loadTasks" class="filter-select">
          <option value="">全部状态</option>
          <option value="pending">等待中</option>
          <option value="running">运行中</option>
          <option value="completed">已完成</option>
          <option value="failed">失败</option>
        </select>
        <button @click="loadTasks" class="btn-refresh">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          刷新
        </button>
      </div>
    </div>

    <!-- Task List -->
    <div class="task-list">
      <div v-for="task in tasks" :key="task.id" class="task-card">
        <div class="task-header">
          <div class="task-info">
            <h3 class="task-title">{{ task.task_type }}</h3>
            <p class="task-id">ID: {{ task.id }}</p>
          </div>
          <span :class="['status-badge', `status-${task.status}`]">
            {{ statusText(task.status) }}
          </span>
        </div>

        <div class="task-details">
          <div class="detail-item">
            <span class="detail-label">项目:</span>
            <span class="detail-value">{{ task.project_name || task.project_id }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">创建时间:</span>
            <span class="detail-value">{{ formatDate(task.created_at) }}</span>
          </div>
          <div v-if="task.completed_at" class="detail-item">
            <span class="detail-label">完成时间:</span>
            <span class="detail-value">{{ formatDate(task.completed_at) }}</span>
          </div>
          <div v-if="task.progress" class="detail-item">
            <span class="detail-label">进度:</span>
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: task.progress + '%' }"></div>
              <span class="progress-text">{{ task.progress }}%</span>
            </div>
          </div>
        </div>

        <div v-if="task.error" class="task-error">
          <svg class="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span class="error-text">{{ task.error }}</span>
        </div>

        <div class="task-actions">
          <button v-if="task.status === 'completed'" @click="viewResult(task)" class="btn-view">
            查看结果
          </button>
          <button v-if="task.status === 'pending' || task.status === 'running'" @click="cancelTask(task)" class="btn-cancel">
            取消任务
          </button>
        </div>
      </div>

      <div v-if="tasks.length === 0" class="empty-state">
        <svg class="w-16 h-16 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
        </svg>
        <p class="text-slate-500 mt-4">暂无任务</p>
      </div>
    </div>

    <!-- Result Modal -->
    <div v-if="viewingTask" class="modal-overlay" @click.self="closeModal">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="modal-title">任务结果</h3>
          <button @click="closeModal" class="modal-close">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <pre class="result-content">{{ JSON.stringify(viewingTask.result, null, 2) }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { asyncAnalysisApi } from '@/api/novel'

const tasks = ref<any[]>([])
const statusFilter = ref('')
const viewingTask = ref<any>(null)

const statusText = (status: string) => {
  const map: Record<string, string> = {
    pending: '等待中',
    running: '运行中',
    completed: '已完成',
    failed: '失败'
  }
  return map[status] || status
}

const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleString('zh-CN')
}

const loadTasks = async () => {
  try {
    tasks.value = await asyncAnalysisApi.getTasks(statusFilter.value)
  } catch (error: any) {
    console.error('加载任务失败:', error)
  }
}

const viewResult = (task: any) => {
  viewingTask.value = task
}

const cancelTask = async (task: any) => {
  if (!confirm('确定要取消此任务吗？')) return
  
  try {
    await asyncAnalysisApi.cancelTask(task.id)
    await loadTasks()
  } catch (error: any) {
    console.error('取消任务失败:', error)
  }
}

const closeModal = () => {
  viewingTask.value = null
}

// ✅ 修复：保存定时器引用，防止内存泄漏
let refreshTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  loadTasks()
  // 每30秒自动刷新
  refreshTimer = setInterval(loadTasks, 30000)
})

// ✅ 修复：组件卸载时清理定时器
onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>


