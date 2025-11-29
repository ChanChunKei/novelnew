<template>
  <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
    <div class="bg-white rounded-lg shadow-xl max-w-xl w-full mx-4 max-h-[90vh] overflow-y-auto">
      <div class="p-6">
        <h2 class="text-2xl font-bold mb-4">添加书籍到队列</h2>

        <form @submit.prevent="handleSubmit" class="space-y-4">
          <!-- 小说ID列表 -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              小说项目ID（每行一个）
            </label>
            <textarea
              v-model="novelIdsText"
              rows="8"
              required
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 font-mono text-sm"
              placeholder="粘贴小说项目ID，每行一个&#10;例如：&#10;abc-123-def&#10;xyz-456-ghi"
            ></textarea>
            <p class="text-sm text-gray-500 mt-1">
              提示：可以从小说列表页面复制项目ID
            </p>
          </div>

          <!-- 优先级 -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              优先级（数字越大越优先）
            </label>
            <input
              v-model.number="priority"
              type="number"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              placeholder="默认为 0"
            />
          </div>

          <!-- 预览 -->
          <div v-if="novelIds.length > 0" class="bg-gray-50 rounded-lg p-4">
            <p class="text-sm font-medium text-gray-700 mb-2">
              将添加 {{ novelIds.length }} 本书：
            </p>
            <ul class="text-sm text-gray-600 space-y-1 max-h-40 overflow-y-auto">
              <li v-for="id in novelIds" :key="id" class="font-mono">{{ id }}</li>
            </ul>
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
              :disabled="loading || novelIds.length === 0"
              class="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              {{ loading ? '添加中...' : `添加 ${novelIds.length} 本` }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { scheduledGeneratorApi } from '@/api/scheduled-generator'

const emit = defineEmits<{
  close: []
  added: []
}>()

const loading = ref(false)
const novelIdsText = ref('')
const priority = ref(0)

const novelIds = computed(() => {
  return novelIdsText.value
    .split('\n')
    .map(line => line.trim())
    .filter(line => line.length > 0)
})

const handleSubmit = async () => {
  if (novelIds.value.length === 0) {
    alert('请输入至少一个小说项目ID')
    return
  }

  loading.value = true
  try {
    await scheduledGeneratorApi.addToQueue({
      novel_ids: novelIds.value,
      priority: priority.value
    })
    emit('added')
  } catch (error: any) {
    alert(`添加失败: ${error.message}`)
  } finally {
    loading.value = false
  }
}
</script>
