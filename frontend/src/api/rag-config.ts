import request from '@/api/base'

export interface SystemConfig {
    key: string
    value: string
    description?: string
    created_at?: string
    updated_at?: string
}

export interface GeminiRAGTestResult {
    success: boolean
    message: string
    api_key_configured: boolean
    api_key_valid: boolean
    provider: string
    corpus_accessible?: boolean
    error_detail?: string
}

export const ragConfigApi = {
    // 获取系统配置
    getSystemConfig: (key: string) => {
        return request.get(`/api/admin/system-configs/${key}`)
    },

    // 更新系统配置
    upsertSystemConfig: (key: string, value: string, description?: string) => {
        return request.put(`/api/admin/system-configs/${key}`, {
            value,
            description
        })
    },

    // 测试 Gemini RAG 连接
    testGeminiRag: (testProjectId?: string) => {
        return request.post('/api/admin/test-gemini-rag', {
            test_project_id: testProjectId
        })
    }
}
