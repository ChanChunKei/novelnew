<template>
  <div class="fade-in">
    <!-- 加载状态 -->
    <div v-if="loading || !uiControl" class="flex justify-center items-center p-4" role="status" aria-label="正在加载输入选项">
      <div class="loader" aria-hidden="true"></div>
      <span class="sr-only">正在加载...</span>
    </div>

    <!-- 单选题 -->
    <div v-else-if="uiControl.type === 'single_choice'" role="group" aria-label="对话选项">
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3" role="group" aria-label="快速选项">
        <button
          v-for="option in uiControl.options"
          :key="option.id"
          @click="handleOptionSelect(option.id, option.label)"
          :aria-label="`选择选项: ${option.label}`"
          class="p-3 bg-indigo-100 text-indigo-700 rounded-lg hover:bg-indigo-200 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-indigo-400"
        >
          {{ option.label }}
        </button>
        <button
          @click="isManualInput = true"
          aria-label="切换到手动输入模式"
          class="p-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-gray-400"
        >
          我要输入
        </button>
      </div>
      <form @submit.prevent="handleTextSubmit" class="flex items-center gap-3">
        <div class="w-full relative">
          <textarea
            v-model="textInput"
            :placeholder="isManualInput ? '请输入您的想法...' : '选择上方选项或点击"我要输入"'"
            class="w-full px-4 py-3 border border-gray-300 rounded-2xl focus:ring-2 focus:ring-indigo-400 focus:border-indigo-400 outline-none transition-all disabled:bg-gray-100 resize-none overflow-y-auto leading-relaxed"
            :disabled="!isManualInput"
            :aria-label="isManualInput ? '输入您的想法' : '请先点击快速选项或"我要输入"按钮'"
            rows="5"
            ref="textInputRef"
            @input="handleTextareaInput"
            @keydown="handleKeyDown"
          ></textarea>
          <div v-if="isManualInput" class="absolute right-2 bottom-2 text-xs text-gray-400 pointer-events-none">
            Ctrl+Enter 发送
          </div>
        </div>
        <button
          type="submit"
          :disabled="!isManualInput"
          aria-label="发送消息"
          :title="isManualInput ? '发送消息 (Ctrl+Enter)' : '请先启用输入'"
          class="flex-shrink-0 w-12 h-12 bg-indigo-500 rounded-full flex items-center justify-center hover:bg-indigo-600 transition-all shadow-md disabled:bg-gray-300 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-indigo-400"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="text-white"
            aria-hidden="true"
          >
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
        </button>
      </form>
    </div>

    <!-- 文本输入 -->
    <form v-else-if="uiControl.type === 'text_input'" @submit.prevent="handleTextSubmit" class="flex items-center gap-3">
      <div class="w-full relative">
        <textarea
          v-model="textInput"
          :placeholder="uiControl.placeholder || '请输入...'"
          class="w-full px-4 py-3 pb-8 border border-gray-300 rounded-2xl focus:ring-2 focus:ring-indigo-400 focus:border-indigo-400 outline-none transition-all resize-none overflow-y-auto leading-relaxed"
          aria-label="输入消息内容"
          required
          ref="textInputRef"
          rows="5"
          @input="handleTextareaInput"
          @keydown="handleKeyDown"
        ></textarea>
        <div class="absolute right-2 bottom-2 text-xs text-gray-400 pointer-events-none">
          Ctrl+Enter 发送
        </div>
      </div>
      <button
        type="submit"
        aria-label="发送消息"
        title="发送消息 (Ctrl+Enter)"
        class="flex-shrink-0 w-12 h-12 bg-indigo-500 rounded-full flex items-center justify-center hover:bg-indigo-600 transition-all shadow-md focus:outline-none focus:ring-2 focus:ring-indigo-400"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          class="text-white"
          aria-hidden="true"
        >
          <line x1="22" y1="2" x2="11" y2="13"></line>
          <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
        </svg>
      </button>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import type { UIControl } from '@/api/novel'

interface Props {
  uiControl: UIControl | null
  loading: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  submit: [userInput: { id: string; value: string } | null]
}>()

const textInput = ref('')
const textInputRef = ref<HTMLTextAreaElement>()
const isManualInput = ref(false)

const MIN_ROWS = 5
const MAX_ROWS = 5

const adjustTextareaHeight = () => {
  const textarea = textInputRef.value
  if (!textarea) {
    return
  }
  if (typeof window === 'undefined') {
    return
  }

  const lineHeight = parseFloat(window.getComputedStyle(textarea).lineHeight || '0') || 20
  const minHeight = lineHeight * MIN_ROWS
  const maxHeight = lineHeight * MAX_ROWS

  textarea.style.height = 'auto'
  const targetHeight = Math.min(maxHeight, Math.max(minHeight, textarea.scrollHeight))
  textarea.style.height = `${targetHeight}px`
}

const handleTextareaInput = () => {
  adjustTextareaHeight()
}

const handleOptionSelect = (id: string, label: string) => {
  emit('submit', { id, value: label })
}

const handleTextSubmit = () => {
  if (textInput.value.trim()) {
    emit('submit', { id: 'text_input', value: textInput.value.trim() })
    textInput.value = ''
    nextTick(() => adjustTextareaHeight())
  }
}

// 处理键盘快捷键：Ctrl+Enter 或 Cmd+Enter 发送
const handleKeyDown = (event: KeyboardEvent) => {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
    event.preventDefault()
    handleTextSubmit()
  }
}

// 当输入控件变为文本输入时，自动聚焦
watch(
  () => props.uiControl,
  async (newControl) => {
    // 每次控件更新时，都重置手动输入状态和文本内容
    isManualInput.value = false
    textInput.value = ''

    await nextTick()
    adjustTextareaHeight()

    if (newControl?.type === 'text_input') {
      textInputRef.value?.focus()
    }
  },
  { deep: true } // 使用 deep watch 确保即使是相同类型的控件也能触发
)

// 监听手动输入状态的变化，以聚焦输入框
watch(isManualInput, async (newValue) => {
  if (newValue) {
    await nextTick()
    adjustTextareaHeight()
    textInputRef.value?.focus()
  }
})

</script>
