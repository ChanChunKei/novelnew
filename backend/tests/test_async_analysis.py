"""
异步分析功能测试

测试：
1. PendingAnalysis模型
2. 异步处理器
3. API端点
"""
import pytest
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.async_task import PendingAnalysis, AnalysisNotification
from app.models.novel import NovelProject, Chapter, ChapterVersion, NovelBlueprint
from app.models.user import User
from app.services.async_analysis_processor import AsyncAnalysisProcessor
from app.services.llm_service import LLMService


# ==================== Fixtures ====================

@pytest.fixture
async def test_db():
    """创建测试数据库"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
    
    await engine.dispose()


@pytest.fixture
async def test_user(test_db: AsyncSession):
    """创建测试用户"""
    user = User(
        id=1,
        username="test_user",
        email="test@example.com",
        hashed_password="hashed",
        created_at=datetime.now(timezone.utc)
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest.fixture
async def test_project(test_db: AsyncSession, test_user):
    """创建测试项目"""
    project = NovelProject(
        id="test_project",
        user_id=test_user.id,
        title="测试小说",
        initial_prompt="测试",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    test_db.add(project)
    
    blueprint = NovelBlueprint(
        project_id=project.id,
        title="测试小说",
        genre="玄幻",
        world_setting={"locations": ["天机阁"]},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    test_db.add(blueprint)
    
    await test_db.commit()
    await test_db.refresh(project)
    
    return project


@pytest.fixture
async def test_chapter(test_db: AsyncSession, test_project):
    """创建测试章节"""
    chapter = Chapter(
        project_id=test_project.id,
        chapter_number=1,
        status="generated",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    test_db.add(chapter)
    await test_db.commit()
    await test_db.refresh(chapter)
    
    version = ChapterVersion(
        chapter_id=chapter.id,
        version_label="v1",
        content="测试章节内容" * 100,
        created_at=datetime.now(timezone.utc)
    )
    test_db.add(version)
    
    chapter.selected_version_id = version.id
    await test_db.commit()
    await test_db.refresh(chapter)
    
    return chapter


# ==================== 测试用例 ====================

@pytest.mark.asyncio
async def test_pending_analysis_model(test_db: AsyncSession, test_chapter, test_user):
    """测试PendingAnalysis模型"""
    # 创建待处理任务
    pending = PendingAnalysis(
        chapter_id=test_chapter.id,
        project_id=test_chapter.project_id,
        user_id=test_user.id,
        status='pending',
        priority=5,
        generation_config={"enhanced_features": {"character_tracking": True}}
    )
    test_db.add(pending)
    await test_db.commit()
    await test_db.refresh(pending)
    
    # 验证属性
    assert pending.is_pending is True
    assert pending.is_processing is False
    assert pending.is_completed is False
    assert pending.is_failed is False
    assert pending.can_retry is False
    
    # 更新状态为processing
    pending.status = 'processing'
    pending.started_at = datetime.now(timezone.utc)
    await test_db.commit()
    
    assert pending.is_processing is True
    assert pending.elapsed_seconds >= 0
    
    # 更新状态为completed
    pending.status = 'completed'
    pending.completed_at = datetime.now(timezone.utc)
    pending.duration_seconds = 10
    await test_db.commit()
    
    assert pending.is_completed is True
    
    # 测试失败状态
    pending.status = 'failed'
    pending.retry_count = 1
    pending.max_retries = 3
    await test_db.commit()
    
    assert pending.is_failed is True
    assert pending.can_retry is True


@pytest.mark.asyncio
async def test_analysis_notification(test_db: AsyncSession, test_chapter, test_user):
    """测试AnalysisNotification模型"""
    # 创建待处理任务
    pending = PendingAnalysis(
        chapter_id=test_chapter.id,
        project_id=test_chapter.project_id,
        user_id=test_user.id,
        status='pending'
    )
    test_db.add(pending)
    await test_db.commit()
    await test_db.refresh(pending)
    
    # 创建通知
    notification = AnalysisNotification(
        pending_analysis_id=pending.id,
        user_id=test_user.id,
        chapter_id=test_chapter.id,
        notification_type='started',
        title='分析已开始',
        message='正在处理...'
    )
    test_db.add(notification)
    await test_db.commit()
    await test_db.refresh(notification)
    
    # 验证未读状态
    assert notification.is_read == 0
    assert notification.read_at is None
    
    # 标记为已读
    notification.mark_as_read()
    await test_db.commit()
    
    assert notification.is_read == 1
    assert notification.read_at is not None


@pytest.mark.asyncio
async def test_async_processor_get_pending_tasks(
    test_db: AsyncSession,
    test_chapter,
    test_user,
    mocker
):
    """测试处理器获取待处理任务"""
    # 创建多个待处理任务
    for i in range(5):
        pending = PendingAnalysis(
            chapter_id=test_chapter.id,
            project_id=test_chapter.project_id,
            user_id=test_user.id,
            status='pending',
            priority=i  # 不同优先级
        )
        test_db.add(pending)
    await test_db.commit()
    
    # Mock LLM服务
    llm_service = mocker.Mock(spec=LLMService)
    
    # 创建处理器
    processor = AsyncAnalysisProcessor(test_db, llm_service)
    
    # 获取待处理任务
    tasks = await processor._get_pending_tasks(limit=3)
    
    # 验证：应该按优先级降序返回
    assert len(tasks) == 3
    assert tasks[0].priority >= tasks[1].priority >= tasks[2].priority


@pytest.mark.asyncio
async def test_async_processor_send_notification(
    test_db: AsyncSession,
    test_chapter,
    test_user,
    mocker
):
    """测试处理器发送通知"""
    # 创建待处理任务
    pending = PendingAnalysis(
        chapter_id=test_chapter.id,
        project_id=test_chapter.project_id,
        user_id=test_user.id,
        status='pending'
    )
    test_db.add(pending)
    await test_db.commit()
    await test_db.refresh(pending)
    
    # Mock LLM服务
    llm_service = mocker.Mock(spec=LLMService)
    
    # 创建处理器
    processor = AsyncAnalysisProcessor(test_db, llm_service)
    
    # 发送通知
    await processor._send_notification(
        pending=pending,
        notification_type='started',
        title='测试通知',
        message='测试消息'
    )
    
    # 验证通知已创建
    stmt = select(AnalysisNotification).where(
        AnalysisNotification.pending_analysis_id == pending.id
    )
    result = await test_db.execute(stmt)
    notification = result.scalar_one_or_none()
    
    assert notification is not None
    assert notification.title == '测试通知'
    assert notification.message == '测试消息'
    assert notification.notification_type == 'started'


@pytest.mark.asyncio
async def test_pending_analysis_query_performance(test_db: AsyncSession, test_chapter, test_user):
    """测试查询性能（大量数据）"""
    # 创建1000个待处理任务
    tasks = []
    for i in range(1000):
        pending = PendingAnalysis(
            chapter_id=test_chapter.id,
            project_id=test_chapter.project_id,
            user_id=test_user.id,
            status='pending' if i % 2 == 0 else 'completed',
            priority=i % 10
        )
        tasks.append(pending)
    
    test_db.add_all(tasks)
    await test_db.commit()
    
    # 查询待处理任务（应该使用索引）
    import time
    start = time.time()
    
    stmt = select(PendingAnalysis).where(
        PendingAnalysis.status == 'pending'
    ).order_by(
        PendingAnalysis.priority.desc()
    ).limit(10)
    
    result = await test_db.execute(stmt)
    pending_tasks = list(result.scalars().all())
    
    elapsed = time.time() - start
    
    # 验证
    assert len(pending_tasks) == 10
    assert elapsed < 0.1  # 应该很快（<100ms）

