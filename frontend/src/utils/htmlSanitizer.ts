/**
 * HTML安全清理工具
 * 防止XSS攻击，清理用户输入的HTML内容
 */

/**
 * 基础HTML清理函数
 * 移除潜在危险的HTML标签和属性
 */
export function sanitizeHTML(dirty: string): string {
  if (!dirty) return ''
  
  // 创建临时DOM元素
  const temp = document.createElement('div')
  temp.textContent = dirty
  
  // 获取纯文本，自动转义HTML实体
  let clean = temp.innerHTML
  
  // 允许的安全HTML标签
  const allowedTags = [
    'p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li', 'blockquote', 'code', 'pre'
  ]
  
  // 移除不安全的标签，保留内容
  const dangerousTags = /<\/?(?!(?:\/?)(?:p|br|strong|em|u|h[1-6]|ul|ol|li|blockquote|code|pre)(?:\s|>))[^>]*>/gi
  clean = clean.replace(dangerousTags, '')
  
  // 移除危险属性
  clean = clean.replace(/\s*on\w+\s*=\s*["'][^"']*["']/gi, '') // 移除事件属性
  clean = clean.replace(/\s*javascript:\s*[^"'>\s]*/gi, '') // 移除javascript:
  clean = clean.replace(/\s*data:\s*[^"'>\s]*/gi, '') // 移除data:
  
  return clean
}

/**
 * 严格HTML清理 - 只保留纯文本
 * 用于高安全要求的场景
 */
export function sanitizeToText(dirty: string): string {
  if (!dirty) return ''
  
  const temp = document.createElement('div')
  temp.innerHTML = dirty
  return temp.textContent || temp.innerText || ''
}

/**
 * Markdown安全渲染
 * 清理Markdown渲染后的HTML
 */
export function sanitizeMarkdown(markdownHTML: string): string {
  if (!markdownHTML) return ''
  
  // 基础清理
  let clean = sanitizeHTML(markdownHTML)
  
  // 额外清理Markdown可能产生的内容
  clean = clean.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
  clean = clean.replace(/<iframe\b[^<]*(?:(?!<\/iframe>)<[^<]*)*<\/iframe>/gi, '')
  clean = clean.replace(/<object\b[^<]*(?:(?!<\/object>)<[^<]*)*<\/object>/gi, '')
  clean = clean.replace(/<embed\b[^<]*>/gi, '')
  clean = clean.replace(/<link\b[^<]*>/gi, '')
  clean = clean.replace(/<meta\b[^<]*>/gi, '')
  
  return clean
}

/**
 * 检查内容是否包含潜在危险
 */
export function isDangerous(content: string): boolean {
  if (!content) return false
  
  const dangerousPatterns = [
    /<script/i,
    /javascript:/i,
    /on\w+\s*=/i,
    /<iframe/i,
    /<object/i,
    /<embed/i,
    /data:\s*text\/html/i,
    /vbscript:/i
  ]
  
  return dangerousPatterns.some(pattern => pattern.test(content))
}

/**
 * 智能HTML清理
 * 根据内容类型选择合适的清理策略
 */
export function smartSanitize(content: string, contentType: 'markdown' | 'html' | 'text' = 'html'): string {
  if (!content) return ''
  
  // 检查是否包含危险内容
  if (isDangerous(content)) {
    console.warn('检测到潜在危险内容，强制转为纯文本', content.substring(0, 100))
    return sanitizeToText(content)
  }
  
  switch (contentType) {
    case 'markdown':
      return sanitizeMarkdown(content)
    case 'text':
      return sanitizeToText(content)
    case 'html':
    default:
      return sanitizeHTML(content)
  }
}