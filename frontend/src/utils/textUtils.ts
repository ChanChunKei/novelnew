/**
 * 文本处理工具函数
 * 用于处理章节内容的清理、格式转换等
 */

/**
 * 移除Markdown格式标记，保留纯文本内容
 * 用于：导出TXT、复制纯文本、字数统计、纯文本显示
 */
export function stripMarkdownFormatting(text: string): string {
  if (!text) return text

  let cleaned = text

  // 移除标题标记（##、###等），保留文本
  cleaned = cleaned.replace(/^#{1,6}\s+/gm, '')

  // 移除粗体标记 **text** 或 __text__
  cleaned = cleaned.replace(/\*\*(.+?)\*\*/g, '$1')
  cleaned = cleaned.replace(/__(.+?)__/g, '$1')

  // 移除斜体标记 *text* 或 _text_（要在粗体之后处理）
  cleaned = cleaned.replace(/\*(.+?)\*/g, '$1')
  cleaned = cleaned.replace(/(?<!\w)_(.+?)_(?!\w)/g, '$1')

  // 移除行内代码标记 `code`
  cleaned = cleaned.replace(/`(.+?)`/g, '$1')

  // 移除链接，保留文本 [text](url) -> text
  cleaned = cleaned.replace(/\[(.+?)\]\(.+?\)/g, '$1')

  // 移除图片 ![alt](url) -> alt
  cleaned = cleaned.replace(/!\[(.+?)\]\(.+?\)/g, '$1')

  // 移除引用标记 >
  cleaned = cleaned.replace(/^>\s+/gm, '')

  // 移除列表标记 - 或 * 或 数字.
  cleaned = cleaned.replace(/^[\*\-\+]\s+/gm, '')
  cleaned = cleaned.replace(/^\d+\.\s+/gm, '')

  // 移除Markdown硬换行：行尾的反斜杠+换行符
  cleaned = cleaned.replace(/\\\s*\n/g, '\n')

  return cleaned
}

/**
 * 规范化内容：解析JSON、处理转义字符、清理误用的Markdown硬换行
 * 用于：版本预览、详情显示、编辑器初始化等需要保留格式的场景
 */
export function normalizeContent(content: string): string {
  if (!content) return ''

  // 1. 尝试解析JSON（如果内容是嵌套的JSON）
  try {
    const parsed = JSON.parse(content)
    if (parsed && typeof parsed === 'object' && parsed.content) {
      content = parsed.content
    }
  } catch (error) {
    // not a json, continue
  }

  // 2. 处理转义字符
  let cleaned = content.replace(/^"|"$/g, '')
  cleaned = cleaned.replace(/\\n/g, '\n')
  cleaned = cleaned.replace(/\\"/g, '"')
  cleaned = cleaned.replace(/\\t/g, '\t')
  cleaned = cleaned.replace(/\\\\/g, '\\')

  // 3. 清理LLM误用的Markdown硬换行符
  // 移除行尾的反斜杠+换行符（Markdown硬换行的误用）
  cleaned = cleaned.replace(/\\\s*\n/g, '\n')
  // 移除只包含反斜杠的空行（用 \ 代替空行的误用）
  cleaned = cleaned.replace(/^\\\s*$/gm, '')

  return cleaned
}

/**
 * 转换为纯文本：在规范化基础上移除Markdown
 * 用于：导出TXT、复制纯文本、字数统计、纯文本最终显示
 */
export function toPlainText(content: string): string {
  const normalized = normalizeContent(content)
  return stripMarkdownFormatting(normalized)
}

/**
 * @deprecated 使用 toPlainText() 或 normalizeContent() 代替
 * 为了向后兼容保留，但建议使用更明确的函数名
 */
export function cleanVersionContent(content: string): string {
  return toPlainText(content)
}

/**
 * 清理文件名中的非法字符
 */
export function sanitizeFileName(name: string): string {
  return name.replace(/[\\/:*?"<>|]/g, '_')
}
