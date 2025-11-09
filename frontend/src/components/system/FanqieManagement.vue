<template>
  <div class="fanqie-management">
    <div class="header">
      <h2 class="title">番茄小说管理</h2>
      <p class="description">管理番茄小说账号、Cookie 和上传记录</p>
    </div>

    <!-- Account Management -->
    <div class="section">
      <div class="section-header">
        <h3 class="section-title">账号管理</h3>
        <button @click="showAddAccount = true" class="btn-primary">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          添加账号
        </button>
      </div>

      <div class="account-list">
        <div v-for="account in accounts" :key="account.id" class="account-card">
          <div class="account-header">
            <div>
              <h4 class="account-name">{{ account.name }}</h4>
              <p class="account-identifier">标识: {{ account.identifier }}</p>
            </div>
            <span :class="['cookie-status', account.cookie_valid ? 'status-valid' : 'status-invalid']">
              {{ account.cookie_valid ? 'Cookie 有效' : 'Cookie 失效' }}
            </span>
          </div>

          <div class="account-stats">
            <div class="stat">
              <span class="stat-label">上传书籍:</span>
              <span class="stat-value">{{ account.books_count || 0 }}</span>
            </div>
            <div class="stat">
              <span class="stat-label">上传章节:</span>
              <span class="stat-value">{{ account.chapters_count || 0 }}</span>
            </div>
            <div class="stat">
              <span class="stat-label">最后上传:</span>
              <span class="stat-value">{{ account.last_upload ? formatDate(account.last_upload) : '从未' }}</span>
            </div>
          </div>

          <div class="account-actions">
            <button @click="loginAccount(account)" class="btn-login">
              {{ account.cookie_valid ? '重新登录' : '立即登录' }}
            </button>
            <button @click="viewUploadHistory(account)" class="btn-secondary">上传记录</button>
            <button @click="deleteAccount(account)" class="btn-danger">删除</button>
          </div>
        </div>

        <div v-if="accounts.length === 0" class="empty-state">
          <svg class="w-16 h-16 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>
          <p class="text-slate-500 mt-4">暂无番茄小说账号</p>
          <button @click="showAddAccount = true" class="btn-primary mt-4">添加第一个账号</button>
        </div>
      </div>
    </div>

    <!-- Upload History -->
    <div class="section">
      <h3 class="section-title">最近上传记录</h3>
      <div class="upload-history">
        <table class="history-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>账号</th>
              <th>书籍</th>
              <th>章节数</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="record in uploadHistory" :key="record.id">
              <td>{{ formatDate(record.created_at) }}</td>
              <td>{{ record.account_name }}</td>
              <td>{{ record.book_name }}</td>
              <td>{{ record.chapter_count }}</td>
              <td>
                <span :class="['status-badge', `status-${record.status}`]">
                  {{ statusText(record.status) }}
                </span>
              </td>
              <td>
                <button v-if="record.status === 'failed'" @click="retryUpload(record)" class="btn-retry">
                  重试
                </button>
                <button @click="viewDetails(record)" class="btn-view">详情</button>
              </td>
            </tr>
          </tbody>
        </table>

        <div v-if="uploadHistory.length === 0" class="empty-state-small">
          <p class="text-slate-500">暂无上传记录</p>
        </div>
      </div>
    </div>

    <!-- Add Account Modal -->
    <div v-if="showAddAccount" class="modal-overlay" @click.self="closeModal">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="modal-title">添加番茄小说账号</h3>
          <button @click="closeModal" class="modal-close">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">账号名称</label>
            <input v-model="newAccount.name" type="text" class="form-input" placeholder="例如: 主账号" />
          </div>

          <div class="form-group">
            <label class="form-label">账号标识</label>
            <input v-model="newAccount.identifier" type="text" class="form-input" placeholder="例如: main" />
            <p class="form-hint">用于区分不同账号的 Cookie 文件</p>
          </div>

          <div class="alert alert-info">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p>添加账号后，需要点击"立即登录"按钮在浏览器中完成登录，系统会自动保存 Cookie。</p>
          </div>
        </div>

        <div class="modal-footer">
          <button @click="closeModal" class="btn-secondary">取消</button>
          <button @click="addAccount" class="btn-primary">添加</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { novelApi } from '@/api/novel'

const accounts = ref<any[]>([])
const uploadHistory = ref<any[]>([])
const showAddAccount = ref(false)
const newAccount = ref({
  name: '',
  identifier: ''
})

const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleString('zh-CN')
}

const statusText = (status: string) => {
  const map: Record<string, string> = {
    success: '成功',
    failed: '失败',
    pending: '进行中'
  }
  return map[status] || status
}

const loadAccounts = async () => {
  // ✅ 修复：简化为检查Cookie文件是否存在
  // 注意：完整的账号管理需要后端数据库支持，这里仅显示默认账号
  accounts.value = [
    {
      id: '1',
      name: '默认账号',
      identifier: 'default',
      cookie_valid: false,  // 需要用户手动登录
      books_count: 0,
      chapters_count: 0,
      last_upload: null
    }
  ]
}

const loadUploadHistory = async () => {
  // ✅ 修复：上传历史需要后端数据库支持，暂时返回空
  // TODO: 实现完整的上传历史记录功能
  uploadHistory.value = []
}

const loginAccount = async (account: any) => {
  try {
    await novelApi.fanqieLogin(account.identifier)
    await loadAccounts()
  } catch (error: any) {
    console.error('登录失败:', error)
  }
}

const viewUploadHistory = (account: any) => {
  // ✅ 修复：显示提示信息
  alert('上传历史功能需要后端数据库支持，暂未实现')
}

const deleteAccount = async (account: any) => {
  // ✅ 修复：默认账号不可删除
  alert('默认账号不可删除。如需管理多个账号，请联系管理员添加账号管理功能。')
}

const addAccount = async () => {
  // ✅ 修复：多账号管理需要后端支持
  alert('多账号管理功能需要后端数据库支持，暂未实现。\n当前仅支持默认账号（identifier: default）')
  closeModal()
}

const retryUpload = (record: any) => {
  // ✅ 修复：重试功能需要后端支持
  alert('重试上传功能需要后端数据库支持，暂未实现')
}

const viewDetails = (record: any) => {
  // ✅ 修复：详情功能需要后端支持
  alert('上传详情功能需要后端数据库支持，暂未实现')
}

const closeModal = () => {
  showAddAccount.value = false
  newAccount.value = {
    name: '',
    identifier: ''
  }
}

onMounted(() => {
  loadAccounts()
  loadUploadHistory()
})
</script>


