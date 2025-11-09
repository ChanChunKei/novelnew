/**
 * 日志工具
 *
 * 在开发环境输出日志，生产环境静默
 */

const isDevelopment = import.meta.env.DEV

export const logger = {
  /**
   * 调试日志 - 仅在开发环境输出
   */
  debug: (...args: any[]) => {
    if (isDevelopment) {
      console.log('[DEBUG]', ...args)
    }
  },

  /**
   * 信息日志
   */
  info: (...args: any[]) => {
    if (isDevelopment) {
      console.info('[INFO]', ...args)
    }
  },

  /**
   * 警告日志 - 所有环境都输出
   */
  warn: (...args: any[]) => {
    console.warn('[WARN]', ...args)
  },

  /**
   * 错误日志 - 所有环境都输出
   */
  error: (...args: any[]) => {
    console.error('[ERROR]', ...args)
  },
}

export default logger
