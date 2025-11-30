<template>
  <div class="page">
    <h2 class="title">蓝图快捷生成</h2>
    <p class="desc">无需对话，直接按模式生成蓝图。支持创意/参考/讨论式（agent）模式。</p>

    <form class="form" @submit.prevent="run">
      <label>
        模式
        <select v-model="mode">
          <option value="creative">创意扩展</option>
          <option value="reference">参考学习</option>
          <option value="agent">讨论式（Brainstormer+Synthesizer）</option>
        </select>
      </label>

      <div class="grid">
        <label>
          核心创意
          <input v-model="creative.idea" type="text" placeholder="废材少年觉醒古老传承..." required />
        </label>
        <label>
          题材
          <input v-model="creative.genre" type="text" placeholder="玄幻/科幻/都市..." />
        </label>
        <label>
          风格
          <input v-model="creative.style" type="text" placeholder="爽文/黑暗/群像..." />
        </label>
        <label>
          目标长度
          <input v-model="creative.target_length" type="text" placeholder="200万字" />
        </label>
      </div>

      <details class="config">
        <summary>参考模式（可选）</summary>
        <div class="grid">
          <label>
            参考书类型
            <select v-model="reference.reference_book.type">
              <option value="book_name">书名</option>
              <option value="upload">自定义文本</option>
            </select>
          </label>
          <label>
            参考内容
            <input v-model="reference.reference_book.content" type="text" placeholder="斗破苍穹 或 粘贴文本" />
          </label>
          <label>
            自定义要求
            <input v-model="reference.custom_requirements" type="text" placeholder="主角性别/时代/限制..." />
          </label>
        </div>
      </details>

      <label>
        项目名称（可选）
        <input v-model="projectName" type="text" placeholder="不填则使用创意前缀" />
      </label>

      <button type="submit" :disabled="loading">开始生成</button>
    </form>

    <div v-if="loading" class="status">生成中…</div>
    <div v-if="error" class="error">错误：{{ error }}</div>

    <div v-if="resp" class="result">
      <h3>蓝图生成成功</h3>
      <p><strong>项目ID：</strong>{{ resp.project_id }}</p>
      <p><strong>模式：</strong>{{ resp.mode }}</p>
      <h4>一句话概述</h4>
      <p>{{ resp.blueprint?.one_sentence_summary }}</p>
      <h4>世界观</h4>
      <pre>{{ resp.blueprint?.world_setting }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { NovelAPI, type BlueprintAutoGenerateResponse } from '@/api/novel'

const mode = ref<'creative' | 'reference' | 'agent'>('creative')
const creative = ref({
  idea: '',
  genre: '',
  style: '',
  target_length: '',
})
const reference = ref({
  reference_book: {
    type: 'book_name' as 'book_name' | 'upload',
    content: '',
  },
  custom_requirements: '',
})
const projectName = ref('')
const loading = ref(false)
const error = ref<string | null>(null)
const resp = ref<BlueprintAutoGenerateResponse | null>(null)

async function run() {
  loading.value = true
  error.value = null
  resp.value = null
  try {
    resp.value = await NovelAPI.autoGenerateBlueprint({
      mode: mode.value,
      creative_input: creative.value,
      reference_input: mode.value === 'reference' ? reference.value : undefined,
      project_name: projectName.value || undefined,
    })
  } catch (e: any) {
    error.value = e?.message || '生成失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.page { padding: 24px; max-width: 900px; margin: 0 auto; }
.title { font-size: 24px; font-weight: 700; }
.desc { color: #4b5563; margin-bottom: 12px; }
.form { display: flex; flex-direction: column; gap: 12px; background: #fff; padding: 16px; border: 1px solid #e5e7eb; border-radius: 12px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px,1fr)); gap: 12px; }
label { display: flex; flex-direction: column; gap: 6px; font-weight: 600; color: #374151; }
input, select, textarea { border: 1px solid #d1d5db; border-radius: 8px; padding: 8px; font-size: 14px; }
button { align-self: flex-start; background: linear-gradient(90deg,#2563eb,#7c3aed); color: #fff; border: none; padding: 10px 16px; border-radius: 10px; cursor: pointer; }
button:disabled { opacity: 0.6; cursor: not-allowed; }
.status { margin-top: 12px; color: #2563eb; }
.error { margin-top: 12px; color: #dc2626; }
.result { margin-top: 16px; background: #f9fafb; padding: 12px; border-radius: 12px; border: 1px solid #e5e7eb; }
pre { white-space: pre-wrap; background: #111827; color: #e5e7eb; padding: 10px; border-radius: 8px; }
.config { border: 1px solid #e5e7eb; padding: 8px; border-radius: 8px; }
.config summary { cursor: pointer; font-weight: 700; }
</style>
