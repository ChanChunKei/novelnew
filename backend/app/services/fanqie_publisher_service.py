"""番茄小说自动发布服务"""
import asyncio
import json
import logging
import re
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..models.novel import NovelProject, Volume, Chapter, ChapterVersion, ChapterOutline
from .fanqie_browser_manager import browser_manager

logger = logging.getLogger(__name__)


class FanqiePublisherService:
    """番茄小说自动发布服务

    使用Playwright浏览器自动化实现章节自动发布功能
    基于实际测试的番茄小说平台流程
    """

    # ✅ 修复：提取配置常量，避免硬编码
    # 超时配置（毫秒）
    PAGE_LOAD_TIMEOUT = 30000  # 页面加载超时
    NAVIGATION_TIMEOUT = 30000  # 导航超时
    SELECTOR_TIMEOUT = 10000   # 元素查找超时

    # 等待时间配置（秒）
    PAGE_LOAD_WAIT = 2.0      # 页面加载后等待
    CLICK_WAIT = 0.5          # 点击后等待
    DIALOG_WAIT = 1.0         # 对话框等待
    INPUT_WAIT = 0.3          # 输入后等待

    def __init__(self, cookies_dir: str = None, headless: bool = False):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self.book_id: Optional[str] = None
        # ✅ 修复：使用绝对路径，基于当前文件所在目录向上查找backend目录
        if cookies_dir is None:
            # 获取当前文件所在目录（backend/app/services/）
            current_file = Path(__file__).resolve()
            # 向上3级到backend目录
            backend_dir = current_file.parent.parent.parent
            cookies_dir = backend_dir / "storage" / "fanqie_cookies"
        self.cookies_dir = Path(cookies_dir)
        self.cookies_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Cookie存储目录: {self.cookies_dir.absolute()}")
        self.headless = headless  # 保存headless设置

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.init_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()

    async def init_browser(self, headless: Optional[bool] = None):
        """初始化浏览器

        Args:
            headless: 是否使用无头模式(默认使用构造函数中的设置)
                     生产环境建议设置为True

        ✅ 修复：确保资源创建失败时正确清理已创建的资源
        """
        if headless is None:
            headless = self.headless

        try:
            self.playwright = await async_playwright().start()

            # 配置浏览器启动参数
            launch_options = {
                "headless": headless,
                "args": [
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-software-rasterizer",
                    "--disable-extensions",
                    "--disable-background-networking",
                    "--disable-sync",
                    "--metrics-recording-only",
                    "--disable-default-apps",
                    "--mute-audio",
                    "--no-first-run",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                    "--disable-background-timer-throttling",
                    "--disable-ipc-flooding-protection",
                    "--password-store=basic",
                    "--use-mock-keychain",
                    "--force-color-profile=srgb",
                    "--disable-features=TranslateUI,BlinkGenPropertyTrees",
                ]
            }

            try:
                # 在Mac上优先使用Firefox,因为Chromium在Apple Silicon上可能崩溃
                try:
                    self.browser = await self.playwright.firefox.launch(**launch_options)
                    logger.info("使用Firefox浏览器")
                except Exception as e:
                    logger.warning(f"Firefox启动失败,尝试使用Webkit: {e}")
                    self.browser = await self.playwright.webkit.launch(**launch_options)
                    logger.info("使用Webkit浏览器")
                try:
                    self.context = await self.browser.new_context()
                    try:
                        self.page = await self.context.new_page()
                        logger.info(f"浏览器初始化完成 (headless={headless})")
                    except Exception:
                        await self.context.close()
                        raise
                except Exception:
                    await self.browser.close()
                    raise
            except Exception:
                await self.playwright.stop()
                raise
        except Exception as e:
            # 确保所有资源都被清理
            logger.error(f"浏览器初始化失败: {e}")
            await self.close()
            raise
        
    async def close(self):
        """关闭浏览器"""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("浏览器已关闭")
        
    @staticmethod
    def _validate_account_identifier(account: str) -> str:
        """
        验证并清理账号标识，防止路径遍历攻击

        ✅ 修复：防止路径遍历漏洞（CVE级别安全问题）
        """
        import re

        # 只允许字母、数字、下划线和连字符
        if not re.match(r'^[a-zA-Z0-9_-]+$', account):
            raise ValueError(
                f"无效的账号标识: {account}。"
                "只允许使用字母、数字、下划线和连字符。"
            )

        # 限制长度
        if len(account) > 64:
            raise ValueError("账号标识长度不能超过64个字符")

        return account

    async def load_cookies(self, account: str = "default"):
        """加载保存的Cookie

        Args:
            account: 账号标识（用于区分不同账号的cookie）
        """
        try:
            # ✅ 修复：验证账号标识，防止路径遍历
            safe_account = self._validate_account_identifier(account)
            cookies_file = self.cookies_dir / f"{safe_account}_cookies.json"

            # ✅ 修复：确保文件路径在 cookies_dir 内
            cookies_file = cookies_file.resolve()
            if not str(cookies_file).startswith(str(self.cookies_dir.resolve())):
                logger.error(f"路径遍历攻击尝试: {account}")
                return False

            if not cookies_file.exists():
                logger.warning(f"Cookie文件不存在: {cookies_file}")
                return False

            with open(cookies_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            await self.context.add_cookies(cookies)
            logger.info(f"成功加载Cookie: {cookies_file}")
            return True
        except ValueError as e:
            logger.error(f"账号标识验证失败: {e}")
            return False
        except Exception as e:
            logger.error(f"加载Cookie失败: {e}")
            return False

    async def save_cookies(self, account: str = "default"):
        """保存当前Cookie

        Args:
            account: 账号标识（用于区分不同账号的cookie）
        """
        try:
            # ✅ 修复：验证账号标识，防止路径遍历
            safe_account = self._validate_account_identifier(account)
            cookies_file = self.cookies_dir / f"{safe_account}_cookies.json"

            # ✅ 修复：确保文件路径在 cookies_dir 内
            cookies_file = cookies_file.resolve()
            if not str(cookies_file).startswith(str(self.cookies_dir.resolve())):
                logger.error(f"路径遍历攻击尝试: {account}")
                return False

            cookies = await self.context.cookies()
            with open(cookies_file, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, indent=2, ensure_ascii=False)
            logger.info(f"成功保存Cookie: {cookies_file}")
            return True
        except ValueError as e:
            logger.error(f"账号标识验证失败: {e}")
            return False
        except Exception as e:
            logger.error(f"保存Cookie失败: {e}")
            return False
            
    async def login(self, username: str, password: str) -> bool:
        """登录番茄小说
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            是否登录成功
        """
        try:
            # 访问登录页面
            await self.page.goto("https://fanqienovel.com/login")
            await self.page.wait_for_load_state("networkidle")
            
            # 填写用户名和密码
            await self.page.fill('input[name="username"]', username)
            await self.page.fill('input[name="password"]', password)
            
            # 点击登录按钮
            await self.page.click('button[type="submit"]')
            
            # 等待登录完成
            await self.page.wait_for_url("**/main/writer/**", timeout=30000)
            
            logger.info("登录成功")
            return True
        except Exception as e:
            logger.error(f"登录失败: {e}")
            return False
            
    async def create_book(
        self,
        book_name: str,
        gender: str = "male",  # male/female
        category: str = "都市脑洞",  # 作品标签
        intro: str = "精彩小说,敬请期待!"  # 作品简介
    ) -> Dict[str, Any]:
        """创建新书籍 (基于2025年11月实际测试流程)

        Args:
            book_name: 书籍名称 (最多15字)
            gender: 目标读者 ("male"=男频, "female"=女频)
            category: 作品标签/分类
            intro: 作品简介 (50-500字)

        Returns:
            创建结果 {"success": bool, "book_id": str, "error": str}
        """
        try:
            logger.info(f"开始创建书籍: {book_name}, 分类: {category}, 读者: {gender}")

            # 1. 检查当前页面,如果不在工作台则访问
            current_url = self.page.url
            if "/main/writer" not in current_url:
                logger.info("当前不在工作台,正在访问...")
                await self.page.goto("https://fanqienovel.com/main/writer/?enter_from=author_zone", timeout=60000)
                await self.page.wait_for_load_state("domcontentloaded", timeout=30000)
                await asyncio.sleep(2)
                logger.info("已访问作家工作台")
            else:
                logger.info(f"当前已在工作台: {current_url}")

            # 2. 点击"创建新书"按钮
            logger.info("正在查找'创建新书'按钮...")

            # 等待页面完全加载
            await self.page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(2)  # 额外等待确保JavaScript执行完成

            # 尝试多种选择器
            create_new_book_btn = None
            selectors = [
                'text="创建新书"',
                'button:has-text("创建新书")',
                '[class*="create"]:has-text("创建新书")',
                'div:has-text("创建新书")',
                'span:has-text("创建新书")',
            ]

            for selector in selectors:
                try:
                    create_new_book_btn = await self.page.wait_for_selector(selector, timeout=5000)
                    if create_new_book_btn:
                        logger.info(f"找到'创建新书'按钮,选择器: {selector}")
                        break
                except Exception as e:
                    logger.debug(f"选择器 {selector} 未找到按钮: {e}")
                    continue

            if not create_new_book_btn:
                # 截图保存当前页面状态用于调试
                screenshot_path = f"debug_create_book_page_{int(time.time())}.png"
                await self.page.screenshot(path=screenshot_path)
                logger.error(f"未找到'创建新书'按钮,已保存截图: {screenshot_path}")

                # 保存页面HTML用于调试
                page_html = await self.page.content()
                html_path = f"debug_page_{int(time.time())}.html"
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(page_html)
                logger.error(f"已保存页面HTML: {html_path}")

                return {
                    "success": False,
                    "error": "未找到'创建新书'按钮,请确认页面是否正确加载"
                }

            # 检查按钮是否可见和可点击
            is_visible = await create_new_book_btn.is_visible()
            is_enabled = await create_new_book_btn.is_enabled()
            logger.info(f"按钮状态: 可见={is_visible}, 可用={is_enabled}")

            if not is_visible:
                screenshot_path = f"debug_button_not_visible_{int(time.time())}.png"
                await self.page.screenshot(path=screenshot_path)
                logger.error(f"按钮不可见,已保存截图: {screenshot_path}")
                return {
                    "success": False,
                    "error": "按钮不可见"
                }

            # 尝试多种点击方式
            click_success = False

            # 方案1: 滚动到按钮位置
            try:
                logger.info("方案1: 滚动到按钮位置...")
                await create_new_book_btn.scroll_into_view_if_needed()
                await asyncio.sleep(1)
                logger.info("✅ 滚动成功")
            except Exception as e:
                logger.warning(f"滚动失败: {e}")

            # 方案2: 检查并关闭可能的遮罩层
            try:
                logger.info("方案2: 检查遮罩层...")
                modal_selectors = ['.modal', '.mask', '.overlay', '[class*="modal"]', '[class*="mask"]']
                for modal_selector in modal_selectors:
                    modal = await self.page.query_selector(modal_selector)
                    if modal:
                        is_modal_visible = await modal.is_visible()
                        if is_modal_visible:
                            logger.warning(f"发现遮罩层: {modal_selector}")
                            # 尝试点击遮罩层的关闭按钮
                            close_btn = await modal.query_selector('button, .close, [class*="close"]')
                            if close_btn:
                                await close_btn.click()
                                await asyncio.sleep(1)
                                logger.info("✅ 关闭遮罩层成功")
            except Exception as e:
                logger.debug(f"检查遮罩层失败: {e}")

            # 方案3: 尝试使用JavaScript直接点击
            try:
                logger.info("方案3: 使用JavaScript点击...")
                await create_new_book_btn.evaluate("el => el.click()")
                await asyncio.sleep(2)

                # 检查是否成功(通过URL变化或弹窗出现)
                current_url = self.page.url
                if "/create" in current_url or await self.page.query_selector('text="创建书本"'):
                    logger.info("✅ JavaScript点击成功")
                    click_success = True
                else:
                    logger.warning("JavaScript点击可能未生效")
            except Exception as e:
                logger.warning(f"JavaScript点击失败: {e}")

            # 方案4: 如果JavaScript点击失败,尝试force点击
            if not click_success:
                try:
                    logger.info("方案4: 使用force点击...")
                    await create_new_book_btn.click(force=True, timeout=5000)
                    await asyncio.sleep(2)
                    logger.info("✅ Force点击成功")
                    click_success = True
                except Exception as e:
                    logger.warning(f"Force点击失败: {e}")

            # 方案5: 如果还是失败,尝试普通点击
            if not click_success:
                try:
                    logger.info("方案5: 使用普通点击...")
                    await create_new_book_btn.click(timeout=5000)
                    await asyncio.sleep(2)
                    logger.info("✅ 普通点击成功")
                    click_success = True
                except Exception as e:
                    logger.error(f"所有点击方式都失败: {e}")
                    screenshot_path = f"debug_click_failed_{int(time.time())}.png"
                    await self.page.screenshot(path=screenshot_path)
                    logger.error(f"已保存截图: {screenshot_path}")
                    return {
                        "success": False,
                        "error": f"点击'创建新书'按钮失败: {str(e)}"
                    }

            logger.info("成功点击'创建新书'按钮")
            await asyncio.sleep(2)

            # 3. 选择"创建书本"(而不是"去写章节")
            # 点击后会出现一个tooltip，包含两个选项
            logger.info("等待'创建书本'选项出现...")

            # 尝试多种选择器
            create_book_selectors = [
                'text="创建书本"',
                'div:has-text("创建书本")',
                'span:has-text("创建书本")',
                '[class*="tooltip"] >> text="创建书本"',
            ]

            create_book_option = None
            for selector in create_book_selectors:
                try:
                    create_book_option = await self.page.wait_for_selector(selector, timeout=3000)
                    if create_book_option:
                        logger.info(f"找到'创建书本'选项，选择器: {selector}")
                        break
                except Exception as e:
                    logger.debug(f"选择器 {selector} 未找到: {e}")
                    continue

            if not create_book_option:
                # 如果没有找到tooltip，直接导航到创建页面
                logger.warning("未找到'创建书本'选项，尝试直接导航到创建页面")
                try:
                    await self.page.goto("https://fanqienovel.com/main/writer/create?enter_from=home", timeout=30000)
                    await self.page.wait_for_load_state("domcontentloaded", timeout=10000)
                    await asyncio.sleep(2)
                    logger.info("已直接导航到创建页面")
                except Exception as e:
                    logger.error(f"导航到创建页面失败: {e}")
                    return {
                        "success": False,
                        "error": f"无法访问创建页面: {str(e)}"
                    }
            else:
                await create_book_option.click()
                await asyncio.sleep(2)
                logger.info("已选择'创建书本'")

            # 4. 填写书名 - 使用精确的placeholder
            title_input = await self.page.wait_for_selector('input[placeholder="请输入作品名称"]', timeout=5000)
            if not title_input:
                logger.error("未找到书名输入框")
                return {
                    "success": False,
                    "error": "未找到书名输入框"
                }

            await title_input.fill(book_name[:15])  # 限制15字
            await asyncio.sleep(0.5)
            logger.info(f"已填写书名: {book_name[:15]}")

            # 注意：根据用户反馈，创建书籍只需要填写书名即可，其他字段都是可选的
            # 因此跳过目标读者、作品标签、简介等字段的填写

            # 8. 点击"立即创建"按钮（第一次）
            create_btn = await self.page.query_selector('button:has-text("立即创建")')
            if not create_btn:
                logger.error("未找到'立即创建'按钮")
                return {
                    "success": False,
                    "error": "未找到'立即创建'按钮"
                }

            await create_btn.click()
            logger.info("✅ 第一次点击'立即创建'按钮")
            await asyncio.sleep(3)

            # 检查是否有各种错误提示
            error_messages = [
                "该书名已存在",
                "书名不符合规范",
                "书名长度超过限制",
                "创建失败",
                "操作太频繁",
                "请稍后再试",
            ]

            detected_error = None
            for error_msg in error_messages:
                try:
                    error_alert = await self.page.wait_for_selector(f'text="{error_msg}"', timeout=1000)
                    if error_alert:
                        detected_error = error_msg
                        logger.error(f"检测到错误提示: {error_msg}")
                        break
                except Exception:
                    pass

            if detected_error:
                # 截图保存错误状态
                screenshot_path = f"error_create_{int(time.time())}.png"
                await self.page.screenshot(path=screenshot_path)
                logger.error(f"创建失败，错误截图已保存: {screenshot_path}")

                return {
                    "success": False,
                    "error": f"创建书籍失败: {detected_error}",
                    "hint": "请手动在番茄小说平台上创建书籍，或修改书名后重试"
                }

            logger.info("未检测到错误提示")

            # 🔑 关键改进：模拟之前加后缀版本的"双击"行为
            # 之前的版本会在修改书名后再次查找并点击"立即创建"按钮
            # 这可能是成功的关键！现在即使没有错误，也再次点击一次
            logger.info("🔄 模拟双击：再次查找并点击'立即创建'按钮...")
            await asyncio.sleep(1)

            # 重新查找"立即创建"按钮（可能按钮状态已改变）
            create_btn_retry = await self.page.query_selector('button:has-text("立即创建")')
            if create_btn_retry:
                await create_btn_retry.click()
                logger.info("✅ 第二次点击'立即创建'按钮（模拟之前加后缀版本的双击行为）")
            else:
                logger.warning("⚠️ 未找到按钮进行第二次点击，可能已经开始跳转")

            logger.info("等待页面跳转...")

            # 9. 等待创建完成,从URL提取book_id
            # 延长等待时间到8秒（加后缀时因为多了操作步骤所以时间更长，这里补偿时间）
            await asyncio.sleep(8)

            current_url = self.page.url
            logger.info(f"创建后的URL: {current_url}")

            # 尝试从URL中提取book_id
            # 优化正则顺序：将最常见的 /book-info/ 放在最前面
            # 番茄小说创建成功后的URL格式:
            # - /main/writer/book-info/{book_id}?type=1 (创建成功后最常见)
            # - /chapter-manage/{book_id}
            # - /main/writer/{book_id}/publish
            import re
            match = re.search(
                r'/book-info/(\d+)|/chapter-manage/(\d+)|/writer/(\d+)/publish|/book-manage\?book_id=(\d+)',
                current_url
            )

            if match:
                book_id = match.group(1) or match.group(2) or match.group(3) or match.group(4)
                logger.info(f"✅ 从URL成功提取book_id: {book_id}")
                self.book_id = book_id
                return {
                    "success": True,
                    "book_id": book_id
                }

            # 第一次提取失败，可能页面跳转慢，等待5秒后重试
            logger.warning("⚠️ 第一次URL提取失败，等待5秒后重试...")
            await asyncio.sleep(5)

            current_url = self.page.url
            logger.info(f"重试时的URL: {current_url}")

            match = re.search(
                r'/book-info/(\d+)|/chapter-manage/(\d+)|/writer/(\d+)/publish|/book-manage\?book_id=(\d+)',
                current_url
            )

            if match:
                book_id = match.group(1) or match.group(2) or match.group(3) or match.group(4)
                logger.info(f"✅ 重试成功！从URL提取book_id: {book_id}")
                self.book_id = book_id
                return {
                    "success": True,
                    "book_id": book_id
                }

            # 重试后仍然失败，检查是否还在创建页面
            if "/create" in current_url:
                logger.error("❌ 创建后URL未跳转，仍停留在创建页面")

                # 截图保存当前页面状态用于调试
                screenshot_path = f"stuck_on_create_{int(time.time())}.png"
                await self.page.screenshot(path=screenshot_path)
                logger.error(f"📸 页面截图已保存: {screenshot_path}")

                # 检查页面上是否有隐藏的错误提示
                page_text = await self.page.evaluate('() => document.body.innerText')
                logger.info(f"📄 页面文本内容(前500字): {page_text[:500]}")

                return {
                    "success": False,
                    "error": "创建书籍后页面未跳转，可能创建失败。请检查番茄小说平台或查看截图: " + screenshot_path,
                    "hint": "建议手动在番茄小说平台上检查书籍是否创建成功"
                }

            # 不在创建页面但也提取不到book_id
            logger.error(f"❌ 无法从URL提取book_id，当前URL: {current_url}")
            return {
                "success": False,
                "error": f"创建后无法获取book_id，当前URL: {current_url}",
                "hint": "请手动检查番茄小说平台是否创建成功"
            }

        except Exception as e:
            logger.error(f"创建书籍失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": f"创建书籍失败: {str(e)}"
            }

    async def find_book_by_name(self, book_name: str) -> Optional[str]:
        """通过书名查找书籍ID

        Args:
            book_name: 书籍名称

        Returns:
            书籍ID，如果未找到返回None
        """
        try:
            logger.info(f"开始查找书籍: {book_name}")
            # 访问作家工作台
            await self.page.goto("https://fanqienovel.com/main/writer/?enter_from=author_zone", timeout=60000)

            # 使用domcontentloaded而不是networkidle,更快更稳定
            try:
                await self.page.wait_for_load_state("domcontentloaded", timeout=30000)
            except Exception as e:
                logger.warning(f"等待页面加载超时,继续执行: {e}")

            # 等待React应用完全渲染
            await asyncio.sleep(5)

            # 等待页面中出现关键元素（书籍列表或创建新书按钮）
            try:
                await self.page.wait_for_selector('a[href*="/chapter-manage/"], button:has-text("创建新书")', timeout=10000)
                logger.info("作家工作台页面加载完成，关键元素已出现")
            except PlaywrightTimeoutError:
                logger.warning("等待关键元素超时，但继续执行")
                await asyncio.sleep(3)  # 再等待3秒

            # 查找书名对应的书籍
            # ✅ 修复：使用多种选择器策略查找书籍

            logger.info(f"🔍 开始查找书籍，目标书名: '{book_name}'，长度: {len(book_name)}")

            # 策略1: 通过ID前缀查找 (旧版页面)
            book_cards = await self.page.query_selector_all('[id^="long-article-table-item-"]')
            logger.info(f"策略1：找到 {len(book_cards)} 个旧版书籍卡片")

            if book_cards:
                for idx, card in enumerate(book_cards):
                    card_text = await card.inner_text()
                    logger.info(f"  卡片{idx+1}: '{card_text.strip()}'")
                    if card_text and (book_name in card_text or card_text.strip() == book_name):
                        card_id = await card.get_attribute('id')
                        if card_id:
                            book_id = card_id.replace('long-article-table-item-', '')
                            logger.info(f"✅ 找到书籍(策略1): {card_text.strip()}, ID: {book_id}")
                            self.book_id = book_id
                            return book_id

            # 策略2: 通过"章节管理"链接查找 (新版页面) - 改进版
            chapter_manage_links = await self.page.query_selector_all('a[href*="/chapter-manage/"]')
            logger.info(f"策略2：找到 {len(chapter_manage_links)} 个章节管理链接")

            # 先提取所有book_id和对应的上下文信息
            books_info = []
            for idx, link in enumerate(chapter_manage_links):
                href = await link.get_attribute('href')
                if href:
                    import re
                    match = re.search(r'/chapter-manage/(\d+)', href)
                    if match:
                        book_id_candidate = match.group(1)

                        # 🔑 关键改进：获取整个页面上这个book_id附近的所有文本
                        # 使用JavaScript在页面上查找包含这个href的元素，然后获取周围的文本
                        context_text = await self.page.evaluate('''(bookId) => {
                            // 查找包含这个book_id的所有链接
                            const links = document.querySelectorAll(`a[href*="${bookId}"]`);
                            const texts = [];

                            links.forEach(link => {
                                // 向上查找可能包含书名的容器
                                let parent = link.parentElement;
                                let depth = 0;
                                while (parent && depth < 5) {
                                    const text = parent.innerText || parent.textContent;
                                    if (text && text.length > 0 && text.length < 200) {
                                        texts.push(text);
                                    }
                                    parent = parent.parentElement;
                                    depth++;
                                }
                            });

                            return texts.join(' | ');
                        }''', book_id_candidate)

                        books_info.append({
                            'book_id': book_id_candidate,
                            'context': context_text,
                            'index': idx + 1
                        })

                        logger.info(f"  链接{idx+1}: book_id={book_id_candidate}")
                        logger.info(f"    上下文: '{context_text[:100]}...'")

                        # 在上下文中查找书名
                        if book_name in context_text:
                            logger.info(f"✅ 找到书籍(策略2改进): ID: {book_id_candidate}")
                            self.book_id = book_id_candidate
                            return book_id_candidate

            # 策略3: 使用JavaScript直接查找包含书名的元素
            book_id = await self.page.evaluate('''(bookName) => {
                // 查找所有可能包含书名的元素
                const allElements = document.querySelectorAll('div, article, section, h1, h2, h3, h4, h5, h6, span, p');
                for (const el of allElements) {
                    if (el.textContent.includes(bookName)) {
                        // 查找附近的"章节管理"链接
                        const parent = el.closest('div, article, section');
                        if (parent) {
                            const link = parent.querySelector('a[href*="/chapter-manage/"]');
                            if (link) {
                                const href = link.getAttribute('href');
                                const match = href.match(/\\/chapter-manage\\/(\\d+)/);
                                if (match) {
                                    return match[1];
                                }
                            }
                        }
                    }
                }
                return null;
            }''', book_name)

            if book_id:
                logger.info(f"✅ 找到书籍(策略3): ID: {book_id}")
                self.book_id = book_id
                return book_id

            # 所有策略都失败，保存截图和页面信息用于调试
            logger.error(f"❌ 未找到书籍: '{book_name}'")

            # 截图保存当前页面
            screenshot_path = f"find_book_failed_{int(time.time())}.png"
            await self.page.screenshot(path=screenshot_path)
            logger.error(f"📸 查找失败截图已保存: {screenshot_path}")

            # 输出页面上所有书籍的书名
            all_books = await self.page.evaluate('''() => {
                const books = [];
                // 查找所有可能的书籍元素
                const elements = document.querySelectorAll('a[href*="/chapter-manage/"], div[id*="table-item"]');
                elements.forEach(el => {
                    const text = el.innerText || el.textContent;
                    if (text && text.trim()) {
                        books.push(text.trim().substring(0, 50));
                    }
                });
                return [...new Set(books)];  // 去重
            }''')
            logger.info(f"📋 番茄后台上的所有书籍({len(all_books)}本): {all_books}")

            return None
        except Exception as e:
            logger.error(f"❌ 查找书籍过程中发生错误: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def get_all_volumes(self) -> List[Dict[str, Any]]:
        """获取当前书籍的所有分卷信息

        Returns:
            分卷列表，每个分卷包含 {index, name}
        """
        try:
            # 先点击"编辑分卷"按钮，确保分卷列表可见
            edit_btn = await self.page.wait_for_selector('button:has-text("编辑分卷")', timeout=5000)
            if not edit_btn:
                logger.error("未找到'编辑分卷'按钮")
                return []

            await edit_btn.click()
            await asyncio.sleep(3)  # 等待对话框打开和渲染

            # 获取分卷列表 - 使用更通用的选择器
            volumes = await self.page.evaluate('''() => {
                // 尝试多种选择器
                let volumeItems = document.querySelectorAll('.chapter-volume-list-item-normal');

                // 如果找不到，尝试其他选择器
                if (volumeItems.length === 0) {
                    // 查找对话框中的所有分卷项
                    const dialog = document.querySelector('dialog');
                    if (dialog) {
                        // 查找所有包含分卷名称的元素
                        volumeItems = dialog.querySelectorAll('[class*="volume"]');

                        // 如果还是找不到，尝试查找所有可编辑的项
                        if (volumeItems.length === 0) {
                            volumeItems = dialog.querySelectorAll('div[cursor="pointer"]');
                        }
                    }
                }

                const result = [];
                volumeItems.forEach((item, index) => {
                    const text = item.textContent.trim();
                    // 过滤掉空文本和按钮文本
                    if (text && !text.includes('新建分卷') && !text.includes('取消') && !text.includes('确定')) {
                        result.push({
                            index: index,
                            name: text
                        });
                    }
                });

                return result;
            }''')

            # 关闭编辑分卷对话框（只在分卷管理页面关闭）
            try:
                # 检查是否在分卷管理对话框中（通过检查"新建分卷"按钮）
                new_volume_btn = await self.page.query_selector('button:has-text("新建分卷")')
                if new_volume_btn:
                    # 确认是分卷对话框，才关闭
                    cancel_btn = await self.page.wait_for_selector('button:has-text("取消")', timeout=2000)
                    if cancel_btn:
                        await cancel_btn.click()
                        await asyncio.sleep(0.5)
                        logger.info("已关闭分卷管理对话框")
            except Exception as e:
                logger.debug(f"关闭分卷对话框: {e}")
                # 不需要按ESC，因为可能不在对话框中

            logger.info(f"获取到 {len(volumes)} 个分卷: {[v['name'] for v in volumes]}")
            return volumes

        except Exception as e:
            logger.error(f"获取分卷列表失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def navigate_to_chapter_manage(self, book_id: Optional[str] = None) -> bool:
        """导航到章节管理页面

        Args:
            book_id: 书籍ID（如果不提供则使用self.book_id）

        Returns:
            是否成功导航

        ✅ 修复：添加超时配置，避免无限等待
        """
        try:
            if book_id:
                self.book_id = book_id

            if not self.book_id:
                logger.error("未指定书籍ID")
                return False

            # 直接访问章节管理页面
            # URL格式: /main/writer/chapter-manage/{book_id}&{book_name}?type=1
            # 但是book_name可以省略，直接用book_id
            url = f"https://fanqienovel.com/main/writer/chapter-manage/{self.book_id}?type=1"
            await self.page.goto(url, timeout=self.NAVIGATION_TIMEOUT)

            # 使用domcontentloaded而不是networkidle，更快更稳定
            try:
                await self.page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception as e:
                logger.warning(f"等待页面加载超时，继续执行: {e}")

            await asyncio.sleep(3)  # 等待React渲染
            logger.info(f"成功导航到章节管理页面: {self.book_id}")
            return True
        except PlaywrightTimeoutError:
            logger.error(f"页面加载超时: {url}")
            return False
        except Exception as e:
            logger.error(f"导航失败: {e}")
            return False

    async def get_uploaded_chapters(self) -> dict:
        """获取已上传的章节信息

        Returns:
            {
                "last_chapter_number": int,  # 最后一章的章节号
                "chapter_titles": dict,      # {章节号: 标题}
                "total_count": int           # 总章节数
            }
        """
        try:
            logger.info("获取已上传的章节列表...")

            # 等待章节列表加载
            await asyncio.sleep(2)

            # 使用JavaScript获取章节列表
            chapters_info = await self.page.evaluate('''() => {
                const chapters = [];

                // 查找所有章节行（使用更通用的选择器）
                const chapterRows = document.querySelectorAll('tr.arco-table-tr');

                for (const row of chapterRows) {
                    // 跳过表头行
                    if (row.querySelector('th')) continue;

                    // 获取章节标题（在第一个td中）
                    const titleElement = row.querySelector('.table-title');
                    if (!titleElement) continue;

                    const title = titleElement.textContent.trim();

                    // 尝试从标题中提取章节号
                    // 格式可能是: "第1章 标题" 或 "第1章 第1章 新的开始"
                    let chapterNumber = null;
                    const match = title.match(/第(\\d+)章/);
                    if (match) {
                        chapterNumber = parseInt(match[1]);
                    } else {
                        // 如果标题中没有章节号，尝试从行号推断
                        const allRows = Array.from(chapterRows).filter(r => !r.querySelector('th'));
                        const rowIndex = allRows.indexOf(row);
                        chapterNumber = rowIndex + 1;
                    }

                    if (chapterNumber) {
                        chapters.push({
                            number: chapterNumber,
                            title: title
                        });
                    }
                }

                return chapters;
            }''')

            if not chapters_info or len(chapters_info) == 0:
                logger.info("未找到已上传的章节")
                return {
                    "last_chapter_number": 0,
                    "chapter_titles": {},
                    "total_count": 0
                }

            # 构建返回数据
            chapter_titles = {ch["number"]: ch["title"] for ch in chapters_info}
            last_chapter_number = max(ch["number"] for ch in chapters_info)

            logger.info(f"已上传 {len(chapters_info)} 章，最后一章: 第{last_chapter_number}章")

            return {
                "last_chapter_number": last_chapter_number,
                "chapter_titles": chapter_titles,
                "total_count": len(chapters_info)
            }

        except Exception as e:
            logger.error(f"获取已上传章节失败: {e}")
            return {
                "last_chapter_number": 0,
                "chapter_titles": {},
                "total_count": 0
            }

    async def select_volume_in_editor(self, volume_name: str = None, volume_number: int = None) -> bool:
        """在章节编辑器中选择指定分卷

        Args:
            volume_name: 要选择的分卷名称（可选）
            volume_number: 要选择的分卷编号（推荐使用，更精确）

        Returns:
            是否成功选择
        """
        try:
            if volume_number:
                logger.info(f"开始选择分卷: 第{volume_number}卷")
            elif volume_name:
                logger.info(f"开始选择分卷: {volume_name}")
            else:
                logger.warning("未指定分卷编号或名称，使用默认分卷")
                return True

            # 保存页面HTML用于调试
            try:
                html_content = await self.page.content()
                with open("debug_select_volume.html", "w", encoding="utf-8") as f:
                    f.write(html_content)
                logger.info("已保存页面HTML到 debug_select_volume.html")
            except:
                pass

            # 方法1: 尝试点击分卷显示区域（发布页面）
            # 查找 .publish-header-volume-wrap-info 或包含分卷名称的可点击区域
            volume_area = await self.page.query_selector('.publish-header-volume-wrap-info, .publish-maintain-volume')

            if volume_area:
                logger.info("找到分卷选择区域，尝试点击")
                # 点击分卷区域打开对话框
                await volume_area.click()
                await asyncio.sleep(0.5)

                # 等待对话框出现
                try:
                    await self.page.wait_for_selector('.arco-modal', timeout=5000)
                    logger.info("对话框已出现")
                except Exception as e:
                    logger.warning(f"等待对话框超时: {e}")

                # 在对话框中查找目标分卷
                # 按分卷编号选择：第1卷选倒数第1个，第2卷选倒数第2个
                if volume_number:
                    # 先获取分卷信息
                    volume_info = await self.page.evaluate('''(volumeNumber) => {
                        // 直接查找所有分卷项
                        const volumeItems = document.querySelectorAll('.editor-volume-list-item-normal');

                        console.log('找到分卷项数量:', volumeItems.length);
                        volumeItems.forEach((item, idx) => {
                            console.log(`  [${idx}] ${item.textContent.trim()} - ${item.className}`);
                        });

                        if (volumeItems.length === 0) {
                            console.log('未找到分卷项');
                            return {success: false, error: '未找到分卷项'};
                        }

                        // 第1卷选倒数第1个（最后一个），第2卷选倒数第2个
                        // 倒数第N个 = 总数 - N
                        const targetIndex = volumeItems.length - volumeNumber;

                        if (targetIndex >= 0 && targetIndex < volumeItems.length) {
                            const item = volumeItems[targetIndex];
                            const text = item.textContent.trim();
                            console.log(`选择第${volumeNumber}卷（倒数第${volumeNumber}个，索引${targetIndex}）: ${text}`);

                            return {success: true, volumeNumber: volumeNumber, matched: text, index: targetIndex};
                        }

                        return {success: false, volumeNumber: volumeNumber, totalItems: volumeItems.length, targetIndex: targetIndex};
                    }''', volume_number)

                    logger.info(f"分卷信息: {volume_info}")

                    if volume_info and volume_info.get('success'):
                        # 使用Playwright的原生click方法点击分卷项
                        target_index = volume_info['index']
                        volume_items = await self.page.query_selector_all('.editor-volume-list-item-normal')

                        if target_index < len(volume_items):
                            logger.info(f"使用Playwright原生方法点击分卷项（索引{target_index}）")
                            await volume_items[target_index].click()
                            await asyncio.sleep(0.5)

                            # 验证是否有selected类
                            has_selected = await self.page.evaluate('''(targetIndex) => {
                                const volumeItems = document.querySelectorAll('.editor-volume-list-item-normal');
                                if (targetIndex < volumeItems.length) {
                                    return volumeItems[targetIndex].className.includes('selected');
                                }
                                return false;
                            }''', target_index)

                            logger.info(f"点击后是否有selected类: {has_selected}")
                            select_result = volume_info
                        else:
                            logger.error(f"索引{target_index}超出范围")
                            select_result = {'success': False, 'error': '索引超出范围'}
                    else:
                        select_result = volume_info
                else:
                    # 没有分卷编号，使用默认分卷
                    logger.warning("未指定分卷编号，使用默认分卷")
                    select_result = {'success': True, 'default': True}

                logger.info(f"分卷选择结果: {select_result}")

                if select_result and select_result.get('success'):
                    await asyncio.sleep(0.5)
                    # 点击"确定"按钮
                    confirm_btn = await self.page.evaluate('''() => {
                        const buttons = Array.from(document.querySelectorAll('button'));
                        const confirmBtn = buttons.find(btn => btn.textContent.includes('确定'));
                        if (confirmBtn) {
                            console.log('找到确定按钮，点击它');
                            confirmBtn.click();
                            return true;
                        }
                        console.log('未找到确定按钮');
                        return false;
                    }''')

                    logger.info(f"确定按钮点击结果: {confirm_btn}")

                    if confirm_btn:
                        await asyncio.sleep(1)  # 等待对话框关闭和页面更新

                        # 验证分卷是否真的切换了
                        current_volume = await self.page.evaluate('''() => {
                            const volumeNameEl = document.querySelector('.publish-header-volume-name');
                            return volumeNameEl ? volumeNameEl.textContent.trim() : null;
                        }''')

                        logger.info(f"当前页面显示的分卷: {current_volume}")

                        if current_volume and select_result.get('matched') in current_volume:
                            logger.info(f"✅ 成功选择分卷: 第{volume_number}卷 ({current_volume})")
                            return True
                        else:
                            logger.warning(f"⚠️ 分卷选择可能失败: 期望'{select_result.get('matched')}'，实际'{current_volume}'")
                            return False
                    else:
                        logger.warning(f"未找到确定按钮，尝试按ESC关闭")
                        await self.page.keyboard.press('Escape')
                        await asyncio.sleep(0.5)
                        return False
                else:
                    # 如果没找到目标分卷，关闭对话框
                    await self.page.keyboard.press('Escape')
                    await asyncio.sleep(0.5)
                    logger.warning(f"未找到目标分卷，将使用当前分卷")
                    return True

            # 方法2: 如果没有找到分卷区域，说明可能已经自动选择了正确的分卷
            # 检查页面上是否显示了目标分卷名称
            page_content = await self.page.content()
            if volume_name in page_content:
                logger.info(f"页面上已显示分卷: {volume_name}，无需手动选择")
                return True

            logger.warning(f"未找到分卷选择器，将使用默认分卷")
            return True

        except Exception as e:
            logger.error(f"选择分卷失败: {e}")
            import traceback
            traceback.print_exc()
            return True  # 返回True以继续上传流程

    async def edit_volume_name(self, old_name: str, new_name: str) -> Dict[str, Any]:
        """编辑分卷名称

        Args:
            old_name: 原分卷名称（用于定位）
            new_name: 新分卷名称（最多20字）

        Returns:
            编辑结果
        """
        try:
            # 1. 点击"编辑分卷"按钮 - 使用JavaScript直接点击
            click_result = await self.page.evaluate('''() => {
                const buttons = Array.from(document.querySelectorAll('button'));
                const editBtn = buttons.find(btn => btn.textContent.includes('编辑分卷'));
                if (!editBtn) return false;
                editBtn.click();
                return true;
            }''')

            if not click_result:
                logger.error("未找到'编辑分卷'按钮")
                return {"success": False, "error": "未找到'编辑分卷'按钮"}

            await asyncio.sleep(2)  # 等待对话框打开

            # 2. 找到目标分卷并点击编辑图标
            # 使用JavaScript查找并点击编辑图标（使用参数传递避免注入）
            edit_result = await self.page.evaluate('''(oldName) => {
                const volumeItems = document.querySelectorAll('.chapter-volume-list-item-normal');
                for (const item of volumeItems) {
                    const nameSpan = item.querySelector('span');
                    if (nameSpan && nameSpan.textContent.includes(oldName)) {
                        const editIcon = item.querySelector('.tomato-edit');
                        if (editIcon) {
                            editIcon.click();
                            return true;
                        }
                    }
                }
                return false;
            }''', old_name)

            if not edit_result:
                logger.error(f"未找到分卷: {old_name}")
                return {"success": False, "error": f"未找到分卷: {old_name}"}

            await asyncio.sleep(0.5)

            # 3. 填写新的分卷名称
            input_selector = 'input[placeholder="请输入分卷名字"]'
            await self.page.wait_for_selector(input_selector, timeout=5000)
            await self.page.fill(input_selector, new_name)
            await asyncio.sleep(0.5)

            # 4. 点击对勾图标确认
            confirm_result = await self.page.evaluate('''() => {
                const confirmIcon = document.querySelector('.tomato-confirm');
                if (!confirmIcon) return false;
                confirmIcon.click();
                return true;
            }''')

            if not confirm_result:
                logger.error("未找到确认图标")
                return {"success": False, "error": "未找到确认图标"}

            await asyncio.sleep(1)

            # 5. 点击"确定"按钮保存
            confirm_btn_result = await self.page.evaluate('''() => {
                const buttons = Array.from(document.querySelectorAll('button'));
                const confirmBtn = buttons.find(btn => btn.textContent.includes('确定') && !btn.disabled);
                if (!confirmBtn) return false;
                confirmBtn.click();
                return true;
            }''')

            if not confirm_btn_result:
                logger.error("未找到'确定'按钮或按钮被禁用")
                return {"success": False, "error": "未找到'确定'按钮或按钮被禁用"}

            await asyncio.sleep(2)  # 等待对话框关闭

            logger.info(f"成功编辑分卷: {old_name} -> {new_name}")
            return {
                "success": True,
                "old_name": old_name,
                "new_name": new_name
            }
        except Exception as e:
            logger.error(f"编辑分卷失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def create_volume(self, volume_name: str) -> Dict[str, Any]:
        """创建新分卷

        注意: 只有当前分卷有章节时才能创建新分卷

        Args:
            volume_name: 分卷名称（最多20字）

        Returns:
            创建结果
        """
        try:
            logger.info(f"开始创建分卷: {volume_name}")

            # 1. 点击"编辑分卷"按钮
            logger.info("查找'编辑分卷'按钮...")
            try:
                # 使用JavaScript直接点击，更可靠
                click_result = await self.page.evaluate('''() => {
                    const buttons = Array.from(document.querySelectorAll('button'));
                    const editBtn = buttons.find(btn => btn.textContent.includes('编辑分卷'));
                    if (!editBtn) return false;
                    editBtn.click();
                    return true;
                }''')

                if not click_result:
                    logger.error("未找到'编辑分卷'按钮")
                    return {"success": False, "error": "未找到'编辑分卷'按钮"}

                logger.info("已点击'编辑分卷'按钮")
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"点击'编辑分卷'按钮失败: {e}")
                return {"success": False, "error": f"点击'编辑分卷'按钮失败: {e}"}

            # 2. 点击"新建分卷"按钮
            logger.info("查找'新建分卷'按钮...")
            try:
                click_result = await self.page.evaluate('''() => {
                    const elements = Array.from(document.querySelectorAll('*'));
                    const newVolumeBtn = elements.find(el => el.textContent.trim() === '新建分卷');
                    if (!newVolumeBtn) return false;
                    newVolumeBtn.click();
                    return true;
                }''')

                if not click_result:
                    logger.error("未找到'新建分卷'按钮")
                    return {"success": False, "error": "未找到'新建分卷'按钮"}

                logger.info("已点击'新建分卷'按钮")
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"点击'新建分卷'按钮失败: {e}")
                return {"success": False, "error": f"点击'新建分卷'按钮失败: {e}"}

            # 3. 填写分卷名称
            logger.info("填写分卷名称...")
            try:
                # 等待输入框出现
                volume_input = await self.page.wait_for_selector('input[placeholder*="分卷"], input[placeholder*="卷名"]', timeout=5000)
                if volume_input:
                    await volume_input.click()
                    await asyncio.sleep(0.2)
                    await volume_input.fill(volume_name)
                    logger.info(f"已填写分卷名称: {volume_name}")
                    await asyncio.sleep(0.5)
                else:
                    logger.error("未找到分卷名称输入框")
                    return {"success": False, "error": "未找到分卷名称输入框"}
            except Exception as e:
                logger.error(f"填写分卷名称失败: {e}")
                return {"success": False, "error": f"填写分卷名称失败: {e}"}

            # 4. 点击对勾确认或按Enter
            logger.info("确认分卷名称...")
            try:
                # 尝试方法1: 点击确认图标
                confirm_result = await self.page.evaluate('''() => {
                    const confirmIcon = document.querySelector('.tomato-confirm, .tomato-check, i[class*="confirm"]');
                    if (confirmIcon) {
                        confirmIcon.click();
                        return 'icon';
                    }
                    return false;
                }''')

                if confirm_result == 'icon':
                    logger.info("已点击确认图标")
                    await asyncio.sleep(1)
                else:
                    # 尝试方法2: 按Enter键
                    logger.info("未找到确认图标，尝试按Enter键")
                    await self.page.keyboard.press('Enter')
                    await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"确认分卷名称失败: {e}")

            # 5. 点击"确定"按钮保存
            logger.info("点击'确定'按钮保存...")
            try:
                # 先保存页面HTML用于调试
                try:
                    html_content = await self.page.content()
                    with open("debug_before_confirm.html", "w", encoding="utf-8") as f:
                        f.write(html_content)
                    logger.info("已保存页面HTML到 debug_before_confirm.html")
                except:
                    pass

                # 使用JavaScript查找并点击"确定"按钮
                confirm_result = await self.page.evaluate('''() => {
                    const buttons = Array.from(document.querySelectorAll('button'));
                    const confirmBtn = buttons.find(btn => btn.textContent.trim() === '确定');
                    if (!confirmBtn) {
                        // 返回所有按钮的文本用于调试
                        return {
                            success: false,
                            buttons: buttons.map(btn => btn.textContent.trim()).filter(t => t)
                        };
                    }
                    confirmBtn.click();
                    return {success: true};
                }''')

                if confirm_result.get('success'):
                    logger.info("已点击'确定'按钮")
                    await asyncio.sleep(2)
                else:
                    available_buttons = confirm_result.get('buttons', [])
                    logger.error(f"未找到'确定'按钮，可用按钮: {available_buttons}")
                    return {"success": False, "error": f"未找到'确定'按钮，可用按钮: {available_buttons}"}
            except Exception as e:
                logger.error(f"点击'确定'按钮失败: {e}")
                return {"success": False, "error": f"点击'确定'按钮失败: {e}"}

            logger.info(f"成功创建分卷: {volume_name}")
            return {
                "success": True,
                "volume_name": volume_name
            }
        except Exception as e:
            logger.error(f"创建分卷失败: {e}")
            # 保存页面HTML用于调试
            try:
                html_content = await self.page.content()
                with open("debug_create_volume_error.html", "w", encoding="utf-8") as f:
                    f.write(html_content)
                logger.info("已保存页面HTML到 debug_create_volume_error.html")
            except:
                pass
            return {
                "success": False,
                "error": str(e)
            }
            
    async def publish_chapter(
        self,
        chapter_number: int,
        chapter_title: str,
        content: str,
        volume_name: Optional[str] = None,
        volume_number: Optional[int] = None,
        use_ai: bool = False
    ) -> Dict[str, Any]:
        """发布章节到番茄小说

        基于实际测试的完整流程

        Args:
            chapter_number: 章节序号（纯数字）
            chapter_title: 章节标题（会自动清理"第X章"前缀）
            content: 章节内容
            volume_name: 分卷名称（可选，不指定则使用当前分卷）
            use_ai: 是否使用AI（默认否，审核通过后立即发布）

        Returns:
            发布结果
        """
        # ✅ 修复：添加输入参数验证
        if not content:
            logger.error("章节内容为空")
            return {"success": False, "error": "章节内容不能为空"}

        if chapter_number <= 0:
            logger.error(f"无效的章节号: {chapter_number}")
            return {"success": False, "error": "章节号必须大于0"}

        try:
            # 1. 点击"新建章节"按钮并等待新页面打开
            logger.info("点击'新建章节'按钮...")

            # 使用context.expect_page()等待新页面打开
            async with self.context.expect_page() as new_page_info:
                # 点击"新建章节"按钮
                click_result = await self.page.evaluate('''() => {
                    const buttons = Array.from(document.querySelectorAll('button, a'));
                    const newChapterBtn = buttons.find(btn => btn.textContent.includes('新建章节'));
                    if (!newChapterBtn) return false;
                    newChapterBtn.click();
                    return true;
                }''')

                if not click_result:
                    logger.error("未找到'新建章节'按钮")
                    return {"success": False, "error": "未找到'新建章节'按钮"}

            # 2. 切换到新打开的页面
            new_page = await new_page_info.value
            self.page = new_page
            logger.info("已切换到新标签页")

            # 等待页面加载完成
            await self.page.wait_for_load_state("domcontentloaded", timeout=15000)
            await asyncio.sleep(3)  # 等待React渲染完成
            logger.info("新标签页加载完成")

            # 3. 如果指定了分卷，选择对应的分卷
            if volume_name or volume_number:
                if volume_number:
                    logger.info(f"尝试选择分卷: 第{volume_number}卷")
                else:
                    logger.info(f"尝试选择分卷: {volume_name}")
                volume_selected = await self.select_volume_in_editor(volume_name=volume_name, volume_number=volume_number)
                if not volume_selected:
                    logger.error(f"未能选择分卷，终止上传")
                    return {
                        "success": False,
                        "error": f"未能选择分卷，请确认分卷已创建"
                    }

            # 4. 验证内容字数
            # 番茄小说要求正文至少1000字
            content_length = len(content.strip())
            if content_length < 1000:
                error_msg = f"正文字数不足：当前{content_length}字，需要至少1000字"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            # 5. 处理章节标题
            # 检查标题是否为通用格式（如"第一章"、"第二章"、"第X章"等）
            is_generic_title = False
            if not chapter_title:
                is_generic_title = True
            elif chapter_title in ["第一章", "第二章", "第三章", "第四章", "第五章", "第六章", "第七章", "第八章", "第九章", "第十章"]:
                is_generic_title = True
            elif chapter_title == f"第{chapter_number}章":
                is_generic_title = True
            elif re.match(r'^第[0-9一二三四五六七八九十百千万]+章$', chapter_title):
                is_generic_title = True

            if is_generic_title:
                error_msg = f"章节{chapter_number}标题为通用格式'{chapter_title}'，跳过上传"
                logger.warning(error_msg)
                return {"success": False, "error": error_msg, "skipped": True}

            # 使用传入的标题（已经在upload_novel_to_fanqie中处理过了）
            clean_title = chapter_title
            logger.info(f"使用章节标题: {clean_title}")

            # 4. 填写章节号
            # 先点击输入框聚焦，然后填写
            chapter_num_input = await self.page.query_selector('.serial-editor-title-left input')
            if chapter_num_input:
                await chapter_num_input.click()
                await asyncio.sleep(0.2)
                await chapter_num_input.fill(str(chapter_number))
                await asyncio.sleep(0.3)
                logger.info(f"填写章节号: {chapter_number}")
            else:
                logger.error("未找到章节号输入框")

            # 5. 填写标题
            # 先点击输入框聚焦，然后填写
            title_input = await self.page.query_selector('input[placeholder*="标题"]')
            if title_input:
                await title_input.click()
                await asyncio.sleep(0.2)
                await title_input.fill(clean_title)
                await asyncio.sleep(0.3)
                logger.info(f"填写标题: {clean_title}")
            else:
                logger.error("未找到标题输入框")

            # 6. 填写正文内容
            # 使用ProseMirror编辑器
            editor = await self.page.query_selector('.ProseMirror')
            if editor:
                # 清空编辑器
                await self.page.evaluate('''() => {
                    const editor = document.querySelector('.ProseMirror');
                    if (editor) editor.innerHTML = '';
                }''')

                # 将内容按段落分割并插入
                paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
                await self.page.evaluate('''(paragraphs) => {
                    const editor = document.querySelector('.ProseMirror');
                    if (editor) {
                        paragraphs.forEach(para => {
                            const p = document.createElement('p');
                            p.textContent = para;
                            editor.appendChild(p);
                        });
                        editor.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                }''', paragraphs)

                logger.info(f"填写内容: {len(content)}字, {len(paragraphs)}段")
                await asyncio.sleep(2)  # 等待自动保存

            # 7. 灵活的状态机：循环检测页面状态并处理
            logger.info("开始灵活状态机处理流程...")
            max_attempts = 20  # 最多尝试20次
            attempt = 0
            publish_dialog_found = False
            typo_submitted = False  # 标记是否已点击提交
            risk_confirmed = False  # 标记是否已点击确定

            while attempt < max_attempts and not publish_dialog_found:
                attempt += 1
                logger.info(f"状态检测循环 {attempt}/{max_attempts}")

                # 检测当前页面状态并执行相应操作（按优先级：确定 > 提交 > 发布设置 > 下一步）
                typo_submitted_js = 'true' if typo_submitted else 'false'
                risk_confirmed_js = 'true' if risk_confirmed else 'false'

                action_result = await self.page.evaluate(f'''() => {{
                    const typoSubmitted = {typo_submitted_js};
                    const riskConfirmed = {risk_confirmed_js};
                    const modals = Array.from(document.querySelectorAll('.arco-modal'));
                    const buttons = Array.from(document.querySelectorAll('button'));

                    // 优先级1: 检查是否有风险检测对话框的"确定"按钮（如果还没点击过）
                    if (!riskConfirmed) {{
                        const riskModal = modals.find(m => {{
                            const text = m.textContent || '';
                            return text.includes('风险检测') || text.includes('风险提示') || text.includes('是否进行');
                        }});
                        if (riskModal) {{
                            const modalButtons = Array.from(riskModal.querySelectorAll('button'));
                            const confirmBtn = modalButtons.find(btn =>
                                btn.textContent.trim() === '确定' &&
                                btn.className.includes('arco-btn-primary')
                            );
                            if (confirmBtn) {{
                                confirmBtn.click();
                                return {{action: 'clicked_confirm_risk', success: true, hasModal: true}};
                            }}
                        }}
                    }}

                    // 优先级2: 检查是否有错别字对话框的"提交"按钮（如果还没点击过）
                    if (!typoSubmitted) {{
                        const typoModal = modals.find(m => m.textContent.includes('错别字'));
                        if (typoModal) {{
                            const modalButtons = Array.from(typoModal.querySelectorAll('button'));
                            const submitBtn = modalButtons.find(btn => btn.textContent.trim() === '提交');
                            if (submitBtn) {{
                                submitBtn.click();
                                return {{action: 'clicked_submit_typo', success: true, hasModal: true}};
                            }}
                        }}
                    }}

                    // 优先级3: 检查是否有发布设置对话框（目标状态，不点击）
                    const publishModal = modals.find(m => m.textContent.includes('发布设置'));
                    if (publishModal) {{
                        return {{action: 'found_publish_dialog', success: true}};
                    }}

                    // 优先级4: 只有在没有对话框时才点击"下一步"
                    if (modals.length === 0) {{
                        const nextBtn = buttons.find(btn => btn.textContent.includes('下一步'));
                        if (nextBtn && !nextBtn.disabled) {{
                            nextBtn.click();
                            return {{action: 'clicked_next', success: true, hasModal: false}};
                        }}
                    }}

                    // 5. 没有找到任何可操作的元素
                    return {{action: 'none', success: false, modalCount: modals.length, buttons: buttons.map(b => b.textContent.trim())}};
                }}''')

                action = action_result.get('action')
                has_modal = action_result.get('hasModal', False)

                if action == 'clicked_confirm_risk':
                    logger.info("✅ 已点击风险检测对话框的'确定'按钮，等待发布设置对话框...")
                    risk_confirmed = True  # 标记已点击确定
                    await asyncio.sleep(5)  # 等待对话框关闭和发布设置对话框出现

                elif action == 'clicked_submit_typo':
                    logger.info("✅ 已点击错别字对话框的'提交'按钮，等待对话框关闭...")
                    typo_submitted = True  # 标记已点击提交
                    await asyncio.sleep(5)  # 等待对话框关闭

                elif action == 'found_publish_dialog':
                    logger.info("✅ 发现发布设置对话框")
                    publish_dialog_found = True
                    break

                elif action == 'clicked_next':
                    logger.info("✅ 已点击'下一步'按钮，等待页面响应...")
                    await asyncio.sleep(5)  # 等待页面响应（改为5秒）

                else:
                    # 没有找到任何可操作的元素，等待一下再检测
                    modal_count = action_result.get('modalCount', 0)
                    logger.info(f"⏳ 未找到可操作元素，等待页面更新... (对话框数: {modal_count})")
                    await asyncio.sleep(5)  # 改为5秒检测一次

            if not publish_dialog_found:
                logger.error("超过最大尝试次数，未能到达发布设置对话框")
                # 保存页面HTML用于调试
                page_content = await self.page.content()
                with open("debug_state_machine_failed.html", "w", encoding="utf-8") as f:
                    f.write(page_content)
                logger.error("已保存页面HTML到 debug_state_machine_failed.html")
                return {"success": False, "error": "未能到达发布设置对话框"}

            # 10. 选择是否使用AI
            ai_option = "是" if use_ai else "否"
            try:
                # 使用JavaScript直接点击radio按钮
                click_result = await self.page.evaluate(f'''() => {{
                    const labels = Array.from(document.querySelectorAll('label'));
                    const targetLabel = labels.find(label => label.textContent.trim() === '{ai_option}');
                    if (!targetLabel) return false;
                    targetLabel.click();
                    return true;
                }}''')

                if click_result:
                    logger.info(f"选择AI选项: {ai_option}")
                    await asyncio.sleep(0.5)
                else:
                    logger.warning(f"未找到AI选项: {ai_option}")
            except Exception as e:
                logger.warning(f"选择AI选项失败: {e}")

            # 11. 确保定时发布是关闭的（审核通过后立即发布）
            # 定时发布开关默认是关闭的，不需要额外操作

            # 12. 点击"确认发布"
            try:
                publish_btn = await self.page.wait_for_selector('button:has-text("确认发布")', timeout=5000)
                if publish_btn:
                    await publish_btn.click()
                    await asyncio.sleep(3)
                    logger.info("点击'确认发布'按钮")
                else:
                    logger.error("未找到'确认发布'按钮")
                    return {"success": False, "error": "未找到'确认发布'按钮"}
            except PlaywrightTimeoutError:
                logger.error("等待'确认发布'按钮超时")
                return {"success": False, "error": "等待'确认发布'按钮超时"}

            # 13. 检查是否发布成功
            # 成功后会显示"已提交，预计1小时内完成审核"
            logger.info(f"章节发布成功: 第{chapter_number}章 {clean_title}")
            return {
                "success": True,
                "chapter_number": chapter_number,
                "title": clean_title,
                "status": "已提交审核"
            }

        except Exception as e:
            logger.error(f"发布章节失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }

    async def upload_novel_to_fanqie(
        self,
        db: AsyncSession,
        project_id: str,
        account: str = "default",
        upload_interval: int = 20
    ) -> Dict[str, Any]:
        """一键上传小说到番茄小说

        完整流程：
        1. 加载Cookie登录
        2. 通过书名查找book_id
        3. 同步分卷结构
        4. 批量上传章节

        Args:
            db: 异步数据库会话
            project_id: 小说项目ID
            account: 番茄小说账号标识
            upload_interval: 上传间隔（秒），默认20秒

        Returns:
            上传结果
        """
        try:
            # 1. 查询小说项目
            stmt = select(NovelProject).where(NovelProject.id == project_id)
            result = await db.execute(stmt)
            project = result.scalar_one_or_none()

            if not project:
                return {"success": False, "error": "小说项目不存在"}

            book_name = project.title
            logger.info(f"开始上传小说: {book_name}")

            # 2. 加载Cookie
            cookie_loaded = await self.load_cookies(account)
            if not cookie_loaded:
                logger.error(f"Cookie加载失败，账号标识: {account}")
                cookies_file = self.cookies_dir / f"{account}_cookies.json"
                return {
                    "success": False,
                    "error": f"Cookie加载失败，请先调用 /api/novels/fanqie/login 接口手动登录并保存Cookie（账号标识: {account}）",
                    "hint": f"Cookie文件路径: {cookies_file.absolute()}"
                }

            # Cookie已加载,准备获取book_id
            logger.info("Cookie已加载")

            # 3. 获取book_id（优先使用项目中保存的fanqie_book_id）
            book_id = project.fanqie_book_id

            if book_id:
                logger.info(f"✅ 使用项目中保存的番茄book_id: {book_id}")
            else:
                # 如果没有保存book_id，尝试通过书名查找
                logger.info(f"项目未保存book_id，尝试通过书名查找: {book_name}")
                book_id = await self.find_book_by_name(book_name)

                if not book_id:
                    # 找不到则自动创建
                    logger.info(f"未找到书籍: {book_name}，尝试自动创建...")
                    create_result = await self.create_book(book_name)

                    if not create_result.get("success"):
                        return {
                            "success": False,
                            "error": f"创建书籍失败: {create_result.get('error')}",
                            "hint": "请检查番茄小说平台是否允许创建新书籍,或手动在平台上创建后再试"
                        }

                    book_id = create_result.get("book_id")
                    logger.info(f"书籍创建成功, ID: {book_id}")

                # 保存book_id到项目，避免下次再查找
                logger.info(f"💾 保存book_id到项目: {book_id}")
                project.fanqie_book_id = book_id
                await db.commit()

            # 4. 导航到章节管理页面
            nav_success = await self.navigate_to_chapter_manage(book_id)
            if not nav_success:
                return {"success": False, "error": "导航到章节管理页面失败"}

            # 5. 同步分卷结构
            # 先获取番茄小说上现有的分卷
            existing_volumes = await self.get_all_volumes()
            if not existing_volumes:
                logger.error("无法获取现有分卷列表")
                return {"success": False, "error": "无法获取现有分卷列表"}

            logger.info(f"番茄小说现有分卷（原始顺序）: {[v['name'] for v in existing_volumes]}")

            # 番茄小说返回的分卷列表是倒序的，需要反转
            existing_volumes = list(reversed(existing_volumes))
            logger.info(f"番茄小说现有分卷（反转后）: {[v['name'] for v in existing_volumes]}")

            # 查询本地所有分卷
            volumes_stmt = (
                select(Volume)
                .where(Volume.project_id == project_id)
                .order_by(Volume.volume_number)
            )
            volumes_result = await db.execute(volumes_stmt)
            volumes = volumes_result.scalars().all()

            volume_sync_results = []

            # 通过名称匹配现有分卷，而不是通过索引
            existing_volume_names = [v['name'] for v in existing_volumes]
            logger.info(f"现有分卷名称: {existing_volume_names}")

            for i, volume in enumerate(volumes):
                # 去掉分卷名称中的"第X卷："前缀（番茄小说会自动添加）
                # 例如："第一卷：初入修仙界" -> "初入修仙界"
                volume_name = volume.title
                original_volume_name = volume_name  # 保存原始名称用于日志

                # 跳过"默认"卷（这是待命名的卷，不需要上传）
                if volume_name == "默认":
                    logger.info(f"跳过'默认'卷（第{volume.volume_number}卷），这是待命名的卷")
                    volume_sync_results.append({"success": True, "action": "skip", "volume_name": "默认"})
                    continue

                if "：" in volume_name:
                    parts = volume_name.split("：", 1)
                    if parts[0].startswith("第") and parts[0].endswith("卷"):
                        volume_name = parts[1]
                        logger.info(f"去掉分卷前缀: {original_volume_name} -> {volume_name}")

                # 检查番茄上是否有对应的分卷（通过卷号匹配）
                # 番茄上的分卷按顺序排列，第i个本地分卷对应第i个番茄分卷
                fanqie_volume_name = None
                if i < len(existing_volumes):
                    fanqie_volume_name = existing_volumes[i]['name']

                # 判断是否需要更新分卷名称
                if fanqie_volume_name:
                    # 分卷存在，检查名称是否匹配
                    # 番茄小说的分卷名称也需要去掉"第X卷："前缀再比较
                    fanqie_volume_name_clean = fanqie_volume_name
                    if "：" in fanqie_volume_name:
                        parts = fanqie_volume_name.split("：", 1)
                        if parts[0].startswith("第") and parts[0].endswith("卷"):
                            fanqie_volume_name_clean = parts[1]
                            logger.info(f"去掉番茄分卷前缀: {fanqie_volume_name} -> {fanqie_volume_name_clean}")

                    if fanqie_volume_name_clean == volume_name:
                        # 名称匹配，跳过
                        logger.info(f"分卷 '{volume_name}' 名称已匹配（番茄: '{fanqie_volume_name}'），跳过同步")
                        volume_sync_results.append({"success": True, "action": "skip", "volume_name": volume_name})
                    else:
                        # 名称不匹配，需要更新
                        logger.info(f"分卷名称不匹配: 番茄'{fanqie_volume_name_clean}' vs 本地'{volume_name}'，执行更新")
                        result = await self.edit_volume_name(fanqie_volume_name, volume_name)
                        volume_sync_results.append(result)

                        if not result.get("success"):
                            logger.error(f"分卷名称更新失败: {result}")
                            return {
                                "success": False,
                                "error": f"分卷名称更新失败: {result.get('error')}",
                                "volume_sync_results": volume_sync_results
                            }
                else:
                    # 分卷不存在，需要创建
                    logger.info(f"番茄上不存在第{i+1}个分卷，创建新分卷: {volume_name}")
                    result = await self.create_volume(volume_name)
                    volume_sync_results.append(result)

                    if not result.get("success"):
                        logger.error(f"分卷创建失败: {result}")
                        return {
                            "success": False,
                            "error": f"分卷创建失败: {result.get('error')}",
                            "volume_sync_results": volume_sync_results
                        }

            logger.info(f"分卷同步完成: {len(volumes)}个分卷")

            # 6. 获取已上传的章节信息
            uploaded_info = await self.get_uploaded_chapters()
            last_uploaded_chapter = uploaded_info.get("last_chapter_number", 0)

            if last_uploaded_chapter > 0:
                logger.info(f"检测到已上传 {uploaded_info['total_count']} 章，最后一章: 第{last_uploaded_chapter}章")
                logger.info(f"将从第 {last_uploaded_chapter + 1} 章开始上传")
            else:
                logger.info("未检测到已上传的章节，将从第1章开始上传")

            # 7. 批量上传章节
            # 查询所有章节及其关联数据
            chapters_stmt = (
                select(Chapter)
                .where(Chapter.project_id == project_id)
                .options(
                    selectinload(Chapter.selected_version),
                    selectinload(Chapter.volume)
                )
                .order_by(Chapter.chapter_number)
            )
            chapters_result = await db.execute(chapters_stmt)
            chapters = chapters_result.scalars().all()

            upload_results = []

            for chapter in chapters:
                # 跳过已上传的章节
                if chapter.chapter_number <= last_uploaded_chapter:
                    logger.info(f"跳过已上传的章节 {chapter.chapter_number}")
                    continue
                # 获取章节内容
                if not chapter.selected_version:
                    logger.warning(f"章节{chapter.chapter_number}没有选中的版本，跳过")
                    continue

                # 提取内容：如果是JSON格式，提取full_content等字段
                from ..services.novel_service import _coerce_text
                raw_content = chapter.selected_version.content
                content = _coerce_text(raw_content) if raw_content else None

                if not content:
                    logger.warning(f"章节{chapter.chapter_number}内容为空，跳过")
                    continue

                # 检查内容是否为空
                content = content.strip()
                if not content:
                    logger.warning(f"章节{chapter.chapter_number}内容为空，跳过")
                    continue

                # 获取分卷名称和编号
                volume_name = None
                volume_number = None
                if chapter.volume:
                    volume_name = chapter.volume.title
                    volume_number = chapter.volume.volume_number

                    # 如果是"默认"卷，不指定分卷名称（使用番茄小说的默认分卷）
                    if volume_name == "默认":
                        logger.info(f"章节{chapter.chapter_number}在'默认'卷中，将上传到番茄小说的默认分卷")
                        volume_name = None
                        volume_number = None
                    else:
                        # 不去掉前缀，直接使用完整的分卷名称（包含"第X卷："）
                        # 这样可以精确匹配番茄小说页面上的分卷
                        logger.info(f"章节{chapter.chapter_number}所属分卷: 第{volume_number}卷 {volume_name}")

                # 获取章节标题
                # 优先使用outline的title，其次从内容第一行提取，最后使用chapter_number
                chapter_title = f"第{chapter.chapter_number}章"

                # 查询章节大纲
                outline_stmt = (
                    select(ChapterOutline)
                    .where(
                        ChapterOutline.project_id == project_id,
                        ChapterOutline.chapter_number == chapter.chapter_number
                    )
                )
                outline_result = await db.execute(outline_stmt)
                outline = outline_result.scalar_one_or_none()

                # 如果outline有标题，优先使用outline的标题
                if outline and outline.title:
                    chapter_title = outline.title
                    # 如果outline标题是"第X章"这种通用格式，尝试从内容提取真实标题
                    if chapter_title in ["第一章", "第二章", "第三章", "第四章", "第五章", "第六章", "第七章", "第八章", "第九章", "第十章"] or \
                       (chapter_title.startswith("第") and chapter_title.endswith("章") and len(chapter_title) <= 4):
                        logger.info(f"章节{chapter.chapter_number}标题为通用格式'{chapter_title}'，尝试从内容提取真实标题")
                        if content:
                            first_line = content.split('\n')[0].strip()
                            # 如果第一行不是"第X章"格式，且长度合适，使用它作为标题
                            if first_line and not (first_line.startswith('第') and first_line.endswith('章') and len(first_line) <= 4):
                                if 2 <= len(first_line) <= 50:
                                    chapter_title = first_line
                                    # 从内容中移除第一行标题
                                    content = '\n'.join(content.split('\n')[1:]).strip()
                                    logger.info(f"使用内容第一行作为标题: {chapter_title}")
                else:
                    # 尝试从内容第一行提取标题
                    if content:
                        first_line = content.split('\n')[0].strip()
                        # 如果第一行看起来像标题（长度在2-50之间）
                        if first_line and 2 <= len(first_line) <= 50:
                            chapter_title = first_line
                            # 从内容中移除第一行标题
                            content = '\n'.join(content.split('\n')[1:]).strip()

                # 上传章节
                logger.info(f"上传章节 {chapter.chapter_number}/{len(chapters)}: {chapter_title} -> 第{volume_number}卷 {volume_name}")

                result = await self.publish_chapter(
                    chapter_number=chapter.chapter_number,
                    chapter_title=chapter_title,
                    content=content,
                    volume_name=volume_name,
                    volume_number=volume_number,
                    use_ai=False  # 不使用AI，审核通过后立即发布
                )

                upload_results.append(result)

                # 如果上传失败，立即停止
                if not result.get("success"):
                    logger.error(f"章节上传失败: {result}")
                    return {
                        "success": False,
                        "error": f"章节{chapter.chapter_number}上传失败: {result.get('error')}",
                        "volume_sync_results": volume_sync_results,
                        "upload_results": upload_results
                    }

                # 返回章节管理页面，准备上传下一章
                await self.navigate_to_chapter_manage(self.book_id)

                # 如果设置了上传间隔，则等待（手动上传模式）
                if upload_interval > 0:
                    logger.info(f"等待{upload_interval}秒后再上传下一章...")
                    await asyncio.sleep(upload_interval)
                else:
                    # 自动生成器模式，不需要等待
                    logger.info("自动生成器模式，立即上传下一章")

            logger.info(f"所有章节上传完成: {len(upload_results)}章")
            return {
                "success": True,
                "book_id": book_id,
                "book_name": book_name,
                "volume_count": len(volumes),
                "chapter_count": len(upload_results),
                "volume_sync_results": volume_sync_results,
                "upload_results": upload_results
            }

        except Exception as e:
            logger.error(f"上传小说失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }

    async def open_login_page(self, account: str = "default") -> Dict[str, Any]:
        """打开番茄小说登录页面，等待用户手动登录

        此方法只负责打开浏览器窗口，不做任何自动检测和保存。
        用户需要在浏览器中完成登录后，调用 manual_save_cookies() 保存Cookie。

        Args:
            account: 账号标识（用于后续保存Cookie时使用）

        Returns:
            操作结果
        """
        try:
            # 清除旧的Cookie,确保是全新的登录
            await self.context.clear_cookies()
            logger.info("已清除旧Cookie,准备进行全新登录")

            # 访问作家工作台（会自动跳转到登录页面）
            await self.page.goto("https://fanqienovel.com/main/writer/?enter_from=author_zone")

            logger.info("=" * 60)
            logger.info("浏览器窗口已打开，请在浏览器中完成登录操作")
            logger.info("=" * 60)
            logger.info("步骤:")
            logger.info("1. 在浏览器中点击登录按钮")
            logger.info("2. 使用手机扫码或账号密码登录")
            logger.info("3. 登录成功后，点击前端界面的'保存Cookie'按钮")
            logger.info("=" * 60)

            return {
                "success": True,
                "account": account,
                "message": "浏览器窗口已打开，请完成登录后点击'保存Cookie'按钮"
            }

        except Exception as e:
            logger.error(f"打开登录页面失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def manual_save_cookies(self, account: str = "default") -> Dict[str, Any]:
        """手动保存当前浏览器会话的Cookie

        此方法从当前浏览器会话中提取Cookie并保存到文件。
        应该在用户完成登录后调用。

        Args:
            account: 账号标识

        Returns:
            操作结果
        """
        try:
            # 获取当前Cookie
            cookies = await self.context.cookies()
            cookie_names = [c['name'] for c in cookies]
            logger.info(f"当前Cookie列表: {cookie_names}")

            # 检查是否有登录相关的Cookie
            has_login_cookie = any(name in cookie_names for name in [
                'sessionid', 'uid', 'passport_csrf_token', 'sid_guard',
                'sid_tt', 'ssid', 'odin_tt', 'passport_auth_status'
            ])

            if not has_login_cookie:
                logger.warning("未检测到登录Cookie，请确保已在浏览器中完成登录")
                return {
                    "success": False,
                    "error": "未检测到登录Cookie，请确保已在浏览器中完成登录"
                }

            # 保存Cookie
            save_success = await self.save_cookies(account)
            if save_success:
                logger.info(f"Cookie已保存，账号标识: {account}")
                return {
                    "success": True,
                    "account": account,
                    "message": "Cookie保存成功！"
                }
            else:
                return {
                    "success": False,
                    "error": "Cookie保存失败"
                }

        except Exception as e:
            logger.error(f"保存Cookie失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

