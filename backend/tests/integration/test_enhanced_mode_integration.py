"""
增强模式集成测试

测试完整的增强模式流程：
1. 章节生成
2. 超级分析
3. 角色追踪
4. 世界观扩展
5. 伏笔记录
6. 事务回滚
"""
import pytest
import json
from datetime import datetime, timezone
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.novel import (
    NovelProject, NovelBlueprint, BlueprintCharacter,
    Chapter, ChapterVersion, ChapterOutline, Volume
)
from app.models.auto_generator import AutoGeneratorTask
from app.services.auto_generator_service import AutoGeneratorService
from app.services.super_analysis_service import SuperAnalysisService
from app.services.llm_service import LLMService


# ==================== Fixtures ====================

@pytest.fixture
async def test_db():
    """创建内存数据库用于测试"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 创建session
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
    
    # 清理
    await engine.dispose()


@pytest.fixture
async def test_project(test_db: AsyncSession):
    """创建测试项目"""
    project = NovelProject(
        id="test_project_001",
        user_id=1,
        title="测试小说",
        initial_prompt="一个修仙世界的故事",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    test_db.add(project)
    
    # 创建蓝图
    blueprint = NovelBlueprint(
        project_id=project.id,
        title="测试小说",
        genre="玄幻",
        world_setting={
            "locations": ["天机阁", "青云宗"],
            "factions": ["正道联盟", "魔教"],
            "items": ["玄天剑"],
            "rules": ["修炼等级：炼气、筑基、金丹"]
        },
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    test_db.add(blueprint)
    
    # 创建角色
    char1 = BlueprintCharacter(
        project_id=project.id,
        name="林风",
        role="主角",
        description="天才修士",
        personality="冷静、果断",
        background="孤儿出身",
        current_state="炼气期巅峰",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    char2 = BlueprintCharacter(
        project_id=project.id,
        name="苏婉",
        role="女主",
        description="青云宗圣女",
        personality="温柔、善良",
        background="宗主之女",
        current_state="筑基期",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    test_db.add_all([char1, char2])
    
    # 创建分卷
    volume = Volume(
        project_id=project.id,
        volume_number=1,
        title="第一卷",
        description="崛起之路",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    test_db.add(volume)
    
    await test_db.commit()
    await test_db.refresh(project)
    await test_db.refresh(blueprint)
    await test_db.refresh(volume)
    
    return {
        "project": project,
        "blueprint": blueprint,
        "volume": volume,
        "characters": [char1, char2]
    }


@pytest.fixture
def mock_llm_service(mocker):
    """Mock LLM服务"""
    llm_service = mocker.Mock(spec=LLMService)
    
    # Mock 超级分析响应
    async def mock_get_llm_response(*args, **kwargs):
        prompt = kwargs.get('conversation_history', [{}])[0].get('content', '')
        
        # 基础分析响应
        if '摘要' in prompt or 'summary' in prompt.lower():
            return json.dumps({
                "summary": "林风在天机阁遇到神秘老者，获得传承",
                "key_events": [
                    "林风进入天机阁",
                    "遇到神秘老者",
                    "获得玄天剑法传承"
                ]
            }, ensure_ascii=False)
        
        # 增强分析响应
        if '角色' in prompt or 'character' in prompt.lower():
            return json.dumps({
                "character_changes": [
                    {
                        "name": "林风",
                        "changes": {
                            "current_state": "筑基期初期",
                            "abilities": ["玄天剑法"]
                        }
                    }
                ],
                "new_characters": [
                    {
                        "name": "神秘老者",
                        "role": "配角",
                        "description": "天机阁守护者",
                        "personality": "神秘、强大",
                        "background": "上古修士"
                    }
                ],
                "world_extensions": {
                    "locations": {
                        "天机阁密室": "存放传承的密室"
                    },
                    "items": {
                        "玄天剑": "上古神剑"
                    }
                },
                "foreshadowings": [
                    {
                        "content": "老者提到即将到来的大劫",
                        "type": "未来事件",
                        "importance": "高"
                    }
                ]
            }, ensure_ascii=False)
        
        return "{}"
    
    llm_service.get_llm_response = mock_get_llm_response
    
    # Mock 摘要生成
    async def mock_get_summary(*args, **kwargs):
        return "章节摘要：林风突破到筑基期"
    
    llm_service.get_summary = mock_get_summary
    
    return llm_service


# ==================== 测试用例 ====================

@pytest.mark.asyncio
async def test_enhanced_mode_full_flow(test_db: AsyncSession, test_project, mock_llm_service):
    """测试增强模式完整流程"""
    
    # 1. 创建章节
    chapter = Chapter(
        project_id=test_project["project"].id,
        volume_id=test_project["volume"].id,
        chapter_number=1,
        status="generated",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    test_db.add(chapter)
    await test_db.commit()
    await test_db.refresh(chapter)
    
    # 2. 创建章节版本
    version = ChapterVersion(
        chapter_id=chapter.id,
        version_label="v1",
        content="""
        林风踏入天机阁，这座传说中的上古遗迹终于向他敞开了大门。
        
        "年轻人，你终于来了。"一位神秘老者出现在他面前。
        
        老者传授给林风玄天剑法，这是失传已久的上古剑诀。林风感觉体内真气涌动，
        竟然直接突破到了筑基期！
        
        "记住，三年后会有大劫降临，你要做好准备。"老者说完便消失了。
        
        林风握着手中的玄天剑，心中充满了疑惑和期待。
        """,
        created_at=datetime.now(timezone.utc)
    )
    test_db.add(version)
    
    # 选中版本
    chapter.selected_version_id = version.id
    await test_db.commit()
    await test_db.refresh(chapter)
    
    # 3. 执行超级分析
    super_analysis = SuperAnalysisService(test_db, mock_llm_service)
    
    blueprint_dict = {
        "characters": [
            {"name": "林风", "role": "主角"},
            {"name": "苏婉", "role": "女主"}
        ],
        "world_setting": test_project["blueprint"].world_setting
    }
    
    basic_result, enhanced_result = await super_analysis.analyze_chapter(
        chapter_number=1,
        chapter_content=version.content,
        blueprint=blueprint_dict,
        user_id=1
    )
    
    # 4. 验证基础分析结果
    assert basic_result is not None
    assert "summary" in basic_result
    assert "林风" in basic_result["summary"]
    assert "key_events" in basic_result
    assert len(basic_result["key_events"]) > 0
    
    # 5. 验证增强分析结果
    assert enhanced_result is not None
    assert "character_changes" in enhanced_result
    assert "new_characters" in enhanced_result
    assert "world_extensions" in enhanced_result
    assert "foreshadowings" in enhanced_result
    
    # 6. 验证角色变化
    char_changes = enhanced_result["character_changes"]
    assert len(char_changes) > 0
    assert char_changes[0]["name"] == "林风"
    assert "筑基期" in char_changes[0]["changes"]["current_state"]
    
    # 7. 验证新角色
    new_chars = enhanced_result["new_characters"]
    assert len(new_chars) > 0
    assert new_chars[0]["name"] == "神秘老者"
    
    # 8. 验证世界观扩展
    world_ext = enhanced_result["world_extensions"]
    assert "locations" in world_ext or "items" in world_ext
    
    # 9. 验证伏笔
    foreshadowings = enhanced_result["foreshadowings"]
    assert len(foreshadowings) > 0
    assert "大劫" in foreshadowings[0]["content"]


@pytest.mark.asyncio
async def test_enhanced_mode_with_feature_toggle(test_db: AsyncSession, test_project, mock_llm_service):
    """测试增强模式功能开关"""
    
    # 创建任务，关闭部分功能
    task = AutoGeneratorTask(
        project_id=test_project["project"].id,
        user_id=1,
        target_chapters=10,
        status="running",
        generation_config={
            "generation_mode": "enhanced",
            "enhanced_features": {
                "character_tracking": True,
                "world_expansion": False,  # 关闭世界观扩展
                "foreshadowing": False,    # 关闭伏笔识别
                "new_character_detection": True
            }
        },
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    test_db.add(task)
    await test_db.commit()
    
    # 验证功能开关生效
    from app.schemas.generation_config import get_enabled_features
    features = get_enabled_features(task.generation_config)
    
    assert features["character_tracking"] is True
    assert features["world_expansion"] is False
    assert features["foreshadowing"] is False
    assert features["new_character_detection"] is True


@pytest.mark.asyncio
async def test_dynamic_threshold(test_db: AsyncSession, test_project):
    """测试动态阈值"""
    
    from app.schemas.generation_config import should_run_enhanced_analysis
    
    # 配置：最小长度2000字
    config = {
        "generation_mode": "enhanced",
        "dynamic_threshold": {
            "min_chapter_length": 2000
        }
    }
    
    # 短章节（1000字）不应该运行增强分析
    assert should_run_enhanced_analysis(config, 1000) is False
    
    # 长章节（3000字）应该运行增强分析
    assert should_run_enhanced_analysis(config, 3000) is True
    
    # 基础模式永远不运行增强分析
    config["generation_mode"] = "basic"
    assert should_run_enhanced_analysis(config, 5000) is False

