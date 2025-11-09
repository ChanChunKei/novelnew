<template>
  <div class="batch-scheduler">
    <div class="panel-header">
      <h2>📅 批量任务调度中心</h2>
      <p class="subtitle">智能错开任务启动时间，避免并发冲突，提升系统稳定性</p>
    </div>

    <!-- 正在运行的任务监控 -->
    <div class="running-tasks-panel">
      <div class="panel-title-row">
        <h3>🔄 正在执行的任务</h3>
        <button @click="refreshRunningTasks" class="btn-refresh" :disabled="loading">
          🔄 刷新
        </button>
      </div>

      <div v-if="runningTasks.length === 0" class="empty-state">
        <span class="empty-icon">😴</span>
        <p>暂无运行中的任务</p>
      </div>

      <div v-else class="running-tasks-grid">
        <div
          v-for="task in runningTasks"
          :key="task.id"
          class="task-card"
          :class="task.status"
        >
          <div class="task-header">
            <span class="task-status-badge" :class="task.status">
              {{ getStatusText(task.status) }}
            </span>
            <span class="task-project">{{ getProjectName(task.project_id) }}</span>
          </div>
          <div class="task-stats">
            <div class="stat">
              <span class="stat-label">已生成</span>
              <span class="stat-value">{{ task.chapters_generated }} 章</span>
            </div>
            <div class="stat">
              <span class="stat-label">生成间隔</span>
              <span class="stat-value">{{ formatInterval(task.interval_seconds) }}</span>
            </div>
            <div v-if="task.scheduled_start_time" class="stat">
              <span class="stat-label">启动倒计时</span>
              <span class="stat-value countdown" :class="getCountdownClass(task.scheduled_start_time)">
                {{ getCountdown(task.scheduled_start_time) }}
              </span>
            </div>
          </div>
          <div class="task-actions">
            <button
              v-if="task.status === 'running'"
              @click="pauseTask(task.id)"
              class="btn-small btn-warning"
            >
              ⏸️ 暂停
            </button>
            <button
              v-if="task.status === 'paused'"
              @click="startTask(task.id)"
              class="btn-small btn-success"
            >
              ▶️ 继续
            </button>
            <button
              @click="stopTask(task.id)"
              class="btn-small btn-danger"
            >
              ⏹️ 停止
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 批量创建表单 -->
    <div class="create-form">
      <h3>🚀 批量启动任务</h3>

      <div class="info-banner">
        <span class="info-icon">💡</span>
        <div class="info-content">
          <strong>智能调度算法</strong>
          <p>系统会自动计算最佳启动间隔（默认5分钟），让任务错开执行，避免 SQLite 写锁竞争</p>
        </div>
      </div>

      <!-- 项目选择 -->
      <div class="form-group">
        <label>📚 选择项目</label>
        <div class="project-selector">
          <div class="selector-header">
            <button @click="selectAllProjects" class="btn-link">全选</button>
            <button @click="deselectAllProjects" class="btn-link">取消全选</button>
            <span class="selected-count">已选择 {{ selectedProjectIds.length }} 个项目</span>
          </div>
          <div class="project-list">
            <label
              v-for="project in allProjects"
              :key="project.id"
              class="project-item"
              :class="{
                selected: selectedProjectIds.includes(project.id),
                'has-task': projectHasRunningTask(project.id)
              }"
            >
              <input
                type="checkbox"
                :value="project.id"
                v-model="selectedProjectIds"
              />
              <div class="project-info">
                <span class="project-name">{{ project.title }}</span>
                <span v-if="projectHasRunningTask(project.id)" class="task-indicator">
                  ⚠️ 已有运行中任务
                </span>
              </div>
            </label>
          </div>
        </div>
        <span class="hint">
          如果项目已有运行中的任务，系统会自动停止旧任务再创建新任务
        </span>
      </div>

      <div class="form-group">
        <label>🕐 生成间隔</label>
        <div class="interval-input-group">
          <select v-model="form.generationInterval" class="interval-select">
            <option :value="null">自动计算（推荐）</option>
            <option
              v-for="option in generationIntervals"
              :key="option.value"
              :value="option.value"
            >
              {{ option.display }}
            </option>
          </select>
          <span class="input-separator">或</span>
          <input
            v-model="form.customInterval"
            type="text"
            class="custom-interval-input"
            placeholder="手动输入，如：1分钟、2小时、30秒"
            @input="() => { if (form.customInterval) form.generationInterval = null }"
          />
        </div>
        <span class="hint">
          每个任务生成一章后等待的时间。可以从下拉框选择预设值，或手动输入自定义时间（支持：秒/分钟/小时/天）
        </span>
      </div>

      <div class="form-group">
        <label>
          <input v-model="form.autoUpload" type="checkbox" />
          自动上传到番茄小说
        </label>
      </div>

      <div v-if="form.autoUpload" class="form-group">
        <label>番茄小说账号</label>
        <input
          v-model="form.fanqieAccount"
          type="text"
          placeholder="请输入账号名称（如：default）"
        />
      </div>

      <button
        @click="createBatchTasks"
        class="btn-primary btn-large"
        :disabled="loading || selectedProjectIds.length === 0"
      >
        {{ loading ? '创建中...' : `🚀 启动选中的 ${selectedProjectIds.length} 个项目` }}
      </button>
    </div>

    <!-- 调度计划 -->
    <div v-if="scheduleResult" class="schedule-result">
      <h3>📊 调度计划</h3>

      <div class="schedule-summary">
        <div class="summary-item">
          <span class="summary-label">已创建任务</span>
          <span class="summary-value">{{ scheduleResult.tasks_created }} 个</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">启动间隔</span>
          <span class="summary-value">{{ scheduleResult.start_interval / 60 }} 分钟</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">生成间隔</span>
          <span class="summary-value">{{ formatInterval(scheduleResult.generation_interval) }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">建议并发数</span>
          <span class="summary-value">≤ {{ scheduleResult.max_concurrent }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">完成启动时间</span>
          <span class="summary-value">{{ Math.round(scheduleResult.estimated_cycle_time / 60) }} 分钟</span>
        </div>
      </div>

      <div class="schedule-table">
        <table>
          <thead>
            <tr>
              <th>项目</th>
              <th>预计启动时间</th>
              <th>倒计时</th>
              <th>生成间隔</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="task in scheduleResult.schedule"
              :key="task.task_id"
            >
              <td class="project-cell">
                <div class="project-name">{{ task.project_title }}</div>
                <div class="project-id">{{ task.project_id }}</div>
              </td>
              <td>{{ formatDateTime(task.scheduled_start_time) }}</td>
              <td>
                <span :class="getCountdownClass(task.scheduled_start_time)">
                  {{ getCountdown(task.scheduled_start_time) }}
                </span>
              </td>
              <td>{{ formatInterval(task.interval_seconds) }}</td>
              <td>
                <button
                  @click="editTask(task)"
                  class="btn-edit"
                >
                  ✏️ 调整
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 编辑任务模态框 -->
    <div v-if="editingTask" class="modal-overlay" @click="closeEditModal">
      <div class="modal-content" @click.stop>
        <h3>⚙️ 调整任务调度</h3>

        <div class="modal-body">
          <p class="task-title">{{ editingTask.project_title }}</p>

          <div class="form-group">
            <label>启动延迟</label>
            <select v-model="editForm.delaySeconds" class="interval-select">
              <option
                v-for="option in startDelays"
                :key="option.value"
                :value="option.value"
              >
                {{ option.display }}
              </option>
            </select>
          </div>

          <div class="form-group">
            <label>生成间隔</label>
            <select v-model="editForm.intervalSeconds" class="interval-select">
              <option
                v-for="option in generationIntervals"
                :key="option.value"
                :value="option.value"
              >
                {{ option.display }}
              </option>
            </select>
          </div>
        </div>

        <div class="modal-footer">
          <button @click="closeEditModal" class="btn-secondary">取消</button>
          <button @click="updateTaskSchedule" class="btn-primary" :disabled="loading">
            {{ loading ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { api } from '@/api/base'

interface ScheduleOption {
  value: number
  label: string
  display: string
}

interface Project {
  id: string
  title: string
}

interface Task {
  id: number
  project_id: string
  status: string
  chapters_generated: number
  interval_seconds: number
  scheduled_start_time?: string
}

interface TaskSchedule {
  project_id: string
  project_title: string
  task_id: number
  scheduled_start_time: string
  delay_seconds: number
  interval_seconds: number
}

interface ScheduleResult {
  batch_id: string
  tasks_created: number
  start_interval: number
  generation_interval: number
  max_concurrent: number
  estimated_cycle_time: number
  schedule: TaskSchedule[]
}

const loading = ref(false)
const generationIntervals = ref<ScheduleOption[]>([])
const startDelays = ref<ScheduleOption[]>([])
const allProjects = ref<Project[]>([])
const selectedProjectIds = ref<string[]>([])
const runningTasks = ref<Task[]>([])
const scheduleResult = ref<ScheduleResult | null>(null)
const editingTask = ref<TaskSchedule | null>(null)
const countdownInterval = ref<number | null>(null)
const currentTime = ref(Date.now())

const form = ref({
  generationInterval: null as number | null,
  customInterval: '',  // 自定义生成间隔（支持手动输入）
  autoUpload: false,
  fanqieAccount: 'default'
})

const editForm = ref({
  delaySeconds: 0,
  intervalSeconds: 3600
})

// 解析时间字符串（支持 "1分钟", "2小时", "30秒" 等格式）
const parseTimeString = (timeStr: string): number | null => {
  if (!timeStr || timeStr.trim() === '') {
    return null
  }

  const str = timeStr.trim()

  // 匹配数字 + 单位
  const patterns = [
    { regex: /^(\d+)\s*秒/, multiplier: 1 },
    { regex: /^(\d+)\s*分(钟)?/, multiplier: 60 },
    { regex: /^(\d+)\s*小时/, multiplier: 3600 },
    { regex: /^(\d+)\s*天/, multiplier: 86400 },
    { regex: /^(\d+)\s*s(ec|econds?)?$/i, multiplier: 1 },
    { regex: /^(\d+)\s*m(in|inutes?)?$/i, multiplier: 60 },
    { regex: /^(\d+)\s*h(our|ours)?$/i, multiplier: 3600 },
    { regex: /^(\d+)\s*d(ay|ays)?$/i, multiplier: 86400 }
  ]

  for (const pattern of patterns) {
    const match = str.match(pattern.regex)
    if (match) {
      const value = parseInt(match[1], 10)
      return value * pattern.multiplier
    }
  }

  // 如果只是纯数字，默认当作秒
  const pureNumber = parseInt(str, 10)
  if (!isNaN(pureNumber) && pureNumber > 0) {
    return pureNumber
  }

  return null
}

// 加载所有项目
const loadProjects = async () => {
  try {
    const projects = await api.get('/api/novels')

    // ✅ 过滤：只显示已命名的项目，排除未命名灵感
    const validProjects = projects.filter((p: any) => {
      return p.title &&
             p.title.trim() !== '' &&
             !p.title.match(/^(新项目|未命名|Untitled|New Project|未命名灵感)$/i)
    })

    allProjects.value = validProjects
    // 默认全选
    selectedProjectIds.value = validProjects.map((p: Project) => p.id)

    if (validProjects.length < projects.length) {
      console.info(`过滤掉 ${projects.length - validProjects.length} 个未命名的灵感项目`)
    }
  } catch (error) {
    console.error('加载项目列表失败:', error)
  }
}

// 加载正在运行的任务
const refreshRunningTasks = async () => {
  try {
    // 获取所有项目的任务
    const tasksPromises = allProjects.value.map(project =>
      api.get(`/api/auto-generator/projects/${project.id}/tasks`)
    )
    const tasksArrays = await Promise.all(tasksPromises)

    // 合并所有任务并过滤出运行中的
    const allTasks = tasksArrays.flat()
    runningTasks.value = allTasks.filter((task: Task) =>
      task.status === 'running' || task.status === 'paused' || task.status === 'pending'
    )
  } catch (error) {
    console.error('加载运行中任务失败:', error)
  }
}

// 加载调度选项
const loadScheduleOptions = async () => {
  try {
    const options = await api.get('/api/auto-generator/schedule-options')
    generationIntervals.value = options.generation_intervals
    startDelays.value = options.start_delays
  } catch (error) {
    console.error('加载调度选项失败:', error)
  }
}

// 全选项目
const selectAllProjects = () => {
  selectedProjectIds.value = allProjects.value.map(p => p.id)
}

// 取消全选
const deselectAllProjects = () => {
  selectedProjectIds.value = []
}

// 检查项目是否有运行中的任务
const projectHasRunningTask = (projectId: string): boolean => {
  return runningTasks.value.some(task => task.project_id === projectId)
}

// 获取项目名称
const getProjectName = (projectId: string): string => {
  const project = allProjects.value.find(p => p.id === projectId)
  return project?.title || projectId
}

// 停止已有任务
const stopExistingTasks = async (projectIds: string[]): Promise<void> => {
  const tasksToStop = runningTasks.value.filter(task =>
    projectIds.includes(task.project_id)
  )

  if (tasksToStop.length > 0) {
    const message = `检测到 ${tasksToStop.length} 个项目已有运行中的任务，将自动停止这些任务后重新创建。是否继续？`
    if (!confirm(message)) {
      throw new Error('用户取消操作')
    }

    // 停止所有冲突任务（串行执行，避免SQLite数据库锁）
    for (const task of tasksToStop) {
      try {
        await api.post(`/api/auto-generator/tasks/${task.id}/stop`)
        // 每次停止后等待200ms，给数据库喘息时间
        await new Promise(resolve => setTimeout(resolve, 200))
      } catch (error) {
        console.error(`停止任务 ${task.id} 失败:`, error)
        // 继续停止其他任务
      }
    }

    // 等待1秒确保任务完全停止
    await new Promise(resolve => setTimeout(resolve, 1000))
  }
}

// 创建批量任务
const createBatchTasks = async () => {
  if (selectedProjectIds.value.length === 0) {
    alert('请至少选择一个项目')
    return
  }

  // 优先使用自定义输入的时间
  let generationInterval = form.value.generationInterval
  if (form.value.customInterval) {
    const parsed = parseTimeString(form.value.customInterval)
    if (parsed === null) {
      alert('时间格式不正确，请输入如：1分钟、2小时、30秒')
      return
    }
    generationInterval = parsed
  }

  loading.value = true
  try {
    // 先停止已有任务
    await stopExistingTasks(selectedProjectIds.value)

    const result = await api.post('/api/auto-generator/batch-tasks', {
      project_ids: selectedProjectIds.value,
      generation_interval: generationInterval,
      auto_start: true,
      auto_upload: form.value.autoUpload,
      fanqie_account: form.value.autoUpload ? form.value.fanqieAccount : null
    })

    scheduleResult.value = result
    startCountdown()

    // 刷新运行中任务列表
    await refreshRunningTasks()
  } catch (error: any) {
    if (error.message !== '用户取消操作') {
      alert('创建批量任务失败: ' + (error.message || '未知错误'))
    }
  } finally {
    loading.value = false
  }
}

// 启动任务
const startTask = async (taskId: number) => {
  try {
    await api.post(`/api/auto-generator/tasks/${taskId}/start`)
    await refreshRunningTasks()
  } catch (error: any) {
    alert('启动任务失败: ' + (error.message || '未知错误'))
  }
}

// 暂停任务
const pauseTask = async (taskId: number) => {
  try {
    await api.post(`/api/auto-generator/tasks/${taskId}/pause`)
    await refreshRunningTasks()
  } catch (error: any) {
    alert('暂停任务失败: ' + (error.message || '未知错误'))
  }
}

// 停止任务
const stopTask = async (taskId: number) => {
  if (!confirm('确定要停止这个任务吗？')) return

  try {
    await api.post(`/api/auto-generator/tasks/${taskId}/stop`)
    await refreshRunningTasks()
  } catch (error: any) {
    alert('停止任务失败: ' + (error.message || '未知错误'))
  }
}

// 编辑任务
const editTask = (task: TaskSchedule) => {
  editingTask.value = task
  editForm.value = {
    delaySeconds: task.delay_seconds,
    intervalSeconds: task.interval_seconds
  }
}

// 关闭编辑模态框
const closeEditModal = () => {
  editingTask.value = null
}

// 更新任务调度
const updateTaskSchedule = async () => {
  if (!editingTask.value) return

  loading.value = true
  try {
    await api.patch(`/api/auto-generator/tasks/${editingTask.value.task_id}/schedule`, {
      delay_seconds: editForm.value.delaySeconds,
      interval_seconds: editForm.value.intervalSeconds
    })

    // 更新本地数据
    if (scheduleResult.value) {
      const task = scheduleResult.value.schedule.find(t => t.task_id === editingTask.value!.task_id)
      if (task) {
        task.delay_seconds = editForm.value.delaySeconds
        task.interval_seconds = editForm.value.intervalSeconds
        // 重新计算启动时间
        const now = new Date()
        task.scheduled_start_time = new Date(now.getTime() + editForm.value.delaySeconds * 1000).toISOString()
      }
    }

    closeEditModal()
    await refreshRunningTasks()
  } catch (error: any) {
    alert('更新任务失败: ' + (error.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

// 格式化时间间隔
const formatInterval = (seconds: number): string => {
  if (seconds < 60) return `${seconds}秒`
  if (seconds < 3600) return `${Math.round(seconds / 60)}分钟`
  if (seconds < 86400) return `${Math.round(seconds / 3600)}小时`
  return `${Math.round(seconds / 86400)}天`
}

// 格式化日期时间
const formatDateTime = (isoString: string): string => {
  return new Date(isoString).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// 获取状态文本
const getStatusText = (status: string): string => {
  const statusMap: Record<string, string> = {
    pending: '等待中',
    running: '运行中',
    paused: '已暂停',
    stopped: '已停止',
    completed: '已完成'
  }
  return statusMap[status] || status
}

// 计算倒计时
const getCountdown = (scheduledTime: string): string => {
  const now = currentTime.value
  const target = new Date(scheduledTime).getTime()
  const diff = target - now

  if (diff <= 0) return '已开始'

  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)

  if (days > 0) return `${days}天${hours % 24}小时`
  if (hours > 0) return `${hours}小时${minutes % 60}分`
  if (minutes > 0) return `${minutes}分${seconds % 60}秒`
  return `${seconds}秒`
}

// 获取倒计时样式类
const getCountdownClass = (scheduledTime: string): string => {
  const diff = new Date(scheduledTime).getTime() - currentTime.value
  if (diff <= 0) return 'countdown-started'
  if (diff < 60000) return 'countdown-urgent' // 小于1分钟
  if (diff < 300000) return 'countdown-soon' // 小于5分钟
  return 'countdown-normal'
}

// 启动倒计时
const startCountdown = () => {
  stopCountdown()
  countdownInterval.value = setInterval(() => {
    currentTime.value = Date.now()
  }, 1000) as unknown as number
}

// 停止倒计时
const stopCountdown = () => {
  if (countdownInterval.value) {
    clearInterval(countdownInterval.value)
    countdownInterval.value = null
  }
}

onMounted(async () => {
  await Promise.all([
    loadProjects(),
    loadScheduleOptions(),
    refreshRunningTasks()
  ])
  startCountdown()
})

onUnmounted(() => {
  stopCountdown()
})
</script>

<style scoped>
.batch-scheduler {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
}

.panel-header {
  text-align: center;
  margin-bottom: 30px;
}

.panel-header h2 {
  font-size: 28px;
  margin-bottom: 10px;
}

.subtitle {
  color: #666;
  font-size: 14px;
}

/* 运行中任务面板 */
.running-tasks-panel {
  background: white;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.panel-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.panel-title-row h3 {
  margin: 0;
}

.btn-refresh {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  background: #f0f0f0;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.3s;
}

.btn-refresh:hover:not(:disabled) {
  background: #e0e0e0;
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: #999;
}

.empty-icon {
  font-size: 48px;
  display: block;
  margin-bottom: 10px;
}

.running-tasks-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 15px;
}

.task-card {
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  padding: 15px;
  background: #fafafa;
  transition: all 0.3s;
}

.task-card.running {
  border-color: #28a745;
  background: #f0fff4;
}

.task-card.paused {
  border-color: #ffc107;
  background: #fffbf0;
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.task-status-badge {
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.task-status-badge.running {
  background: #28a745;
  color: white;
}

.task-status-badge.paused {
  background: #ffc107;
  color: #333;
}

.task-status-badge.pending {
  background: #6c757d;
  color: white;
}

.task-project {
  font-weight: 600;
  color: #333;
  font-size: 14px;
}

.task-stats {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.stat {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
}

.stat-label {
  color: #666;
}

.stat-value {
  font-weight: 500;
  color: #333;
}

.stat-value.countdown {
  font-weight: 600;
}

.task-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.btn-small {
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.3s;
}

.btn-small.btn-success {
  background: #28a745;
  color: white;
}

.btn-small.btn-warning {
  background: #ffc107;
  color: #333;
}

.btn-small.btn-danger {
  background: #dc3545;
  color: white;
}

/* 创建表单 */
.create-form, .schedule-result {
  background: white;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.info-banner {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 24px;
}

.info-icon {
  font-size: 24px;
}

.info-content strong {
  display: block;
  font-size: 16px;
  margin-bottom: 4px;
}

.info-content p {
  margin: 0;
  font-size: 14px;
  opacity: 0.95;
}

/* 项目选择器 */
.project-selector {
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  padding: 15px;
  background: #fafafa;
}

.selector-header {
  display: flex;
  gap: 15px;
  align-items: center;
  margin-bottom: 15px;
  padding-bottom: 10px;
  border-bottom: 1px solid #e0e0e0;
}

.btn-link {
  background: none;
  border: none;
  color: #007bff;
  cursor: pointer;
  font-size: 14px;
  text-decoration: underline;
  padding: 0;
}

.btn-link:hover {
  color: #0056b3;
}

.selected-count {
  margin-left: auto;
  color: #666;
  font-size: 14px;
  font-weight: 500;
}

.project-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 10px;
  max-height: 300px;
  overflow-y: auto;
}

.project-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  transition: all 0.2s;
}

.project-item:hover {
  background: #f0f0f0;
}

.project-item.selected {
  border-color: #007bff;
  background: #e7f3ff;
}

.project-item.has-task {
  border-color: #ffc107;
  background: #fff9e6;
}

.project-item.selected.has-task {
  border-color: #ff6b6b;
  background: #ffe6e6;
}

.project-item input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
}

.project-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.project-name {
  font-weight: 500;
  color: #333;
  font-size: 14px;
}

.task-indicator {
  font-size: 11px;
  color: #ff6b6b;
  font-weight: 600;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
}

/* 时间间隔输入组 */
.interval-input-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.interval-input-group .interval-select {
  flex: 1;
  min-width: 0;
}

.interval-input-group .input-separator {
  color: #999;
  font-size: 14px;
  white-space: nowrap;
}

.interval-input-group .custom-interval-input {
  flex: 1.5;
  min-width: 0;
}

.interval-select, .form-group input[type="text"] {
  width: 100%;
  padding: 12px;
  border: 2px solid #cbd5e0;
  border-radius: 6px;
  font-size: 14px;
  background: white;
}

.custom-interval-input {
  padding: 12px;
  border: 2px solid #cbd5e0;
  border-radius: 6px;
  font-size: 14px;
  background: white;
}

.hint {
  display: block;
  margin-top: 5px;
  font-size: 12px;
  color: #999;
}

.btn-primary, .btn-secondary, .btn-edit {
  padding: 12px 24px;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.3s;
}

.btn-large {
  width: 100%;
  font-size: 16px;
  font-weight: 600;
  padding: 16px;
}

.btn-primary {
  background: #007bff;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #0056b3;
}

.btn-secondary {
  background: #6c757d;
  color: white;
}

.btn-edit {
  background: #ffc107;
  color: #333;
  padding: 6px 12px;
  font-size: 12px;
}

button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 调度结果 */
.schedule-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 15px;
  margin-bottom: 30px;
}

.summary-item {
  text-align: center;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 6px;
}

.summary-label {
  display: block;
  font-size: 12px;
  color: #666;
  margin-bottom: 5px;
}

.summary-value {
  display: block;
  font-size: 20px;
  font-weight: bold;
  color: #333;
}

.schedule-table {
  overflow-x: auto;
}

.schedule-table table {
  width: 100%;
  border-collapse: collapse;
}

.schedule-table th,
.schedule-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #e0e0e0;
}

.schedule-table th {
  background: #f8f9fa;
  font-weight: 600;
  color: #333;
}

.project-cell {
  max-width: 200px;
}

.project-name {
  font-weight: 500;
  color: #333;
  margin-bottom: 4px;
}

.project-id {
  font-size: 12px;
  color: #999;
}

.countdown-normal { color: #28a745; }
.countdown-soon { color: #ffc107; font-weight: 600; }
.countdown-urgent { color: #ff6b6b; font-weight: bold; animation: pulse 1s infinite; }
.countdown-started { color: #17a2b8; font-weight: bold; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* 模态框 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 8px;
  padding: 24px;
  max-width: 500px;
  width: 90%;
}

.modal-body {
  margin: 20px 0;
}

.task-title {
  font-weight: 600;
  color: #333;
  margin-bottom: 20px;
}

.modal-footer {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}
</style>
