<template>
  <n-card :bordered="false" class="admin-card">
    <template #header>
      <div class="card-header">
        <span class="card-title">用户管理</span>
        <n-space :size="12">
          <n-input
            v-model:value="keyword"
            clearable
            round
            placeholder="搜索用户名或邮箱"
            @update:value="handleSearch"
            class="search-input"
          />
          <n-button type="primary" size="small" @click="openCreateModal">
            创建用户
          </n-button>
          <n-button quaternary size="small" @click="fetchUsers" :loading="loading">
            刷新
          </n-button>
        </n-space>
      </div>
    </template>

    <n-space vertical size="large">
      <n-alert v-if="error" type="error" closable @close="error = null">
        {{ error }}
      </n-alert>

      <n-spin :show="loading">
        <n-data-table
          :columns="columns"
          :data="filteredUsers"
          :bordered="false"
          :pagination="pagination"
          :row-key="rowKey"
          class="user-table"
        />
      </n-spin>
    </n-space>
  </n-card>

  <!-- 创建用户对话框 -->
  <n-modal
    v-model:show="createModalVisible"
    preset="card"
    title="创建新用户"
    class="create-modal"
    :style="{ width: '480px', maxWidth: '92vw' }"
  >
    <n-form label-placement="top" :model="createForm">
      <n-form-item label="用户名" required>
        <n-input
          v-model:value="createForm.username"
          placeholder="请输入用户名（3-64字符）"
          :maxlength="64"
        />
      </n-form-item>
      <n-form-item label="邮箱">
        <n-input v-model:value="createForm.email" placeholder="请输入邮箱（可选）" />
      </n-form-item>
      <n-form-item label="初始密码" required>
        <n-input
          v-model:value="createForm.password"
          placeholder="请输入初始密码（至少6位）"
          type="password"
          show-password-on="click"
        />
      </n-form-item>
      <n-form-item label="权限">
        <n-checkbox v-model:checked="createForm.is_admin">设为管理员</n-checkbox>
      </n-form-item>
    </n-form>
    <template #footer>
      <n-space justify="end">
        <n-button quaternary @click="closeCreateModal">取消</n-button>
        <n-button type="primary" :loading="creating" @click="createUser">创建</n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NCheckbox,
  NDataTable,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NPopconfirm,
  NSpin,
  NTag,
  NSpace,
  type DataTableColumns,
  useDialog,
  useMessage
} from 'naive-ui'

import { AdminAPI, type AdminUser } from '@/api/admin'

const users = ref<AdminUser[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const keyword = ref('')
const creating = ref(false)
const message = useMessage()
const dialog = useDialog()

const pagination = reactive({
  page: 1,
  pageSize: 10,
  showSizePicker: false
})

const createModalVisible = ref(false)
const createForm = reactive({
  username: '',
  email: '',
  password: '',
  is_admin: false
})

const columns: DataTableColumns<AdminUser> = [
  {
    title: 'ID',
    key: 'id',
    sorter: (a, b) => a.id - b.id,
    width: 80
  },
  {
    title: '用户名',
    key: 'username',
    ellipsis: { tooltip: true }
  },
  {
    title: '邮箱',
    key: 'email',
    ellipsis: { tooltip: true },
    render(row) {
      return row.email || '—'
    }
  },
  {
    title: '权限',
    key: 'is_admin',
    align: 'center',
    render(row) {
      return h(
        NTag,
        {
          type: row.is_admin ? 'success' : 'default',
          bordered: false,
          size: 'small'
        },
        { default: () => (row.is_admin ? '管理员' : '普通用户') }
      )
    }
  },
  {
    title: '状态',
    key: 'is_active',
    align: 'center',
    render(row) {
      return h(
        NTag,
        {
          type: row.is_active ? 'success' : 'error',
          bordered: false,
          size: 'small'
        },
        { default: () => (row.is_active ? '正常' : '已禁用') }
      )
    }
  },
  {
    title: '操作',
    key: 'actions',
    align: 'center',
    width: 180,
    render(row) {
      return h(
        NSpace,
        { size: 8, justify: 'center' },
        {
          default: () => [
            h(
              NButton,
              {
                size: 'small',
                type: row.is_active ? 'warning' : 'success',
                tertiary: true,
                onClick: () => toggleUserActive(row)
              },
              { default: () => (row.is_active ? '禁用' : '启用') }
            ),
            h(
              NPopconfirm,
              {
                onPositiveClick: () => deleteUser(row)
              },
              {
                trigger: () =>
                  h(
                    NButton,
                    {
                      size: 'small',
                      type: 'error',
                      tertiary: true
                    },
                    { default: () => '删除' }
                  ),
                default: () => `确定删除用户 "${row.username}" 吗？此操作不可恢复！`
              }
            )
          ]
        }
      )
    }
  }
]

const filteredUsers = computed(() => {
  if (!keyword.value.trim()) {
    return users.value
  }
  const q = keyword.value.trim().toLowerCase()
  return users.value.filter(
    (user) =>
      user.username.toLowerCase().includes(q) ||
      (user.email && user.email.toLowerCase().includes(q))
  )
})

const rowKey = (row: AdminUser) => row.id

const fetchUsers = async () => {
  loading.value = true
  error.value = null
  try {
    users.value = await AdminAPI.listUsers()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '获取用户数据失败'
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
}

const openCreateModal = () => {
  createForm.username = ''
  createForm.email = ''
  createForm.password = ''
  createForm.is_admin = false
  createModalVisible.value = true
}

const closeCreateModal = () => {
  createModalVisible.value = false
}

const createUser = async () => {
  if (!createForm.username.trim()) {
    message.error('请输入用户名')
    return
  }
  if (createForm.username.length < 3) {
    message.error('用户名至少3个字符')
    return
  }
  if (!createForm.password || createForm.password.length < 6) {
    message.error('密码至少6位')
    return
  }

  creating.value = true
  try {
    const newUser = await AdminAPI.createUser({
      username: createForm.username.trim(),
      email: createForm.email.trim() || undefined,
      password: createForm.password,
      is_admin: createForm.is_admin
    })
    users.value.unshift(newUser)
    message.success(`用户 "${newUser.username}" 创建成功`)
    closeCreateModal()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '创建用户失败')
  } finally {
    creating.value = false
  }
}

const toggleUserActive = async (user: AdminUser) => {
  try {
    const updated = await AdminAPI.toggleUserActive(user.id)
    const index = users.value.findIndex((u) => u.id === user.id)
    if (index !== -1) {
      users.value[index] = updated
    }
    message.success(`用户 "${user.username}" 已${updated.is_active ? '启用' : '禁用'}`)
  } catch (err) {
    message.error(err instanceof Error ? err.message : '操作失败')
  }
}

const deleteUser = async (user: AdminUser) => {
  try {
    await AdminAPI.deleteUser(user.id)
    users.value = users.value.filter((u) => u.id !== user.id)
    message.success(`用户 "${user.username}" 已删除`)
  } catch (err) {
    message.error(err instanceof Error ? err.message : '删除失败')
  }
}

onMounted(fetchUsers)
</script>

<style scoped>
.admin-card {
  width: 100%;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.card-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: #1f2937;
}

.search-input {
  width: min(230px, 60vw);
}

@media (max-width: 767px) {
  .card-header {
    flex-direction: column;
    align-items: stretch;
  }

  .card-title {
    font-size: 1.125rem;
  }

  .search-input {
    width: 100%;
  }
}
</style>
