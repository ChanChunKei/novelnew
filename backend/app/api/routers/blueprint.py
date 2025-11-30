"""
蓝图自动生成API路由
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...schemas.user import UserInDB
from ...services.blueprint_generator_service import BlueprintGeneratorService
from ...services.novel_service import NovelService
from ...schemas.novel import NovelProjectSchema

router = APIRouter(prefix="/blueprint", tags=["blueprint"])


# ==================== Request/Response Models ====================

class CreativeInput(BaseModel):
    """创意扩展模式的输入"""
    idea: str = Field(..., description="核心创意（一句话或一段话）")
    genre: Optional[str] = Field("玄幻", description="题材类型")
    style: Optional[str] = Field("爽文", description="风格偏好")
    target_length: Optional[str] = Field("200万字", description="目标长度")


class ReferenceBook(BaseModel):
    """参考书信息"""
    type: str = Field(..., description="类型：book_name 或 upload")
    content: str = Field(..., description="书名或上传的文本内容")


class ReferenceInput(BaseModel):
    """参考学习模式的输入"""
    reference_book: ReferenceBook = Field(..., description="参考书信息")
    custom_requirements: Optional[str] = Field(None, description="自定义要求")


class AutoGenerateRequest(BaseModel):
    """蓝图自动生成请求"""
    mode: str = Field(..., description="模式：creative 或 reference")
    creative_input: Optional[CreativeInput] = None
    reference_input: Optional[ReferenceInput] = None
    project_name: Optional[str] = Field(None, description="项目名称（可选，默认从创意中提取）")


class PlagiarismCheck(BaseModel):
    """抄袭检测结果"""
    passed: bool
    overall_similarity: float
    name_similarity: float
    text_similarity: float
    details: str


class AutoGenerateResponse(BaseModel):
    """蓝图自动生成响应"""
    project_id: str
    mode: str
    blueprint: Dict
    meta_features: Optional[Dict] = None
    plagiarism_check: Optional[PlagiarismCheck] = None


# ==================== API Endpoints ====================

@router.post("/auto-generate", response_model=AutoGenerateResponse)
async def auto_generate_blueprint(
    request: AutoGenerateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """
    自动生成小说蓝图

    支持两种模式：
    1. creative: 基于简短创意扩展生成完整蓝图
    2. reference: 基于参考书提取元特征并生成原创蓝图
    """
    # 验证输入
    if request.mode == "creative":
        if not request.creative_input:
            raise HTTPException(status_code=400, detail="creative_input is required for creative mode")
    elif request.mode == "reference":
        if not request.reference_input:
            raise HTTPException(status_code=400, detail="reference_input is required for reference mode")
    elif request.mode == "agent":
        if not request.creative_input:
            raise HTTPException(status_code=400, detail="creative_input is required for agent mode")
    else:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {request.mode}")

    try:
        # 初始化服务
        generator_service = BlueprintGeneratorService(session)
        novel_service = NovelService(session)

        # 生成蓝图
        result = await generator_service.generate_blueprint(
            mode=request.mode,
            user_id=current_user.id,
            creative_input=request.creative_input.dict() if request.creative_input else None,
            reference_input=request.reference_input.dict() if request.reference_input else None,
        )

        # 提取项目名称
        if request.project_name:
            project_name = request.project_name
        elif request.mode == "creative" and request.creative_input:
            # 从创意中提取前20个字作为项目名
            project_name = request.creative_input.idea[:20]
        else:
            project_name = "AI生成的小说"

        # 创建项目并保存蓝图
        project = await novel_service.create_project_with_blueprint(
            user_id=current_user.id,
            title=project_name,
            blueprint_data=result["blueprint"]
        )

        # 构建响应
        response = AutoGenerateResponse(
            project_id=project.id,
            mode=result["mode"],
            blueprint=result["blueprint"],
            meta_features=result.get("meta_features"),
            plagiarism_check=PlagiarismCheck(**result["plagiarism_check"]) if "plagiarism_check" in result else None
        )

        return response

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成蓝图失败: {str(e)}")


@router.get("/reference-books")
async def list_reference_books(
    current_user: UserInDB = Depends(get_current_user),
):
    """
    获取可用的参考书列表

    返回内置的经典网文信息，供用户选择
    """
    reference_books = [
        {
            "name": "斗破苍穹",
            "genre": "东方玄幻",
            "style": "热血爽文",
            "description": "天才少年萧炎因家族变故跌入谷底，后凭借神秘戒指中的药老指导重新崛起的故事"
        },
        {
            "name": "遮天",
            "genre": "东方玄幻",
            "style": "史诗宏大",
            "description": "地球青年叶凡意外来到修行世界，以凡体踏上成帝之路的故事"
        },
        {
            "name": "凡人修仙传",
            "genre": "仙侠修真",
            "style": "谨慎流",
            "description": "普通山村少年韩立凭借坚韧意志和谨慎性格在修仙界一步步成长的故事"
        }
    ]

    return {"reference_books": reference_books}
