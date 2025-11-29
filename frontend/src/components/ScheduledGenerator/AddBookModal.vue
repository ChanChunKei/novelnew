<template>
  <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
    <div class="bg-white rounded-lg shadow-xl max-w-xl w-full mx-4 max-h-[90vh] overflow-y-auto">
      <div class="p-6">
        <h2 class="text-2xl font-bold mb-4">添加书籍到队列</h2>

        <form @submit.prevent="handleSubmit" class="space-y-4">
          <!-- 小说选择列表 -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">
              选择要加入队列的书籍
            </label>

            <div class="flex items-center gap-3 mb-3">
              <input
                v-model="search"
                type="text"
                class="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                placeholder="按书名或ID搜索"
              />
              <span class="text-sm text-gray-500">已选 {{ selectedIds.length }} 本</span>
            </div>

            <div class="border rounded-lg divide-y max-h-64 overflow-y-auto">
              <template v-if="!novelsLoading && filteredNovels.length > 0">
                <label
                  v-for="novel in filteredNovels"
                  :key="novel.id"
                  class="flex items-start gap-3 px-3 py-2 hover:bg-gray-50 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    class="mt-1 h-4 w-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
                    :value="novel.id"
                    v-model="selectedIds"
                  />
                  <div class="text-sm">
                    <p class="font-medium text-gray-800">{{ novel.title || '未命名' }}</p>
                    <p class="text-gray-500 font-mono break-all">{{ novel.id }}</p>
                  </div>
                </label>
              </template>
              <div v-else-if="novelsLoading" class="p-4 text-center text-gray-500">加载书籍列表中...</div>
              <div v-else class="p-4 text-center text-gray-500">没有可用的书籍</div>
            </div>
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
              :disabled="loading || selectedIds.length === 0"
              class="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              {{ loading ? '添加中...' : `添加 ${selectedIds.length} 本` }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { scheduledGeneratorApi } from '@/api/scheduled-generator'
import { NovelAPI, type NovelProjectSummary } from '@/api/novel'

const emit = defineEmits<{
  close: []
  added: []
}>()

const loading = ref(false)
const novelsLoading = ref(false)
const search = ref('')
const novels = ref<NovelProjectSummary[]>([])
const selectedIds = ref<string[]>([])
const priority = ref(0)

const filteredNovels = computed(() => {
  if (!search.value.trim()) return novels.value
  const keyword = search.value.trim().toLowerCase()
  return novels.value.filter(
    n =>
      (n.title && n.title.toLowerCase().includes(keyword)) ||
      n.id.toLowerCase().includes(keyword)
  )
})

const loadNovels = async () => {
  novelsLoading.value = true
  try {
    novels.value = await NovelAPI.getAllNovels()
  } catch (error: any) {
    alert(`加载书籍失败: ${error.message}`)
  } finally {
    novelsLoading.value = false
  }
}

const handleSubmit = async () => {
  if (selectedIds.value.length === 0) {
    alert('请选择至少一本书')
    return
  }

  loading.value = true
  try {
    await scheduledGeneratorApi.addToQueue({
      novel_ids: selectedIds.value,
      priority: priority.value
    })
    emit('added')
  } catch (error: any) {
    alert(`添加失败: ${error.message}`)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadNovels()
})
</script>
