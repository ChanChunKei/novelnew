<template>
  <div class="bg-white/70 backdrop-blur-xl rounded-2xl shadow-lg p-8">
    <h2 class="text-2xl font-bold text-gray-800 mb-4">AI 模型路由配置</h2>

    <!-- 说明文档 -->
    <div class="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
      <h3 class="text-sm font-semibold text-blue-900 mb-2">📖 配置说明</h3>
      <ul class="text-xs text-blue-800 space-y-1">
        <li>• 配置 <strong>4个路由槽位</strong>，每个路由可以设置不同的 API 地址、Key 和模型</li>
        <li>• <strong>11个AI功能</strong> 可以自由选择使用哪个路由</li>
        <li>• 灵活配置，支持多个 API 提供商（OpenAI、SiliconFlow、Gemini 等）</li>
      </ul>
    </div>

    <!-- 路由配置 -->
    <div class="mb-8">
      <h3 class="text-lg font-semibold text-gray-800 mb-4">🔧 路由配置</h3>
      <div class="space-y-4">
        <div
          v-for="(route, index) in routes"
          :key="index"
          class="p-4 border-2 rounded-lg"
          :class="route.enabled ? 'border-indigo-300 bg-indigo-50' : 'border-gray-200 bg-gray-50'"
        >
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-3">
              <span class="text-lg font-bold text-gray-700">路由{{ index + 1 }}</span>
              <label class="flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  v-model="route.enabled"
                  class="w-4 h-4 text-indigo-600 rounded focus:ring-indigo-500"
                >
                <span class="ml-2 text-sm text-gray-600">启用</span>
              </label>
            </div>
            <button
              v-if="route.enabled"
              @click="testRoute(index)"
              class="text-xs px-3 py-1 bg-green-500 text-white rounded hover:bg-green-600"
            >
              测试连接
            </button>
          </div>

          <div v-if="route.enabled" class="space-y-3">
            <!-- API URL -->
            <div>
              <label class="block text-xs font-medium text-gray-700 mb-1">
                API URL
              </label>
              <input
                type="text"
                v-model="route.url"
                class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                placeholder="https://api.example.com/v1"
              >
            </div>

            <!-- API Key -->
            <div>
              <label class="block text-xs font-medium text-gray-700 mb-1">
                API Key
              </label>
              <input
                type="password"
                v-model="route.apiKey"
                class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 font-mono"
                placeholder="sk-xxxxxxxxxxxxxxxx"
              >
            </div>

            <!-- 模型名称 -->
            <div>
              <label class="block text-xs font-medium text-gray-700 mb-1">
                模型名称
              </label>
              <input
                type="text"
                v-model="route.model"
                class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                placeholder="gpt-4o-mini / deepseek-ai/DeepSeek-R1"
              >
            </div>

            <!-- 快速填充按钮 -->
            <div class="flex gap-2 pt-2">
              <button
                @click="fillPreset(index, 'siliconflow')"
                class="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
              >
                SiliconFlow
              </button>
              <button
                @click="fillPreset(index, 'openai')"
                class="text-xs px-2 py-1 bg-green-100 text-green-700 rounded hover:bg-green-200"
              >
                OpenAI
              </button>
              <button
                @click="fillPreset(index, 'gemini')"
                class="text-xs px-2 py-1 bg-orange-100 text-orange-700 rounded hover:bg-orange-200"
              >
                Gemini
              </button>
              <button
                @click="fillPreset(index, 'deepseek')"
                class="text-xs px-2 py-1 bg-purple-100 text-purple-700 rounded hover:bg-purple-200"
              >
                DeepSeek
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- AI 功能路由分配 -->
    <div class="mb-6">
      <h3 class="text-lg font-semibold text-gray-800 mb-4">🎯 AI 功能路由分配</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div
          v-for="func in aiFunctions"
          :key="func.key"
          class="p-3 border border-gray-200 rounded-lg hover:border-indigo-300 transition-colors"
        >
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium text-gray-700">{{ func.name }}</span>
            <select
              v-model="func.routeIndex"
              class="text-sm px-2 py-1 border border-gray-300 rounded focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
            >
              <option :value="0">路由1</option>
              <option :value="1">路由2</option>
              <option :value="2">路由3</option>
              <option :value="3">路由4</option>
            </select>
          </div>
          <div class="mt-1 text-xs text-gray-500">
            {{ getRouteInfo(func.routeIndex) }}
          </div>
        </div>
      </div>
    </div>

    <!-- 操作按钮 -->
    <div class="flex justify-end space-x-4 pt-4">
      <button
        type="button"
        @click="handleReset"
        class="px-4 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600 transition-colors"
      >
        重置为默认
      </button>
      <button
        @click="handleSave"
        class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
      >
        保存配置
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { getLLMConfig, createOrUpdateLLMConfig } from '@/api/llm';

// 路由配置
interface Route {
  enabled: boolean;
  url: string;
  apiKey: string;
  model: string;
}

// AI 功能
interface AIFunction {
  key: string;
  name: string;
  routeIndex: number;
}

// 4个路由槽位
const routes = ref<Route[]>([
  { enabled: true, url: 'https://api.siliconflow.cn/v1', apiKey: '', model: 'deepseek-ai/DeepSeek-R1' },
  { enabled: false, url: '', apiKey: '', model: '' },
  { enabled: false, url: '', apiKey: '', model: '' },
  { enabled: false, url: '', apiKey: '', model: '' },
]);

// AI功能 (key 必须与后端 AIFunctionType 枚举值一致)
const aiFunctions = ref<AIFunction[]>([
  { key: 'concept_dialogue', name: '文思对话', routeIndex: 0 },
  { key: 'blueprint_generation', name: '蓝图生成', routeIndex: 0 },
  { key: 'chapter_content_writing', name: '章节生成', routeIndex: 0 },
  { key: 'summary_extraction', name: '章节摘要', routeIndex: 0 },
  { key: 'outline_generation', name: '大纲生成', routeIndex: 0 },
  { key: 'basic_analysis', name: '基础分析', routeIndex: 0 },
  { key: 'enhanced_analysis', name: '增强分析', routeIndex: 0 },
  { key: 'character_tracking', name: '角色追踪', routeIndex: 0 },
  { key: 'worldview_expansion', name: '世界观扩展', routeIndex: 0 },
  { key: 'volume_naming', name: '卷名生成', routeIndex: 0 },
  { key: 'ai_denoising', name: 'AI去味', routeIndex: 0 },
]);

// 预设配置
const presets: Record<string, { url: string; model: string }> = {
  siliconflow: {
    url: 'https://api.siliconflow.cn/v1',
    model: 'deepseek-ai/DeepSeek-R1',
  },
  openai: {
    url: 'https://api.openai.com/v1',
    model: 'gpt-4o-mini',
  },
  gemini: {
    url: 'https://generativelanguage.googleapis.com/v1beta/openai',
    model: 'gemini-2.0-flash-exp',
  },
  deepseek: {
    url: 'https://api.deepseek.com/v1',
    model: 'deepseek-chat',
  },
};

onMounted(async () => {
  try {
    const existingConfig = await getLLMConfig();
    if (existingConfig && existingConfig.llm_provider_api_key) {
      try {
        const parsed = JSON.parse(existingConfig.llm_provider_api_key);
        if (parsed.routes && Array.isArray(parsed.routes)) {
          routes.value = parsed.routes;
        }
        if (parsed.functions && Array.isArray(parsed.functions)) {
          aiFunctions.value = parsed.functions;
        }
      } catch (error) {
        console.log('解析配置失败，使用默认值');
      }
    }
  } catch (error) {
    console.log('未找到现有配置，使用默认值');
  }
});

const fillPreset = (index: number, presetKey: string) => {
  const preset = presets[presetKey];
  if (preset) {
    routes.value[index].url = preset.url;
    routes.value[index].model = preset.model;
  }
};

const testRoute = async (index: number) => {
  const route = routes.value[index];
  if (!route.url || !route.apiKey) {
    alert('❌ 请先配置 URL 和 API Key');
    return;
  }
  alert('🔄 测试连接功能待实现...');
};

const getRouteInfo = (routeIndex: number): string => {
  const route = routes.value[routeIndex];
  if (!route.enabled) {
    return '❌ 路由未启用';
  }
  if (!route.url || !route.apiKey) {
    return '⚠️ 路由未配置完整';
  }
  return `✅ ${route.model || '未设置模型'}`;
};

const handleSave = async () => {
  try {
    // 验证至少有一个路由启用
    const hasEnabledRoute = routes.value.some(r => r.enabled);
    if (!hasEnabledRoute) {
      alert('❌ 至少需要启用一个路由！');
      return;
    }

    // 验证启用的路由配置完整
    for (let i = 0; i < routes.value.length; i++) {
      const route = routes.value[i];
      if (route.enabled) {
        if (!route.url || !route.apiKey || !route.model) {
          alert(`❌ 路由${i + 1} 配置不完整！\n请填写 URL、API Key 和模型名称。`);
          return;
        }
      }
    }

    // 序列化配置
    const configJson = JSON.stringify({
      routes: routes.value,
      functions: aiFunctions.value,
    });

    await createOrUpdateLLMConfig({
      llm_provider_api_key: configJson,
      llm_provider_url: '', // 不再使用
      llm_provider_model: '', // 不再使用
    });

    alert('✅ AI 路由配置已保存！\n\n配置将在下次调用 AI 功能时生效。');
  } catch (error: any) {
    alert('❌ 保存失败：' + (error.message || '未知错误'));
  }
};

const handleReset = () => {
  if (confirm('确定要重置为默认配置吗？\n\n这将清空所有自定义设置。')) {
    routes.value = [
      { enabled: true, url: 'https://api.siliconflow.cn/v1', apiKey: '', model: 'deepseek-ai/DeepSeek-R1' },
      { enabled: false, url: '', apiKey: '', model: '' },
      { enabled: false, url: '', apiKey: '', model: '' },
      { enabled: false, url: '', apiKey: '', model: '' },
    ];
    aiFunctions.value.forEach(func => {
      func.routeIndex = 0;
    });
    alert('✅ 已重置为默认配置！记得点击"保存配置"按钮。');
  }
};
</script>
