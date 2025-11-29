<template>
  <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
    <div class="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
      <div class="p-6">
        <h2 class="text-2xl font-bold mb-4">{{ config ? '编辑配置' : '创建配置' }}</h2>

        <form @submit.prevent="handleSubmit" class="space-y-4">
          <!-- 配置名称 -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">配置名称</label>
            <input
              v-model="form.name"
              type="text"
              required
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              placeholder="例如：每日定时生成"
            />
          </div>

          <!-- 触发时间 -->
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">小时（太平洋时间）</label>
              <input
                v-model.number="form.trigger_hour"
                type="number"
                min="0"
                max="23"
                required
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">分钟</label>
              <input
                v-model.number="form.trigger_minute"
                type="number"
                min="0"
                max="59"
                required
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>

          <!-- 生成模式 -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">生成模式</label>
            <select
              v-model="form.generation_mode"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            >
              <option value="basic">基础模式（快速）</option>
              <option value="enhanced">增强模式（深度分析）</option>
            </select>
          </div>

          <!-- 并发数量 -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              并发生成数量（1-5本）
            </label>
            <input
              v-model.number="form.concurrent_books"
              type="number"
              min="1"
              max="5"
              required
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <!-- 单本时长 -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              单本最大时长（分钟）
            </label>
            <input
              v-model.number="form.max_duration_per_book"
              type="number"
              min="10"
              max="600"
              required
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <!-- 番茄上传 -->
          <div>
            <label class="flex items-center">
              <input
                v-model="form.auto_upload_fanqie"
                type="checkbox"
                class="mr-2 h-4 w-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
              />
              <span class="text-sm font-medium text-gray-700">自动上传番茄小说</span>
            </label>
          </div>

          <!-- 上传间隔 -->
          <div v-if="form.auto_upload_fanqie">
            <label class="block text-sm font-medium text-gray-700 mb-1">
              上传间隔（秒，5-60）
            </label>
            <input
              v-model.number="form.upload_interval_seconds"
              type="number"
              min="5"
              max="60"
              required
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <!-- 按钮 -->
          <div class="flex gap-3 pt-4">
            <button
              type="button"
              @click="$emit('close')"
              class="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              取消
            </button>
            <button
              type="submit"
              :disabled="loading"
              class="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              {{ loading ? '保存中...' : '保存' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { scheduledGeneratorApi, type ScheduledGeneratorConfig } from '@/api/scheduled-generator'

interface Props {
  config?: ScheduledGeneratorConfig | null
}

const props = defineProps<Props>()
const emit = defineEmits<{
  close: []
  saved: []
}>()

const loading = ref(false)
const form = ref({
  name: '默认定时任务',
  trigger_hour: 2,
  trigger_minute: 0,
  generation_mode: 'basic' as 'basic' | 'enhanced',
  auto_upload_fanqie: false,
  upload_interval_seconds: 20,
  concurrent_books: 1,
  max_duration_per_book: 120
})

onMounted(() => {
  if (props.config) {
    form.value = {
      name: props.config.name,
      trigger_hour: props.config.trigger_hour,
      trigger_minute: props.config.trigger_minute,
      generation_mode: props.config.generation_mode,
      auto_upload_fanqie: props.config.auto_upload_fanqie,
      upload_interval_seconds: props.config.upload_interval_seconds,
      concurrent_books: props.config.concurrent_books,
      max_duration_per_book: props.config.max_duration_per_book
    }
  }
})

const handleSubmit = async () => {
  loading.value = true
  try {
    if (props.config) {
      await scheduledGeneratorApi.updateConfig(props.config.id, form.value)
    } else {
      await scheduledGeneratorApi.createConfig(form.value)
    }
    emit('saved')
  } catch (error: any) {
    alert(`保存失败: ${error.message}`)
  } finally {
    loading.value = false
  }
}
</script>
