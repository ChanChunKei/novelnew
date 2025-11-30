from fastapi import APIRouter

from . import admin, auth, auto_generator, llm_config, novels, updates, writer, async_analysis, ai_routing, volume_management, scheduled_generator, blueprint, discussion_mode

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(novels.router)
api_router.include_router(writer.router)
api_router.include_router(admin.router)
api_router.include_router(updates.router)
api_router.include_router(llm_config.router)
api_router.include_router(auto_generator.router)
# ✅ 注册异步分析路由
api_router.include_router(async_analysis.router)
# ✅ 注册AI路由管理
api_router.include_router(ai_routing.router)
# ✅ 注册分卷管理路由
api_router.include_router(volume_management.router)
# ✅ 注册定时自动生成器路由
api_router.include_router(scheduled_generator.router)
# ✅ 注册蓝图自动生成路由
api_router.include_router(blueprint.router)
# ✅ 注册讨论模式路由
api_router.include_router(discussion_mode.router)
