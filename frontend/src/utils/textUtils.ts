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
 * 清理版本内容：解析JSON、处理转义字符、移除Markdown
 * 用于显示、导出、字数统计等场景
 */
export function cleanVersionContent(content: string): string {
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

  // 3. 清理Markdown格式标记（用于纯文本显示）
  cleaned = stripMarkdownFormatting(cleaned)

  return cleaned
}

/**
 * 清理文件名中的非法字符
 */
export function sanitizeFileName(name: string): string {
  return name.replace(/[\\/:*?"<>|]/g, '_')
}
