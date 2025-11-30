<template>
  <div class="page">
    <h2 class="title">讨论模式生成</h2>
    <p class="desc">独立的 Planner/Writer/Reviewer 协作生成路径，可选分卷决策和自动上传番茄。</p>

    <form class="form" @submit.prevent="runGeneration">
      <div class="grid">
        <label>
          项目ID
          <input v-model.number="form.project_id" type="number" required />
        </label>
        <label>
          章节号
          <input v-model.number="form.chapter_number" type="number" required />
        </label>
        <label>
          当前卷号
          <input v-model.number="form.current_volume_number" type="number" min="1" />
        </label>
        <label>
          当前卷已有章节数
          <input v-model.number="form.current_volume_chapters" type="number" min="0" />
        </label>
      </div>

      <div class="grid">
        <label>
          类型
          <input v-model="form.genre" type="text" placeholder="玄幻/都市…" />
        </label>
        <label>
          目标字数
          <input v-model.number="form.word_count" type="number" min="500" />
        </label>
      </div>

      <label>
        前情提要
        <textarea v-model="form.previous_summary" rows="3" placeholder="可选：上一章摘要"></textarea>
      </label>
      <label>
        角色状态
        <textarea v-model="form.character_states" rows="3" placeholder="可选：主要角色状态"></textarea>
      </label>
      <label>
        蓝图摘要
        <textarea v-model="form.blueprint_summary" rows="3" placeholder="可选：蓝图概要"></textarea>
      </label>

      <div class="grid">
        <label class="inline">
          <input v-model="form.auto_upload" type="checkbox" />
          生成后自动上传番茄
        </label>
        <label v-if="form.auto_upload">
          番茄账号标识
          <input v-model="form.fanqie_account" type="text" placeholder="fanqie账号标识" />
        </label>
      </div>

      <details class="config">
        <summary>高级配置</summary>
        <div class="grid">
          <label>
            最大迭代
            <input v-model.number="form.config.max_iterations" type="number" min="1" max="10" />
          </label>
          <label>
            通过分
            <input v-model.number="form.config.approval_threshold" type="number" min="0" max="100" />
          </label>
          <label>
            讨论阈值
            <input v-model.number="form.config.discussion_threshold" type="number" min="0" max="100" />
          </label>
          <label>
            分卷决策
            <select v-model="form.config.enable_volume_decision">
              <option :value="true">启用</option>
              <option :value="false">关闭</option>
            </select>
          </label>
          <label>
            最少章节/卷
            <input v-model.number="form.config.min_chapters_per_volume" type="number" min="1" />
          </label>
          <label>
            最多章节/卷
            <input v-model.number="form.config.max_chapters_per_volume" type="number" min="1" />
          </label>
        </div>
      </details>

      <button type="submit" :disabled="loading">开始生成</button>
    </form>

    <div v-if="loading" class="status">生成中…</div>
    <div v-if="error" class="error">错误：{{ error }}</div>

    <div v-if="result" class="result">
      <h3>结果</h3>
      <p><strong>标题：</strong>{{ result.title || '未命名' }}</p>
      <p><strong>评分：</strong>{{ result.final_score }} 分</p>
      <p><strong>分卷决策：</strong>
        <span v-if="result.volume_decision">
          {{ result.volume_decision.should_create_volume ? '分卷' : '不分卷' }} / {{ result.volume_decision.volume_title || '未定' }}
        </span>
        <span v-else>无</span>
      </p>
      <h4>正文</h4>
      <pre class="content">{{ result.content }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { DiscussionAPI, type DiscussionChapterRequest, type DiscussionChapterResponse } from '@/api/discussion'

const loading = ref(false)
const error = ref<string | null>(null)
const result = ref<DiscussionChapterResponse | null>(null)

const form = ref<DiscussionChapterRequest>({
  project_id: 1,
  chapter_number: 1,
  genre: '',
  word_count: 3000,
  previous_summary: '',
  character_states: '',
  blueprint_summary: '',
  volumes_snapshot: undefined,
  current_volume_chapters: 0,
  current_volume_number: 1,
  auto_upload: false,
  fanqie_account: '',
  config: {
    max_iterations: 5,
    approval_threshold: 80,
    discussion_threshold: 60,
    timeout_seconds: 300,
    enable_tools: true,
    verbose: false,
    enable_volume_decision: true,
    min_chapters_per_volume: 15,
    max_chapters_per_volume: 30,
  },
})

async function runGeneration() {
  loading.value = true
  error.value = null
  result.value = null
  try {
    result.value = await DiscussionAPI.generateChapter(form.value)
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
.desc { color: #4b5563; margin-bottom: 16px; }
.form { display: flex; flex-direction: column; gap: 12px; background: #fff; padding: 16px; border: 1px solid #e5e7eb; border-radius: 12px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px,1fr)); gap: 12px; }
label { display: flex; flex-direction: column; gap: 6px; font-weight: 600; color: #374151; }
input, textarea, select { border: 1px solid #d1d5db; border-radius: 8px; padding: 8px; font-size: 14px; }
button { align-self: flex-start; background: linear-gradient(90deg,#6366f1,#8b5cf6); color: #fff; border: none; padding: 10px 16px; border-radius: 10px; cursor: pointer; }
button:disabled { opacity: 0.6; cursor: not-allowed; }
.status { margin-top: 12px; color: #2563eb; }
.error { margin-top: 12px; color: #dc2626; }
.result { margin-top: 16px; background: #f9fafb; padding: 12px; border-radius: 12px; border: 1px solid #e5e7eb; }
.content { white-space: pre-wrap; background: #111827; color: #e5e7eb; padding: 12px; border-radius: 8px; max-height: 400px; overflow: auto; }
.config { border: 1px solid #e5e7eb; padding: 8px; border-radius: 8px; }
.config summary { cursor: pointer; font-weight: 700; }
</style>
