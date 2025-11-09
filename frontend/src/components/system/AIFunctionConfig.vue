<template>
  <div class="ai-function-config">
    <div class="header">
      <h2 class="title">AI 功能配置</h2>
      <p class="description">配置各个 AI 功能的模型选择、参数和行为</p>
    </div>

    <!-- Function List -->
    <div class="function-list">
      <div v-for="func in functions" :key="func.name" class="function-card">
        <div class="function-header">
          <div>
            <h3 class="function-name">{{ func.display_name }}</h3>
            <p class="function-desc">{{ func.description }}</p>
          </div>
          <button @click="editFunction(func)" class="btn-edit">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
            配置
          </button>
        </div>

        <div class="function-details">
          <div class="detail-grid">
            <div class="detail-item">
              <span class="detail-label">模型:</span>
              <span class="detail-value">{{ func.model || '默认' }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">温度:</span>
              <span class="detail-value">{{ func.temperature }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">超时:</span>
              <span class="detail-value">{{ func.timeout }}s</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">重试:</span>
              <span class="detail-value">{{ func.max_retries }}次</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">异步模式:</span>
              <span :class="['badge', func.async_mode ? 'badge-success' : 'badge-gray']">
                {{ func.async_mode ? '是' : '否' }}
              </span>
            </div>
            <div class="detail-item">
              <span class="detail-label">必需:</span>
              <span :class="['badge', func.required ? 'badge-warning' : 'badge-gray']">
                {{ func.required ? '是' : '否' }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Edit Modal -->
    <div v-if="editingFunction" class="modal-overlay" @click.self="closeModal">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="modal-title">配置 {{ editingFunction.display_name }}</h3>
          <button @click="closeModal" class="modal-close">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">模型选择</label>
            <select v-model="formData.model" class="form-input">
              <option value="">使用默认模型</option>
              <option value="gpt-4">GPT-4</option>
              <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
              <option value="claude-3-opus">Claude 3 Opus</option>
              <option value="claude-3-sonnet">Claude 3 Sonnet</option>
            </select>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">温度 (0-2)</label>
              <input v-model.number="formData.temperature" type="number" class="form-input" min="0" max="2" step="0.1" />
              <p class="form-hint">较高的值会使输出更随机，较低的值会使其更集中和确定</p>
            </div>

            <div class="form-group">
              <label class="form-label">最大 Token</label>
              <input v-model.number="formData.max_tokens" type="number" class="form-input" min="1" />
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">超时时间(秒)</label>
              <input v-model.number="formData.timeout" type="number" class="form-input" min="1" />
            </div>

            <div class="form-group">
              <label class="form-label">最大重试次数</label>
              <input v-model.number="formData.max_retries" type="number" class="form-input" min="0" max="10" />
            </div>
          </div>

          <div class="form-group">
            <label class="flex items-center gap-2">
              <input v-model="formData.async_mode" type="checkbox" class="form-checkbox" />
              <span class="form-label mb-0">异步模式</span>
            </label>
            <p class="form-hint">启用后，调用将在后台执行，不阻塞主流程</p>
          </div>

          <div class="form-group">
            <label class="flex items-center gap-2">
              <input v-model="formData.required" type="checkbox" class="form-checkbox" />
              <span class="form-label mb-0">必需功能</span>
            </label>
            <p class="form-hint">如果此功能失败，整个流程将终止</p>
          </div>

          <div class="form-group">
            <label class="flex items-center gap-2">
              <input v-model="formData.enable_fallback" type="checkbox" class="form-checkbox" />
              <span class="form-label mb-0">启用降级</span>
            </label>
            <p class="form-hint">主模型失败时自动切换到备用模型</p>
          </div>
        </div>

        <div class="modal-footer">
          <button @click="closeModal" class="btn-secondary">取消</button>
          <button @click="saveFunction" class="btn-primary">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { aiConfigApi } from '@/api/novel'

const functions = ref<any[]>([])
const editingFunction = ref<any>(null)
const formData = ref({
  model: '',
  temperature: 0.7,
  max_tokens: 2000,
  timeout: 30,
  max_retries: 3,
  async_mode: false,
  required: false,
  enable_fallback: true
})

const loadFunctions = async () => {
  try {
    functions.value = await aiConfigApi.getFunctionConfigs()
  } catch (error: any) {
    console.error('加载功能配置失败:', error)
  }
}

const editFunction = (func: any) => {
  editingFunction.value = func
  formData.value = { ...func }
}

const saveFunction = async () => {
  if (!editingFunction.value) return
  
  try {
    await aiConfigApi.updateFunctionConfig(editingFunction.value.name, formData.value)
    await loadFunctions()
    closeModal()
  } catch (error: any) {
    console.error('保存功能配置失败:', error)
  }
}

const closeModal = () => {
  editingFunction.value = null
  formData.value = {
    model: '',
    temperature: 0.7,
    max_tokens: 2000,
    timeout: 30,
    max_retries: 3,
    async_mode: false,
    required: false,
    enable_fallback: true
  }
}

onMounted(() => {
  loadFunctions()
})
</script>


