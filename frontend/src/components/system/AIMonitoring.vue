<template>
  <div class="ai-monitoring">
    <div class="header">
      <h2 class="title">AI 调用监控</h2>
      <div class="date-range">
        <input v-model="startDate" type="date" class="date-input" />
        <span class="text-slate-500">至</span>
        <input v-model="endDate" type="date" class="date-input" />
        <button @click="loadStats" class="btn-primary">查询</button>
      </div>
    </div>

    <!-- Stats Cards -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon bg-blue-100 text-blue-600">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
          </svg>
        </div>
        <div class="stat-content">
          <p class="stat-label">总调用次数</p>
          <p class="stat-value">{{ stats.total_calls || 0 }}</p>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon bg-green-100 text-green-600">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <div class="stat-content">
          <p class="stat-label">成功率</p>
          <p class="stat-value">{{ stats.success_rate || 0 }}%</p>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon bg-yellow-100 text-yellow-600">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <div class="stat-content">
          <p class="stat-label">平均响应时间</p>
          <p class="stat-value">{{ stats.avg_response_time || 0 }}ms</p>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon bg-purple-100 text-purple-600">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <div class="stat-content">
          <p class="stat-label">总成本</p>
          <p class="stat-value">${{ stats.total_cost || 0 }}</p>
        </div>
      </div>
    </div>

    <!-- Function Stats -->
    <div class="section">
      <h3 class="section-title">功能调用统计</h3>
      <div class="table-container">
        <table class="stats-table">
          <thead>
            <tr>
              <th>功能名称</th>
              <th>调用次数</th>
              <th>成功次数</th>
              <th>失败次数</th>
              <th>降级次数</th>
              <th>平均耗时</th>
              <th>成本</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="func in stats.function_stats" :key="func.name">
              <td class="font-medium">{{ func.display_name }}</td>
              <td>{{ func.total_calls }}</td>
              <td class="text-green-600">{{ func.success_count }}</td>
              <td class="text-red-600">{{ func.failure_count }}</td>
              <td class="text-yellow-600">{{ func.fallback_count }}</td>
              <td>{{ func.avg_time }}ms</td>
              <td>${{ func.cost }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Provider Stats -->
    <div class="section">
      <h3 class="section-title">供应商使用统计</h3>
      <div class="provider-stats">
        <div v-for="provider in stats.provider_stats" :key="provider.name" class="provider-stat-card">
          <h4 class="provider-name">{{ provider.name }}</h4>
          <div class="provider-metrics">
            <div class="metric">
              <span class="metric-label">调用:</span>
              <span class="metric-value">{{ provider.calls }}</span>
            </div>
            <div class="metric">
              <span class="metric-label">成功率:</span>
              <span class="metric-value">{{ provider.success_rate }}%</span>
            </div>
            <div class="metric">
              <span class="metric-label">Token:</span>
              <span class="metric-value">{{ provider.total_tokens }}</span>
            </div>
            <div class="metric">
              <span class="metric-label">成本:</span>
              <span class="metric-value">${{ provider.cost }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { aiConfigApi } from '@/api/novel'

const startDate = ref('')
const endDate = ref('')
const stats = ref<any>({
  total_calls: 0,
  success_rate: 0,
  avg_response_time: 0,
  total_cost: 0,
  function_stats: [],
  provider_stats: []
})

const loadStats = async () => {
  try {
    const data = await aiConfigApi.getCallStats(startDate.value, endDate.value)
    stats.value = data
  } catch (error: any) {
    console.error('加载统计数据失败:', error)
  }
}

onMounted(() => {
  // 默认查询最近7天
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - 7)
  
  endDate.value = end.toISOString().split('T')[0]
  startDate.value = start.toISOString().split('T')[0]
  
  loadStats()
})
</script>


