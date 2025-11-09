<template>
  <div class="w-full">
    <!-- 上传按钮 -->
    <div class="flex flex-col gap-6">
      <div class="border-b border-slate-200 pb-4">
        <h3 class="text-2xl font-bold text-slate-900">📚 番茄小说上传</h3>
        <p class="text-sm text-slate-600 mt-1">一键上传小说到番茄小说平台</p>
      </div>

      <!-- 状态显示 -->
      <div v-if="uploadStatus" class="flex items-start gap-4 p-4 rounded-lg border" :class="statusClass">
        <div class="flex-shrink-0">
          <svg v-if="uploadStatus.type === 'success'" class="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
          </svg>
          <svg v-else-if="uploadStatus.type === 'error'" class="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
          <svg v-else-if="uploadStatus.type === 'info'" class="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <svg v-else class="w-6 h-6 text-blue-600 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
        </div>
        <div class="flex-1">
          <p class="font-medium text-slate-900">{{ uploadStatus.message }}</p>
          <p v-if="uploadStatus.hint" class="text-sm text-slate-600 mt-1">{{ uploadStatus.hint }}</p>
        </div>
      </div>

      <!-- Cookie状态 -->
      <div class="p-4 bg-slate-50 rounded-lg border border-slate-200">
        <div class="flex flex-col gap-3">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <div class="w-2 h-2 rounded-full" :class="hasCookie ? 'bg-green-500' : 'bg-gray-300'"></div>
              <span class="text-sm text-slate-600">
                Cookie状态: {{ hasCookie ? '已保存' : '未登录' }}
              </span>
            </div>
            <div class="flex gap-2">
              <!-- 已有Cookie时显示重新设置按钮 -->
              <button
                v-if="hasCookie"
                @click="handleResetCookie"
                class="px-4 py-2 text-sm font-medium text-amber-600 bg-white border border-amber-200 rounded-lg hover:bg-amber-50 transition-all duration-200"
              >
                🔄 重新设置Cookie
              </button>
              <!-- 未登录时显示登录按钮 -->
              <button
                v-if="!hasCookie"
                @click="showManualInput = !showManualInput"
                class="px-4 py-2 text-sm font-medium text-green-600 bg-white border border-green-200 rounded-lg hover:bg-green-50 transition-all duration-200"
              >
                {{ showManualInput ? '取消手动输入' : '手动输入Cookie' }}
              </button>
              <button
                v-if="!hasCookie"
                @click="handleLogin"
                :disabled="isLoggingIn"
                class="px-4 py-2 text-sm font-medium text-indigo-600 bg-white border border-indigo-200 rounded-lg hover:bg-indigo-50 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {{ isLoggingIn ? '打开浏览器中...' : '浏览器登录' }}
              </button>
            </div>
          </div>

          <!-- 手动输入Cookie区域 -->
          <div v-if="showManualInput && !hasCookie" class="flex flex-col gap-3 p-3 bg-white rounded-lg border border-slate-300">
            <div class="flex flex-col gap-2">
              <label class="text-sm font-medium text-slate-700">粘贴Cookie字符串</label>
              <textarea
                v-model="manualCookie"
                rows="4"
                class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent text-sm font-mono"
                placeholder="从浏览器开发者工具中复制完整的Cookie字符串，例如：&#10;sessionid=xxx; uid=xxx; passport_csrf_token=xxx; ..."
              ></textarea>
              <p class="text-xs text-slate-500">
                💡 获取方法：打开番茄小说作家后台 → F12开发者工具 → Network → 刷新页面 → 点击任意请求 → 复制Cookie
              </p>
            </div>
            <button
              @click="handleManualSaveCookie"
              :disabled="!manualCookie.trim() || isSavingCookie"
              class="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {{ isSavingCookie ? '保存中...' : '✓ 保存Cookie' }}
            </button>
          </div>

          <!-- 保存Cookie按钮 - 仅在浏览器登录中显示 -->
          <div v-if="!hasCookie && isLoggingIn && !showManualInput" class="flex items-center gap-2">
            <button
              @click="handleSaveCookie"
              :disabled="isSavingCookie"
              class="flex-1 px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {{ isSavingCookie ? '保存中...' : '✓ 保存Cookie' }}
            </button>
            <span class="text-xs text-slate-500">完成登录后点击此按钮</span>
          </div>
        </div>
      </div>

      <!-- 上传设置 -->
      <div class="flex flex-col gap-4">
        <div class="flex flex-col gap-2">
          <label class="text-sm font-medium text-slate-700">账号标识</label>
          <input
            v-model="account"
            type="text"
            class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            placeholder="default"
          />
          <p class="text-xs text-slate-500">用于区分不同番茄小说账号的Cookie</p>
        </div>

        <div class="flex flex-col gap-2">
          <label class="text-sm font-medium text-slate-700">上传间隔（秒）</label>
          <input
            v-model.number="uploadInterval"
            type="number"
            min="10"
            max="300"
            class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            placeholder="20"
          />
          <p class="text-xs text-slate-500">每章上传间隔时间，建议20-60秒，避免被检测为机器人</p>
        </div>

        <div class="flex flex-col gap-2">
          <label class="flex items-center gap-2 cursor-pointer">
            <input
              v-model="headless"
              type="checkbox"
              class="w-4 h-4 text-indigo-600 border-slate-300 rounded focus:ring-indigo-500"
            />
            <span class="text-sm font-medium text-slate-700">无头模式</span>
          </label>
          <p class="text-xs text-slate-500">生产环境建议开启，调试时可关闭</p>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="flex gap-3">
        <button
          v-if="!isUploading"
          @click="handleUpload"
          :disabled="!hasCookie"
          class="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-gradient-to-r from-indigo-600 to-indigo-700 text-white font-medium rounded-lg hover:from-indigo-700 hover:to-indigo-800 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow-md hover:shadow-lg"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          <span>▶️ 开始上传</span>
        </button>

        <button
          v-if="isUploading"
          @click="handleStopUpload"
          class="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-gradient-to-r from-red-600 to-red-700 text-white font-medium rounded-lg hover:from-red-700 hover:to-red-800 transition-all duration-200 shadow-md hover:shadow-lg"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
          <span>⏹️ 停止上传</span>
        </button>
      </div>

      <!-- 使用说明 -->
      <div class="p-4 bg-amber-50 border border-amber-200 rounded-lg">
        <h4 class="text-sm font-semibold text-amber-900 mb-2">📖 使用说明</h4>
        <ol class="text-sm text-amber-800 list-decimal list-inside space-y-1">
          <li>在番茄小说平台手动创建一本新书，书名与本地小说名称一致</li>
          <li>点击"立即登录"按钮，在弹出的浏览器中完成登录</li>
          <li>登录成功后，Cookie会自动保存</li>
          <li>点击"一键上传"按钮，系统会自动同步分卷和章节</li>
          <li>上传过程中如遇错误会立即停止，请根据提示处理</li>
        </ol>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { novelApi } from '@/api/novel'

const props = defineProps<{
  projectId: string
}>()

// 状态
const account = ref('default')
const headless = ref(true)
const uploadInterval = ref(20)
const isUploading = ref(false)
const isLoggingIn = ref(false)
const hasCookie = ref(false)
const showManualInput = ref(false)
const manualCookie = ref('')
const uploadStatus = ref<{
  type: 'success' | 'error' | 'loading' | 'info'
  message: string
  hint?: string
} | null>(null)

// 上传控制
let uploadAbortController: AbortController | null = null

// 计算属性
const statusClass = computed(() => {
  if (!uploadStatus.value) return ''
  return {
    'status-success': uploadStatus.value.type === 'success',
    'status-error': uploadStatus.value.type === 'error',
    'status-loading': uploadStatus.value.type === 'loading',
    'status-info': uploadStatus.value.type === 'info'
  }
})

// 检查Cookie状态
const checkCookieStatus = () => {
  // 这里可以添加检查Cookie文件是否存在的逻辑
  // 暂时假设如果登录过就有Cookie
  hasCookie.value = localStorage.getItem(`fanqie_cookie_${account.value}`) === 'true'
}

// 处理登录
const handleLogin = async () => {
  isLoggingIn.value = true
  uploadStatus.value = {
    type: 'loading',
    message: '正在打开浏览器，请在浏览器中完成登录...'
  }

  try {
    const result = await novelApi.fanqieLogin(account.value)

    if (result.success) {
      uploadStatus.value = {
        type: 'info',
        message: '浏览器窗口已打开',
        hint: '请在浏览器中完成登录，然后点击下方的"保存Cookie"按钮'
      }
    } else {
      uploadStatus.value = {
        type: 'error',
        message: result.error || '打开浏览器失败'
      }
    }
  } catch (error: any) {
    uploadStatus.value = {
      type: 'error',
      message: '打开浏览器失败: ' + error.message
    }
  } finally {
    isLoggingIn.value = false
  }
}

// 处理保存Cookie（从浏览器）
const isSavingCookie = ref(false)
const handleSaveCookie = async () => {
  isSavingCookie.value = true
  uploadStatus.value = {
    type: 'loading',
    message: '正在保存Cookie...'
  }

  try {
    const result = await novelApi.fanqieSaveCookies(account.value)

    if (result.success) {
      hasCookie.value = true
      localStorage.setItem(`fanqie_cookie_${account.value}`, 'true')
      uploadStatus.value = {
        type: 'success',
        message: 'Cookie保存成功！现在可以上传小说了'
      }
      isLoggingIn.value = false
    } else {
      uploadStatus.value = {
        type: 'error',
        message: result.error || 'Cookie保存失败',
        hint: '请确保已在浏览器中完成登录操作'
      }
    }
  } catch (error: any) {
    uploadStatus.value = {
      type: 'error',
      message: 'Cookie保存失败: ' + error.message
    }
  } finally {
    isSavingCookie.value = false
  }
}

// 处理手动保存Cookie
const handleManualSaveCookie = async () => {
  if (!manualCookie.value.trim()) {
    uploadStatus.value = {
      type: 'error',
      message: '请输入Cookie字符串'
    }
    return
  }

  isSavingCookie.value = true
  uploadStatus.value = {
    type: 'loading',
    message: '正在保存Cookie...'
  }

  try {
    const result = await novelApi.fanqieManualSaveCookies(account.value, manualCookie.value.trim())

    if (result.success) {
      hasCookie.value = true
      localStorage.setItem(`fanqie_cookie_${account.value}`, 'true')
      uploadStatus.value = {
        type: 'success',
        message: 'Cookie保存成功！现在可以上传小说了'
      }
      showManualInput.value = false
      manualCookie.value = ''
    } else {
      uploadStatus.value = {
        type: 'error',
        message: result.error || 'Cookie保存失败',
        hint: '请确保Cookie字符串格式正确'
      }
    }
  } catch (error: any) {
    uploadStatus.value = {
      type: 'error',
      message: 'Cookie保存失败: ' + error.message
    }
  } finally {
    isSavingCookie.value = false
  }
}

// 处理重置Cookie
const handleResetCookie = () => {
  if (confirm('确定要重新设置Cookie吗？这将清除当前保存的Cookie，需要重新登录。')) {
    hasCookie.value = false
    localStorage.removeItem(`fanqie_cookie_${account.value}`)
    showManualInput.value = false
    manualCookie.value = ''
    uploadStatus.value = {
      type: 'info',
      message: 'Cookie已清除，请重新登录',
      hint: '可以选择浏览器登录或手动输入Cookie'
    }
  }
}

// 停止上传
const handleStopUpload = () => {
  if (uploadAbortController) {
    uploadAbortController.abort()
    uploadAbortController = null
    isUploading.value = false
    uploadStatus.value = {
      type: 'info',
      message: '上传已取消',
      hint: '上传请求已中止，但后台可能仍在处理中'
    }
  }
}

// 处理上传
const handleUpload = async () => {
  if (!hasCookie.value) {
    uploadStatus.value = {
      type: 'error',
      message: '请先登录番茄小说',
      hint: '点击"立即登录"按钮完成登录'
    }
    return
  }

  // 创建新的 AbortController
  uploadAbortController = new AbortController()

  isUploading.value = true
  uploadStatus.value = {
    type: 'loading',
    message: '正在上传小说到番茄小说平台...'
  }

  try {
    const result = await novelApi.uploadToFanqie(
      props.projectId,
      account.value,
      headless.value,
      uploadInterval.value,
      uploadAbortController.signal
    )

    if (result.success) {
      uploadStatus.value = {
        type: 'success',
        message: `上传成功！共上传 ${result.chapter_count} 章节到 ${result.volume_count} 个分卷`,
        hint: `书籍ID: ${result.book_id}`
      }
    } else {
      uploadStatus.value = {
        type: 'error',
        message: result.error || '上传失败',
        hint: result.hint
      }
      
      // 如果是Cookie失效，更新状态
      if (result.error?.includes('Cookie')) {
        hasCookie.value = false
        localStorage.removeItem(`fanqie_cookie_${account.value}`)
      }
    }
  } catch (error: any) {
    // 检查是否是用户主动取消
    if (error.name === 'AbortError' || error.message?.includes('abort')) {
      // 用户已通过handleStopUpload取消，状态已更新
      return
    }

    uploadStatus.value = {
      type: 'error',
      message: '上传失败: ' + error.message
    }
  } finally {
    isUploading.value = false
    uploadAbortController = null
  }
}

// 初始化
checkCookieStatus()
</script>

<style scoped>
.status-success {
  background-color: #f0fdf4;
  border-color: #bbf7d0;
}

.status-error {
  background-color: #fef2f2;
  border-color: #fecaca;
}

.status-loading {
  background-color: #eff6ff;
  border-color: #bfdbfe;
}

.status-info {
  background-color: #eff6ff;
  border-color: #bfdbfe;
}
</style>

