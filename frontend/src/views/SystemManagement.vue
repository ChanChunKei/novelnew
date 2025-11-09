<template>
  <div class="system-management">
    <div class="container mx-auto px-4 py-8">
      <!-- Header -->
      <div class="header mb-8">
        <h1 class="text-3xl font-bold text-slate-900">系统管理</h1>
        <p class="text-slate-600 mt-2">AI 配置、监控、异步任务等系统功能管理</p>
      </div>

      <!-- Tabs -->
      <div class="tabs-container">
        <div class="tabs">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            @click="activeTab = tab.key"
            :class="['tab', { 'tab-active': activeTab === tab.key }]"
          >
            <component :is="tab.icon" class="w-5 h-5" />
            <span>{{ tab.label }}</span>
            <span v-if="tab.badge" class="badge">{{ tab.badge }}</span>
          </button>
        </div>
      </div>

      <!-- Tab Content -->
      <div class="tab-content">
        <!-- AI 供应商管理 -->
        <div v-if="activeTab === 'providers'" class="content-panel">
          <AIProviderManagement />
        </div>

        <!-- AI 功能配置 -->
        <div v-else-if="activeTab === 'functions'" class="content-panel">
          <AIFunctionConfig />
        </div>

        <!-- AI 调用监控 -->
        <div v-else-if="activeTab === 'monitoring'" class="content-panel">
          <AIMonitoring />
        </div>

        <!-- 异步任务 -->
        <div v-else-if="activeTab === 'tasks'" class="content-panel">
          <AsyncTaskManagement />
        </div>

        <!-- 番茄小说管理 -->
        <div v-else-if="activeTab === 'fanqie'" class="content-panel">
          <FanqieManagement />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, h } from 'vue'
import AIProviderManagement from '@/components/system/AIProviderManagement.vue'
import AIFunctionConfig from '@/components/system/AIFunctionConfig.vue'
import AIMonitoring from '@/components/system/AIMonitoring.vue'
import AsyncTaskManagement from '@/components/system/AsyncTaskManagement.vue'
import FanqieManagement from '@/components/system/FanqieManagement.vue'

const activeTab = ref('providers')

const tabs = [
  {
    key: 'providers',
    label: 'AI 供应商',
    icon: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
      h('path', { d: 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5' })
    ])
  },
  {
    key: 'functions',
    label: '功能配置',
    icon: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
      h('circle', { cx: 12, cy: 12, r: 3 }),
      h('path', { d: 'M12 1v6m0 6v6M5.64 5.64l4.24 4.24m4.24 4.24l4.24 4.24M1 12h6m6 0h6M5.64 18.36l4.24-4.24m4.24-4.24l4.24-4.24' })
    ])
  },
  {
    key: 'monitoring',
    label: 'AI 监控',
    icon: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
      h('path', { d: 'M3 3v18h18' }),
      h('path', { d: 'M18 17V9M13 17V5M8 17v-3' })
    ])
  },
  {
    key: 'tasks',
    label: '异步任务',
    icon: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
      h('circle', { cx: 12, cy: 12, r: 10 }),
      h('polyline', { points: '12 6 12 12 16 14' })
    ]),
    badge: '3'
  },
  {
    key: 'fanqie',
    label: '番茄小说',
    icon: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
      h('path', { d: 'M4 19.5A2.5 2.5 0 016.5 17H20' }),
      h('path', { d: 'M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z' })
    ])
  }
]
</script>

<style scoped>
.system-management {
  min-height: 100vh;
  background: linear-gradient(to bottom right, rgb(248 250 252), rgb(239 246 255 / 0.3), rgb(238 242 255 / 0.4));
}

.header {
  border-bottom: 1px solid rgb(226 232 240);
  padding-bottom: 1.5rem;
}

.tabs-container {
  background-color: white;
  border-radius: 0.5rem;
  box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  border: 1px solid rgb(226 232 240);
  padding: 0.5rem;
  margin-bottom: 1.5rem;
}

.tabs {
  display: flex;
  gap: 0.5rem;
  overflow-x: auto;
}

.tab {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  transition: all 0.2s;
  white-space: nowrap;
  color: rgb(71 85 105);
}

.tab:hover {
  color: rgb(15 23 42);
  background-color: rgb(248 250 252);
}

.tab-active {
  background: linear-gradient(to right, rgb(238 242 255), rgb(224 231 255 / 0.8));
  color: rgb(67 56 202);
  box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  outline: 1px solid rgb(199 210 254 / 0.5);
}

.badge {
  margin-left: auto;
  padding: 0.125rem 0.5rem;
  font-size: 0.75rem;
  font-weight: 600;
  background-color: rgb(254 226 226);
  color: rgb(185 28 28);
  border-radius: 9999px;
}

.tab-content {
  background-color: white;
  border-radius: 0.5rem;
  box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  border: 1px solid rgb(226 232 240);
  padding: 1.5rem;
}

.content-panel {
  min-height: 600px;
}
</style>

