<template>
  <div class="rag-config">
    <div class="bg-white rounded-lg shadow-sm border border-slate-200 p-6">
      <h2 class="text-xl font-semibold text-slate-800 mb-6 flex items-center gap-2">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        RAG 检索配置
      </h2>

      <div class="space-y-6 max-w-2xl">
        <!-- RAG Provider Selection -->
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-2">检索提供方 (RAG Provider)</label>
          <div class="grid grid-cols-2 gap-4">
            <div
              @click="form.provider = 'libsql'"
              :class="[
                'cursor-pointer rounded-lg border p-4 flex items-center gap-3 transition-all',
                form.provider === 'libsql'
                  ? 'border-indigo-500 bg-indigo-50 ring-1 ring-indigo-500'
                  : 'border-slate-200 hover:border-slate-300'
              ]"
            >
              <div class="flex-shrink-0">
                <div class="w-5 h-5 rounded-full border flex items-center justify-center"
                  :class="form.provider === 'libsql' ? 'border-indigo-600' : 'border-slate-400'"
                >
                  <div v-if="form.provider === 'libsql'" class="w-2.5 h-2.5 rounded-full bg-indigo-600"></div>
                </div>
              </div>
              <div>
                <div class="font-medium text-slate-900">LibSQL (本地)</div>
                <div class="text-xs text-slate-500">使用本地向量数据库，无需外部 API</div>
              </div>
            </div>

            <div
              @click="form.provider = 'gemini'"
              :class="[
                'cursor-pointer rounded-lg border p-4 flex items-center gap-3 transition-all',
                form.provider === 'gemini'
                  ? 'border-indigo-500 bg-indigo-50 ring-1 ring-indigo-500'
                  : 'border-slate-200 hover:border-slate-300'
              ]"
            >
              <div class="flex-shrink-0">
                <div class="w-5 h-5 rounded-full border flex items-center justify-center"
                  :class="form.provider === 'gemini' ? 'border-indigo-600' : 'border-slate-400'"
                >
                  <div v-if="form.provider === 'gemini'" class="w-2.5 h-2.5 rounded-full bg-indigo-600"></div>
                </div>
              </div>
              <div>
                <div class="font-medium text-slate-900">Google Gemini</div>
                <div class="text-xs text-slate-500">使用 Google 语义检索，需配置 API Key</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Gemini API Key Input -->
        <div v-if="form.provider === 'gemini'" class="transition-all duration-300">
          <label class="block text-sm font-medium text-slate-700 mb-2">
            Gemini API Key
            <span class="text-red-500">*</span>
          </label>
          <div class="relative">
            <input
              v-model="form.apiKey"
              :type="showKey ? 'text' : 'password'"
              class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all"
              placeholder="AIzaSy..."
            />
            <button
              @click="showKey = !showKey"
              class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
            >
              <svg v-if="showKey" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
              </svg>
              <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
            </button>
          </div>
          <p class="mt-1 text-xs text-slate-500">
            请在 <a href="https://aistudio.google.com/app/apikey" target="_blank" class="text-indigo-600 hover:underline">Google AI Studio</a> 获取 API Key
          </p>
        </div>

        <!-- Actions -->
        <div class="flex items-center gap-4 pt-4 border-t border-slate-100">
          <button
            @click="saveConfig"
            :disabled="saving"
            class="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-colors"
          >
            <svg v-if="saving" class="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {{ saving ? '保存中...' : '保存配置' }}
          </button>

          <button
            v-if="form.provider === 'gemini'"
            @click="testConnection"
            :disabled="testing || !form.apiKey"
            class="px-6 py-2 border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-colors"
          >
            <svg v-if="testing" class="animate-spin h-4 w-4 text-slate-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {{ testing ? '测试连接中...' : '测试连接' }}
          </button>
        </div>

        <!-- Test Result -->
        <div v-if="testResult" :class="[
          'mt-4 p-4 rounded-lg border text-sm',
          testResult.success ? 'bg-green-50 border-green-200 text-green-800' : 'bg-red-50 border-red-200 text-red-800'
        ]">
          <div class="flex items-start gap-2">
            <svg v-if="testResult.success" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-green-600 mt-0.5" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
            </svg>
            <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-red-600 mt-0.5" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
            </svg>
            <div class="flex-1">
              <p class="font-medium">{{ testResult.message }}</p>
              <p v-if="testResult.error_detail" class="mt-1 text-xs opacity-90 font-mono bg-white/50 p-1 rounded">
                {{ testResult.error_detail }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ragConfigApi, type GeminiRAGTestResult } from '@/api/rag-config'
import { globalAlert } from '@/composables/useAlert'

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const showKey = ref(false)
const testResult = ref<GeminiRAGTestResult | null>(null)

const form = ref({
  provider: 'libsql',
  apiKey: ''
})

// 加载配置
const loadConfig = async () => {
  loading.value = true
  try {
    const [providerRes, apiKeyRes] = await Promise.all([
      ragConfigApi.getSystemConfig('rag.provider').catch(() => null),
      ragConfigApi.getSystemConfig('gemini.api_key').catch(() => null)
    ])

    if (providerRes?.data) {
      form.value.provider = providerRes.data.value
    }
    if (apiKeyRes?.data) {
      form.value.apiKey = apiKeyRes.data.value
    }
  } catch (error) {
    console.error('Failed to load RAG config:', error)
  } finally {
    loading.value = false
  }
}

// 保存配置
const saveConfig = async () => {
  saving.value = true
  testResult.value = null
  try {
    await Promise.all([
      ragConfigApi.upsertSystemConfig('rag.provider', form.value.provider, 'RAG 检索提供方'),
      ragConfigApi.upsertSystemConfig('gemini.api_key', form.value.apiKey, 'Google Gemini API Key')
    ])
    
    globalAlert.showSuccess('RAG 配置已更新', '保存成功')
  } catch (error: any) {
    globalAlert.showError(error.message || '未知错误', '保存失败')
  } finally {
    saving.value = false
  }
}

// 测试连接
const testConnection = async () => {
  testing.value = true
  testResult.value = null
  
  // 先保存当前输入的 Key，确保后端测试时用的是最新的
  try {
    await ragConfigApi.upsertSystemConfig('gemini.api_key', form.value.apiKey, 'Google Gemini API Key')
  } catch (error) {
    // 忽略保存错误，继续尝试测试（可能后端已有 Key）
  }

  try {
    const res = await ragConfigApi.testGeminiRag()
    testResult.value = res.data
  } catch (error: any) {
    testResult.value = {
      success: false,
      message: '测试请求失败',
      api_key_configured: !!form.value.apiKey,
      api_key_valid: false,
      provider: form.value.provider,
      error_detail: error.message
    }
  } finally {
    testing.value = false
  }
}

onMounted(() => {
  loadConfig()
})
</script>
