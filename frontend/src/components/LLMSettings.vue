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
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-gray-800">🎯 AI 功能路由分配</h3>
        <div class="flex gap-2">
          <span class="text-sm text-gray-600 mr-2">一键切换至：</span>
          <button
            v-for="index in 4"
            :key="index"
            @click="switchAllToRoute(index - 1)"
            class="text-xs px-3 py-1 rounded transition-colors"
            :class="routes[index - 1].enabled
              ? 'bg-indigo-100 text-indigo-700 hover:bg-indigo-200'
              : 'bg-gray-100 text-gray-400 cursor-not-allowed'"
            :disabled="!routes[index - 1].enabled"
          >
            路由{{ index }}
          </button>
        </div>
      </div>
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

    <!-- 混合生成配置 -->
    <div class="mb-6">
      <h3 class="text-lg font-semibold text-gray-800 mb-4">🎨 混合生成模式</h3>
      <div class="p-4 bg-purple-50 border border-purple-200 rounded-lg">
        <div class="flex items-center justify-between mb-4">
          <div>
            <div class="font-medium text-gray-800">启用混合生成</div>
            <div class="text-xs text-gray-600 mt-1">
              多版本生成时，每个版本使用不同的AI路由，获得更多样化的结果
            </div>
          </div>
          <label class="flex items-center cursor-pointer">
            <input
              type="checkbox"
              v-model="mixedGeneration.enabled"
              class="w-5 h-5 text-purple-600 rounded focus:ring-purple-500"
            >
          </label>
        </div>

        <div v-if="mixedGeneration.enabled" class="space-y-4">
          <!-- 大纲混合生成配置 -->
          <div class="p-3 bg-white rounded-lg border border-purple-100">
            <div class="font-medium text-sm text-gray-700 mb-2">📝 大纲生成路由分配</div>
            <div class="grid grid-cols-5 gap-2">
              <div
                v-for="versionIndex in 5"
                :key="'outline-' + versionIndex"
                class="flex flex-col items-center"
              >
                <span class="text-xs text-gray-500 mb-1">版本{{ versionIndex }}</span>
                <select
                  v-model="mixedGeneration.outline[versionIndex - 1]"
                  class="text-xs px-2 py-1 border border-gray-300 rounded focus:outline-none focus:ring-purple-500 focus:border-purple-500 w-full"
                >
                  <option :value="0">路由1</option>
                  <option :value="1">路由2</option>
                  <option :value="2">路由3</option>
                  <option :value="3">路由4</option>
                  <option :value="-1">随机</option>
                </select>
              </div>
            </div>
            <div class="text-xs text-gray-500 mt-2">
              💡 提示：如果只生成2个版本，只有前2个路由配置会被使用
            </div>
          </div>

          <!-- 章节混合生成配置 -->
          <div class="p-3 bg-white rounded-lg border border-purple-100">
            <div class="font-medium text-sm text-gray-700 mb-2">📖 章节生成路由分配</div>
            <div class="grid grid-cols-5 gap-2">
              <div
                v-for="versionIndex in 5"
                :key="'chapter-' + versionIndex"
                class="flex flex-col items-center"
              >
                <span class="text-xs text-gray-500 mb-1">版本{{ versionIndex }}</span>
                <select
                  v-model="mixedGeneration.chapter[versionIndex - 1]"
                  class="text-xs px-2 py-1 border border-gray-300 rounded focus:outline-none focus:ring-purple-500 focus:border-purple-500 w-full"
                >
                  <option :value="0">路由1</option>
                  <option :value="1">路由2</option>
                  <option :value="2">路由3</option>
                  <option :value="3">路由4</option>
                  <option :value="-1">随机</option>
                </select>
              </div>
            </div>
            <div class="text-xs text-gray-500 mt-2">
              💡 提示：选择"随机"会从所有已启用的路由中随机选择
            </div>
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

// 混合生成配置
const mixedGeneration = ref({
  enabled: false,
  outline: [0, 1, 2, 0, 1],  // 默认：前3个版本用不同路由，后2个循环使用
  chapter: [0, 1, 0, 1, 2],  // 默认：版本1用路由1，版本2用路由2，以此类推
});

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
        if (parsed.mixedGeneration) {
          mixedGeneration.value = parsed.mixedGeneration;
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

const switchAllToRoute = (routeIndex: number) => {
  const route = routes.value[routeIndex];
  if (!route.enabled) {
    alert('❌ 该路由未启用，无法切换！');
    return;
  }
  if (!route.url || !route.apiKey || !route.model) {
    alert('⚠️ 该路由配置不完整，请先完成配置！');
    return;
  }

  aiFunctions.value.forEach(func => {
    func.routeIndex = routeIndex;
  });

  alert(`✅ 已将所有AI功能切换到路由${routeIndex + 1}！\n\n记得点击"保存配置"按钮。`);
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
      mixedGeneration: mixedGeneration.value,
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
    mixedGeneration.value = {
      enabled: false,
      outline: [0, 1, 2, 0, 1],
      chapter: [0, 1, 0, 1, 2],
    };
    alert('✅ 已重置为默认配置！记得点击"保存配置"按钮。');
  }
};
</script>
