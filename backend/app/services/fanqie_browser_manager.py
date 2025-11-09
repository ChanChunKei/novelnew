"""番茄小说浏览器会话管理器

用于在多个API调用之间保持浏览器会话
"""
import logging
from typing import Optional, Dict
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


class FanqieBrowserManager:
    """番茄小说浏览器会话管理器（单例模式）"""
    
    _instance: Optional['FanqieBrowserManager'] = None
    _sessions: Dict[str, Dict[str, any]] = {}  # account -> {browser, context, page, playwright}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def get_or_create_session(self, account: str = "default", headless: bool = False):
        """获取或创建浏览器会话
        
        Args:
            account: 账号标识
            headless: 是否使用无头模式
            
        Returns:
            (browser, context, page, playwright) 元组
        """
        if account in self._sessions:
            session = self._sessions[account]
            # 检查会话是否仍然有效
            try:
                # 尝试获取页面URL来验证会话是否有效
                await session['page'].url
                logger.info(f"复用现有浏览器会话: {account}")
                return session['browser'], session['context'], session['page'], session['playwright']
            except Exception as e:
                logger.warning(f"现有会话无效，创建新会话: {e}")
                await self.close_session(account)
        
        # 创建新会话
        logger.info(f"创建新浏览器会话: {account}, headless={headless}")
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=headless)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        self._sessions[account] = {
            'browser': browser,
            'context': context,
            'page': page,
            'playwright': playwright
        }
        
        return browser, context, page, playwright
    
    async def close_session(self, account: str = "default"):
        """关闭指定账号的浏览器会话
        
        Args:
            account: 账号标识
        """
        if account not in self._sessions:
            return
        
        session = self._sessions[account]
        try:
            if session.get('page'):
                await session['page'].close()
            if session.get('context'):
                await session['context'].close()
            if session.get('browser'):
                await session['browser'].close()
            if session.get('playwright'):
                await session['playwright'].stop()
            logger.info(f"已关闭浏览器会话: {account}")
        except Exception as e:
            logger.error(f"关闭浏览器会话失败: {e}")
        finally:
            del self._sessions[account]
    
    async def close_all_sessions(self):
        """关闭所有浏览器会话"""
        accounts = list(self._sessions.keys())
        for account in accounts:
            await self.close_session(account)
        logger.info("已关闭所有浏览器会话")


# 全局浏览器管理器实例
browser_manager = FanqieBrowserManager()

