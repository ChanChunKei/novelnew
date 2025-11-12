import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_admin
from ...db.session import get_session
from ...models import NovelProject, UsageMetric, User
from ...schemas.admin import (
    AdminNovelSummary,
    DailyRequestLimit,
    Statistics,
    UpdateLogCreate,
    UpdateLogRead,
    UpdateLogUpdate,
)
from ...schemas.config import SystemConfigCreate, SystemConfigRead, SystemConfigUpdate
from ...schemas.prompt import PromptCreate, PromptRead, PromptUpdate
from ...schemas.novel import (
    Chapter as ChapterSchema,
    NovelProject as NovelProjectSchema,
    NovelSectionResponse,
    NovelSectionType,
)
from ...schemas.user import AdminCreate, PasswordChangeRequest, User as UserSchema
from ...schemas.rag_test import GeminiRAGTestRequest, GeminiRAGTestResult
from ...services.auth_service import AuthService
from ...services.admin_setting_service import AdminSettingService
from ...services.config_service import ConfigService
from ...services.novel_service import NovelService
from ...services.prompt_service import PromptService
from ...services.update_log_service import UpdateLogService
from ...services.user_service import UserService
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Admin"])


def get_prompt_service(session: AsyncSession = Depends(get_session)) -> PromptService:
    return PromptService(session)


def get_update_log_service(session: AsyncSession = Depends(get_session)) -> UpdateLogService:
    return UpdateLogService(session)


def get_admin_setting_service(session: AsyncSession = Depends(get_session)) -> AdminSettingService:
    return AdminSettingService(session)


def get_config_service(session: AsyncSession = Depends(get_session)) -> ConfigService:
    return ConfigService(session)


def get_novel_service(session: AsyncSession = Depends(get_session)) -> NovelService:
    return NovelService(session)


def get_user_service(session: AsyncSession = Depends(get_session)) -> UserService:
    return UserService(session)


def get_auth_service(session: AsyncSession = Depends(get_session)) -> AuthService:
    return AuthService(session)


@router.get("/stats", response_model=Statistics)
async def read_statistics(
    session: AsyncSession = Depends(get_session),
    _: None = Depends(get_current_admin),
) -> Statistics:
    novel_count = await session.scalar(select(func.count(NovelProject.id))) or 0
    user_count = await session.scalar(select(func.count(User.id))) or 0
    usage = await session.get(UsageMetric, "api_request_count")
    api_request_count = usage.value if usage else 0
    logger.info("管理员获取统计数据：小说=%s，用户=%s，请求=%s", novel_count, user_count, api_request_count)
    return Statistics(novel_count=novel_count, user_count=user_count, api_request_count=api_request_count)


@router.get("/users", response_model=List[UserSchema])
async def list_users(
    service: UserService = Depends(get_user_service),
    _: None = Depends(get_current_admin),
) -> List[UserSchema]:
    users = await service.list_users()
    logger.info("管理员请求用户列表，共 %s 条", len(users))
    return [UserSchema.model_validate(user) for user in users]


@router.post("/users", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
async def create_admin_user(
    payload: AdminCreate,
    service: AuthService = Depends(get_auth_service),
    _: None = Depends(get_current_admin),
) -> UserSchema:
    """管理员创建新的管理员或普通用户账户。"""
    user = await service.create_admin_user(
        username=payload.username,
        email=payload.email,
        password=payload.password,
        is_admin=payload.is_admin,
    )
    logger.info("管理员创建新用户：%s (is_admin=%s)", user.username, user.is_admin)
    return UserSchema.model_validate(user)


@router.patch("/users/{user_id}/toggle-active", response_model=UserSchema)
async def toggle_user_active(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    current_admin=Depends(get_current_admin),
) -> UserSchema:
    """管理员启用/禁用用户账户。"""
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 防止管理员禁用自己
    if user.id == current_admin.id:
        raise HTTPException(status_code=400, detail="不能禁用自己的账户")

    user.is_active = not user.is_active
    await session.commit()
    await session.refresh(user)

    logger.info("管理员 %s %s 用户 %s", current_admin.username, "启用" if user.is_active else "禁用", user.username)
    return UserSchema.model_validate(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    current_admin=Depends(get_current_admin),
) -> None:
    """管理员删除用户账户。"""
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 防止管理员删除自己
    if user.id == current_admin.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账户")

    username = user.username
    await session.delete(user)
    await session.commit()

    logger.info("管理员 %s 删除用户 %s", current_admin.username, username)


@router.get("/novel-projects", response_model=List[AdminNovelSummary])
async def list_novel_projects(
    service: NovelService = Depends(get_novel_service),
    _: None = Depends(get_current_admin),
) -> List[AdminNovelSummary]:
    projects = await service.list_projects_for_admin()
    logger.info("管理员查看项目列表，共 %s 个", len(projects))
    return projects


@router.delete("/novel-projects/unfinished-inspirations", status_code=status.HTTP_200_OK)
async def delete_unfinished_inspirations(
    session: AsyncSession = Depends(get_session),
    current_admin=Depends(get_current_admin),
) -> dict:
    """删除所有未完成的灵感项目（未命名或使用默认名称的项目）

    ✅ 性能优化：在数据库层面筛选，避免加载所有项目到内存
    """

    # ✅ 在数据库层面构建筛选条件
    conditions = [
        NovelProject.title.is_(None),  # 标题为NULL
        func.trim(NovelProject.title) == '',  # 标题为空字符串（去除空格后）
    ]

    # 添加各种默认名称的条件（不区分大小写）
    default_names = ['未命名', '新项目', 'untitled', 'new project', '未命名灵感']
    for pattern in default_names:
        conditions.append(func.lower(func.trim(NovelProject.title)) == pattern)

    # ✅ 在数据库层面筛选，只查询符合条件的项目
    result = await session.execute(
        select(NovelProject).where(or_(*conditions))
    )
    unfinished_projects = result.scalars().all()

    # 收集ID并删除
    deleted_ids = [project.id for project in unfinished_projects]
    deleted_count = len(deleted_ids)

    for project in unfinished_projects:
        await session.delete(project)

    await session.commit()

    logger.info(
        "管理员 %s 删除了 %s 个未完成灵感项目: %s",
        current_admin.username,
        deleted_count,
        deleted_ids[:10]  # 只记录前10个ID
    )

    return {
        "deleted_count": deleted_count,
        "deleted_ids": deleted_ids,
        "message": f"成功删除 {deleted_count} 个未完成的灵感项目"
    }


@router.get("/novel-projects/{project_id}", response_model=NovelProjectSchema)
async def get_novel_project(
    project_id: str,
    service: NovelService = Depends(get_novel_service),
    _: None = Depends(get_current_admin),
) -> NovelProjectSchema:
    logger.info("管理员查看项目详情：%s", project_id)
    return await service.get_project_schema_for_admin(project_id)


@router.get("/novel-projects/{project_id}/sections/{section}", response_model=NovelSectionResponse)
async def get_novel_project_section(
    project_id: str,
    section: NovelSectionType,
    service: NovelService = Depends(get_novel_service),
    _: None = Depends(get_current_admin),
) -> NovelSectionResponse:
    logger.info("管理员查看项目 %s 的 %s 区段", project_id, section)
    return await service.get_section_data_for_admin(project_id, section)


@router.get("/novel-projects/{project_id}/chapters/{chapter_number}", response_model=ChapterSchema)
async def get_novel_project_chapter(
    project_id: str,
    chapter_number: int,
    service: NovelService = Depends(get_novel_service),
    _: None = Depends(get_current_admin),
) -> ChapterSchema:
    logger.info("管理员查看项目 %s 第 %s 章详情", project_id, chapter_number)
    return await service.get_chapter_schema_for_admin(project_id, chapter_number)


@router.get("/prompts", response_model=List[PromptRead])
async def list_prompts(
    service: PromptService = Depends(get_prompt_service),
    _: None = Depends(get_current_admin),
) -> List[PromptRead]:
    prompts = await service.list_prompts()
    logger.info("管理员请求提示词列表，共 %s 条", len(prompts))
    return prompts


@router.post("/prompts", response_model=PromptRead, status_code=status.HTTP_201_CREATED)
async def create_prompt(
    payload: PromptCreate,
    service: PromptService = Depends(get_prompt_service),
    _: None = Depends(get_current_admin),
) -> PromptRead:
    prompt = await service.create_prompt(payload)
    logger.info("管理员创建提示词：%s", prompt.id)
    return prompt


@router.get("/prompts/{prompt_id}", response_model=PromptRead)
async def get_prompt(
    prompt_id: int,
    service: PromptService = Depends(get_prompt_service),
    _: None = Depends(get_current_admin),
) -> PromptRead:
    prompt = await service.get_prompt_by_id(prompt_id)
    if not prompt:
        logger.warning("提示词 %s 不存在", prompt_id)
        raise HTTPException(status_code=404, detail="提示词不存在")
    logger.info("管理员获取提示词：%s", prompt_id)
    return prompt


@router.patch("/prompts/{prompt_id}", response_model=PromptRead)
async def update_prompt(
    prompt_id: int,
    payload: PromptUpdate,
    service: PromptService = Depends(get_prompt_service),
    _: None = Depends(get_current_admin),
) -> PromptRead:
    result = await service.update_prompt(prompt_id, payload)
    if not result:
        logger.warning("提示词 %s 不存在，无法更新", prompt_id)
        raise HTTPException(status_code=404, detail="提示词不存在")
    logger.info("管理员更新提示词：%s", prompt_id)
    return result


@router.delete("/prompts/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt(
    prompt_id: int,
    service: PromptService = Depends(get_prompt_service),
    _: None = Depends(get_current_admin),
) -> None:
    deleted = await service.delete_prompt(prompt_id)
    if not deleted:
        logger.warning("提示词 %s 不存在，无法删除", prompt_id)
        raise HTTPException(status_code=404, detail="提示词不存在")
    logger.info("管理员删除提示词：%s", prompt_id)


@router.get("/update-logs", response_model=List[UpdateLogRead])
async def list_update_logs(
    service: UpdateLogService = Depends(get_update_log_service),
    _: None = Depends(get_current_admin),
) -> List[UpdateLogRead]:
    logs = await service.list_logs()
    logger.info("管理员查看更新日志列表，共 %s 条", len(logs))
    return [UpdateLogRead.model_validate(log) for log in logs]


@router.post("/update-logs", response_model=UpdateLogRead, status_code=status.HTTP_201_CREATED)
async def create_update_log(
    payload: UpdateLogCreate,
    service: UpdateLogService = Depends(get_update_log_service),
    current_admin=Depends(get_current_admin),
) -> UpdateLogRead:
    log = await service.create_log(
        payload.content,
        creator=current_admin.username,
        is_pinned=payload.is_pinned or False,
    )
    logger.info("管理员 %s 创建更新日志：%s", current_admin.username, log.id)
    return UpdateLogRead.model_validate(log)


@router.delete("/update-logs/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_update_log(
    log_id: int,
    service: UpdateLogService = Depends(get_update_log_service),
    _: None = Depends(get_current_admin),
) -> None:
    await service.delete_log(log_id)
    logger.info("管理员删除更新日志：%s", log_id)


@router.patch("/update-logs/{log_id}", response_model=UpdateLogRead)
async def update_update_log(
    log_id: int,
    payload: UpdateLogUpdate,
    service: UpdateLogService = Depends(get_update_log_service),
    _: None = Depends(get_current_admin),
) -> UpdateLogRead:
    log = await service.update_log(
        log_id,
        content=payload.content,
        is_pinned=payload.is_pinned,
    )
    logger.info("管理员更新日志 %s", log_id)
    return UpdateLogRead.model_validate(log)


@router.get("/settings/daily-request-limit", response_model=DailyRequestLimit)
async def get_daily_limit(
    service: AdminSettingService = Depends(get_admin_setting_service),
    _: None = Depends(get_current_admin),
) -> DailyRequestLimit:
    value = await service.get("daily_request_limit", "100")
    logger.info("管理员查询每日请求上限：%s", value)
    return DailyRequestLimit(limit=int(value or 100))


@router.put("/settings/daily-request-limit", response_model=DailyRequestLimit)
async def update_daily_limit(
    payload: DailyRequestLimit,
    service: AdminSettingService = Depends(get_admin_setting_service),
    _: None = Depends(get_current_admin),
) -> DailyRequestLimit:
    await service.set("daily_request_limit", str(payload.limit))
    logger.info("管理员设置每日请求上限为 %s", payload.limit)
    return payload


@router.get("/system-configs", response_model=List[SystemConfigRead])
async def list_system_configs(
    service: ConfigService = Depends(get_config_service),
    _: None = Depends(get_current_admin),
) -> List[SystemConfigRead]:
    configs = await service.list_configs()
    logger.info("管理员获取系统配置，共 %s 条", len(configs))
    return configs


@router.get("/system-configs/{key}", response_model=SystemConfigRead)
async def get_system_config(
    key: str,
    service: ConfigService = Depends(get_config_service),
    _: None = Depends(get_current_admin),
) -> SystemConfigRead:
    config = await service.get_config(key)
    if not config:
        logger.warning("系统配置 %s 不存在", key)
        raise HTTPException(status_code=404, detail="配置项不存在")
    logger.info("管理员查询系统配置：%s", key)
    return config


@router.put("/system-configs/{key}", response_model=SystemConfigRead)
async def upsert_system_config(
    key: str,
    payload: SystemConfigCreate,
    service: ConfigService = Depends(get_config_service),
    _: None = Depends(get_current_admin),
) -> SystemConfigRead:
    logger.info("管理员写入系统配置：%s", key)
    return await service.upsert_config(
        SystemConfigCreate(key=key, value=payload.value, description=payload.description)
    )


@router.patch("/system-configs/{key}", response_model=SystemConfigRead)
async def patch_system_config(
    key: str,
    payload: SystemConfigUpdate,
    service: ConfigService = Depends(get_config_service),
    _: None = Depends(get_current_admin),
) -> SystemConfigRead:
    config = await service.patch_config(key, payload)
    if not config:
        logger.warning("系统配置 %s 不存在，无法更新", key)
        raise HTTPException(status_code=404, detail="配置项不存在")
    logger.info("管理员部分更新系统配置：%s", key)
    return config


@router.delete("/system-configs/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_system_config(
    key: str,
    service: ConfigService = Depends(get_config_service),
    _: None = Depends(get_current_admin),
) -> None:
    deleted = await service.remove_config(key)
    if not deleted:
        logger.warning("系统配置 %s 不存在，无法删除", key)
        raise HTTPException(status_code=404, detail="配置项不存在")
    logger.info("管理员删除系统配置：%s", key)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChangeRequest,
    current_admin=Depends(get_current_admin),
    service: AuthService = Depends(get_auth_service),
) -> None:
    await service.change_password(current_admin.username, payload.old_password, payload.new_password)
    logger.info("管理员 %s 修改密码", current_admin.username)


@router.post("/test-gemini-rag", response_model=GeminiRAGTestResult)
async def test_gemini_rag(
    request: GeminiRAGTestRequest = GeminiRAGTestRequest(),
    session: AsyncSession = Depends(get_session),
    _: None = Depends(get_current_admin),
) -> GeminiRAGTestResult:
    """
    测试 Gemini RAG 配置是否正确

    测试项：
    1. 检查 API Key 是否配置
    2. 验证 API Key 是否有效（尝试列出 Corpus）
    3. 检查 RAG Provider 配置
    4. 可选：测试指定项目的 Corpus 访问

    需要管理员权限
    """
    try:
        from ...services.gemini_rag_service import GeminiRAGService
        from ...repositories.system_config_repository import SystemConfigRepository
        import os

        repo = SystemConfigRepository(session)

        # 1. 检查 rag.provider 配置
        rag_provider_record = await repo.get_by_key("rag.provider")
        rag_provider = rag_provider_record.value if rag_provider_record else os.getenv("RAG_PROVIDER", "libsql")

        # 2. 检查 API Key 是否配置
        api_key_record = await repo.get_by_key("gemini.api_key")
        api_key = api_key_record.value if api_key_record else os.getenv("GEMINI_API_KEY")

        api_key_configured = bool(api_key and api_key.strip())

        if not api_key_configured:
            return GeminiRAGTestResult(
                success=False,
                message="未配置 Gemini API Key",
                api_key_configured=False,
                api_key_valid=False,
                provider=rag_provider.strip().lower(),
                error_detail="请在系统配置中设置 gemini.api_key"
            )

        # 3. 测试 API Key 是否有效
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key.strip())

            # 尝试列出 Corpus（测试权限）
            corpora_list = list(genai.list_corpora())
            corpus_count = len(corpora_list)

            api_key_valid = True
            test_message = f"✅ Gemini API Key 有效！已连接到 Google AI，找到 {corpus_count} 个 Corpus"

            # 4. 可选：测试指定项目的 Corpus 访问
            corpus_accessible = None
            if request.test_project_id:
                gemini_service = GeminiRAGService(db_session=session)
                corpus_name = await gemini_service.ensure_corpus(request.test_project_id)

                if corpus_name:
                    corpus_accessible = True
                    test_message += f"\n✅ 项目 {request.test_project_id} 的 Corpus 可访问: {corpus_name}"
                else:
                    corpus_accessible = False
                    test_message += f"\n⚠️ 项目 {request.test_project_id} 的 Corpus 创建/访问失败"

            logger.info("管理员测试 Gemini RAG: 成功")

            return GeminiRAGTestResult(
                success=True,
                message=test_message,
                api_key_configured=True,
                api_key_valid=True,
                provider=rag_provider.strip().lower(),
                corpus_accessible=corpus_accessible
            )

        except ImportError:
            logger.error("google-generativeai 依赖未安装")
            return GeminiRAGTestResult(
                success=False,
                message="❌ 缺少 google-generativeai 依赖",
                api_key_configured=True,
                api_key_valid=False,
                provider=rag_provider.strip().lower(),
                error_detail="请运行: pip install google-generativeai"
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Gemini API Key 验证失败: {error_msg}")

            # 判断是权限问题还是Key无效
            if "PERMISSION_DENIED" in error_msg or "API key not valid" in error_msg:
                return GeminiRAGTestResult(
                    success=False,
                    message="❌ Gemini API Key 无效或权限不足",
                    api_key_configured=True,
                    api_key_valid=False,
                    provider=rag_provider.strip().lower(),
                    error_detail=f"错误详情: {error_msg}"
                )
            else:
                return GeminiRAGTestResult(
                    success=False,
                    message=f"❌ Gemini 连接测试失败",
                    api_key_configured=True,
                    api_key_valid=False,
                    provider=rag_provider.strip().lower(),
                    error_detail=f"错误详情: {error_msg}"
                )

    except Exception as e:
        logger.error(f"测试 Gemini RAG 时发生异常: {e}", exc_info=True)
        return GeminiRAGTestResult(
            success=False,
            message=f"❌ 测试过程发生异常",
            api_key_configured=False,
            api_key_valid=False,
            provider="unknown",
            error_detail=str(e)
        )
