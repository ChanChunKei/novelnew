<template>
  <n-message-provider>
    <n-dialog-provider>
      <n-layout has-sider class="admin-layout">
        <n-layout-sider
          collapse-mode="width"
          :collapsed="collapsed"
          :collapsed-width="64"
          :width="240"
          bordered
          show-trigger
          @collapse="collapsed = true"
          @expand="collapsed = false"
        >
          <div class="sider-header">
            <span class="logo" v-if="!collapsed">Arboris 管理台</span>
            <span class="logo-small" v-else>管理</span>
          </div>
          <n-menu
            :value="activeKey"
            :options="menuOptions"
            :collapsed="collapsed"
            :collapsed-width="64"
            :accordion="true"
            @update:value="handleMenuSelect"
          />
        </n-layout-sider>

        <n-layout>
          <n-layout-header bordered class="admin-header">
            <n-space align="center" justify="space-between" class="header-content">
              <n-space align="center" :size="12">
                <n-button
                  class="mobile-trigger"
                  quaternary
                  circle
                  size="small"
                  @click="collapsed = !collapsed"
                >
                  <template #icon>
                    <span class="icon">☰</span>
                  </template>
                </n-button>
                <span class="header-title">{{ currentMenuLabel }}</span>
              </n-space>
              <n-space align="center" :size="10">
                <span class="header-subtitle">高效掌控平台运行状态</span>
                <n-button size="small" type="primary" ghost @click="goBack">
                  返回业务系统
                </n-button>
              </n-space>
            </n-space>
          </n-layout-header>
          <n-layout-content class="admin-content">
            <n-scrollbar class="content-scroll">
              <component :is="activeComponent" />
            </n-scrollbar>
          </n-layout-content>
        </n-layout>
      </n-layout>
    </n-dialog-provider>
  </n-message-provider>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, h, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  NButton,
  NDialogProvider,
  NLayout,
  NLayoutContent,
  NLayoutHeader,
  NLayoutSider,
  NMenu,
  NMessageProvider,
  NScrollbar,
  NSpace,
  type MenuOption
} from 'naive-ui'
import { useRoute, useRouter } from 'vue-router'

const collapsed = ref(false)
const activeKey = ref<MenuKey>('statistics')
const router = useRouter()
const route = useRoute()

type MenuKey =
  | 'statistics'
  | 'users'
  | 'prompts'
  | 'novels'
  | 'logs'
  | 'settings'
  | 'password'

const components: Record<MenuKey, ReturnType<typeof defineAsyncComponent>> = {
  statistics: defineAsyncComponent(() => import('../components/admin/Statistics.vue')),
  users: defineAsyncComponent(() => import('../components/admin/UserManagement.vue')),
  prompts: defineAsyncComponent(() => import('../components/admin/PromptManagement.vue')),
  novels: defineAsyncComponent(() => import('../components/admin/NovelManagement.vue')),
  logs: defineAsyncComponent(() => import('../components/admin/UpdateLogManagement.vue')),
  settings: defineAsyncComponent(() => import('../components/admin/SettingsManagement.vue')),
  password: defineAsyncComponent(() => import('../components/admin/PasswordManagement.vue'))
}

const iconRenderers: Record<MenuKey, () => any> = {
  statistics: () => h('span', { class: 'menu-icon' }, '📊'),
  users: () => h('span', { class: 'menu-icon' }, '👤'),
  prompts: () => h('span', { class: 'menu-icon' }, '🗒️'),
  novels: () => h('span', { class: 'menu-icon' }, '📚'),
  logs: () => h('span', { class: 'menu-icon' }, '📝'),
  settings: () => h('span', { class: 'menu-icon' }, '⚙️'),
  password: () => h('span', { class: 'menu-icon' }, '🔒')
}

const menuOptions: MenuOption[] = [
  { key: 'statistics', label: '数据总览', icon: iconRenderers.statistics },
  { key: 'users', label: '用户管理', icon: iconRenderers.users },
  { key: 'prompts', label: '提示词管理', icon: iconRenderers.prompts },
  { key: 'novels', label: '小说项目', icon: iconRenderers.novels },
  { key: 'logs', label: '更新日志', icon: iconRenderers.logs },
  { key: 'settings', label: '系统配置', icon: iconRenderers.settings },
  { key: 'password', label: '安全中心', icon: iconRenderers.password }
]

const isMenuKey = (key: string): key is MenuKey => key in components

const syncActiveKeyWithRoute = () => {
  const tab = route.query.tab
  if (typeof tab === 'string' && isMenuKey(tab)) {
    activeKey.value = tab
  }
}

const handleMenuSelect = (key: string) => {
  if (!isMenuKey(key)) {
    return
  }
  activeKey.value = key
  router.replace({ name: 'admin', query: { tab: key } })
}

const activeComponent = computed(() => components[activeKey.value])
const currentMenuLabel = computed(() => {
  const match = menuOptions.find((option) => option.key === activeKey.value)
  return match ? (match.label as string) : ''
})

const goBack = () => {
  router.push('/')
}

const updateCollapsedByWidth = () => {
  collapsed.value = window.innerWidth < 992
}

onMounted(() => {
  updateCollapsedByWidth()
  window.addEventListener('resize', updateCollapsedByWidth)
  syncActiveKeyWithRoute()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateCollapsedByWidth)
})

watch(
  () => route.query.tab,
  () => {
    syncActiveKeyWithRoute()
  }
)
</script>

<style scoped>
.admin-layout {
  height: 100vh;
}

.sider-header {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: #1f2937;
}

.logo {
  font-size: 1.1rem;
}

.logo-small {
  font-size: 0.9rem;
}

.admin-header {
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(8px);
  padding: 0 20px;
}

.header-content {
  width: 100%;
  height: 64px;
}

.header-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: #1f2937;
}

.header-subtitle {
  font-size: 0.95rem;
  color: #6b7280;
}

.admin-content {
  background: #f5f5f7;
}

.content-scroll {
  height: calc(100vh - 64px);
  padding: 24px;
  box-sizing: border-box;
}

.menu-icon {
  font-size: 1.1rem;
}

.mobile-trigger {
  display: none;
}

@media (max-width: 991px) {
  .content-scroll {
    padding: 16px;
  }

  .mobile-trigger {
    display: inline-flex;
  }

  .header-content {
    flex-direction: column;
    align-items: stretch;
    gap: 12px !important;
  }

  .header-subtitle {
    font-size: 0.9rem;
  }
}
</style>
