"""
后台处理器启动脚本

独立进程，定时扫描pending_analysis表并执行增强分析

使用方法:
    python -m app.background_processor
"""
import asyncio
import logging
import signal
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# ✅ 修复：从正确的路径导入AsyncSessionLocal
from app.db.session import AsyncSessionLocal
from app.services.async_analysis_processor import AsyncAnalysisProcessor
from app.services.llm_service import LLMService

# ✅ 修复：确保logs目录存在
log_dir = Path(__file__).parent.parent / 'logs'
log_dir.mkdir(exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'background_processor.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class BackgroundProcessorManager:
    """后台处理器管理器"""
    
    def __init__(self):
        self.processor = None
        self.is_running = False
    
    async def start(self):
        """启动处理器

        ✅ 修复：使用session_maker和llm_service_factory
        """
        logger.info("=" * 60)
        logger.info("异步分析后台处理器启动中...")
        logger.info("=" * 60)

        try:
            # ✅ 创建LLM服务工厂函数
            def llm_service_factory(db):
                return LLMService(db)

            # ✅ 创建处理器（传入session_maker和factory）
            self.processor = AsyncAnalysisProcessor(
                session_maker=AsyncSessionLocal,  # ✅ 修复：使用正确的AsyncSessionLocal
                llm_service_factory=llm_service_factory
            )

            # 配置处理器
            self.processor.max_concurrent = 3  # 最大并发数
            self.processor.poll_interval = 10  # 轮询间隔（秒）
            self.processor.processing_timeout = 600  # 处理超时（秒）

            logger.info(f"配置:")
            logger.info(f"  - 最大并发数: {self.processor.max_concurrent}")
            logger.info(f"  - 轮询间隔: {self.processor.poll_interval}秒")
            logger.info(f"  - 处理超时: {self.processor.processing_timeout}秒")
            logger.info("=" * 60)

            # 启动处理器
            self.is_running = True
            await self.processor.start()

        except KeyboardInterrupt:
            logger.info("收到中断信号，正在停止...")
            await self.stop()
        except Exception as e:
            logger.error(f"处理器异常: {e}", exc_info=True)
            await self.stop()
    
    async def stop(self):
        """停止处理器"""
        if self.processor:
            await self.processor.stop()
        
        self.is_running = False
        logger.info("=" * 60)
        logger.info("异步分析后台处理器已停止")
        logger.info("=" * 60)
    
    def handle_signal(self, signum, frame):
        """处理系统信号"""
        logger.info(f"收到信号 {signum}，准备退出...")
        if self.is_running:
            asyncio.create_task(self.stop())


async def main():
    """主函数"""
    manager = BackgroundProcessorManager()
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, manager.handle_signal)
    signal.signal(signal.SIGTERM, manager.handle_signal)
    
    # 启动处理器
    await manager.start()


if __name__ == "__main__":
    # 确保日志目录存在
    Path("logs").mkdir(exist_ok=True)
    
    # 运行主函数
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序已退出")

