"""
Gemini Semantic Retrieval API 集成服务

使用 Google Gemini 的 Semantic Retrieval API 实现零配置向量搜索。
相比传统向量库方案，优势：
1. 无需自建向量数据库（libsql/Milvus/ChromaDB）
2. 无需手动调用 embedding API
3. Google 全托管，自动扩展
4. 免费额度充足（1500次/天）

技术架构：
- Corpus: 项目级语料库（一个小说项目 = 一个 Corpus）
- Document: 章节文档（一章 = 一个 Document）
- Chunk: 自动分块（Google 自动处理）
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
except ImportError:
    genai = None  # type: ignore[assignment]
    logger.warning("未安装 google-generativeai，Gemini RAG 功能不可用")


@dataclass
class GeminiSearchResult:
    """Gemini 搜索结果"""

    chapter_number: int
    chapter_title: str
    content_snippet: str
    relevance_score: float
    metadata: Dict[str, Any]


class GeminiRAGService:
    """
    Gemini Semantic Retrieval 服务

    使用场景：
    1. 章节生成后自动入库：add_chapter()
    2. search_chapters 工具调用：search()
    3. 项目删除时清理：delete_corpus()

    配置优先级：
    1. 数据库 SystemConfig 表（gemini.api_key, rag.provider）
    2. 环境变量（GEMINI_API_KEY, RAG_PROVIDER）
    """

    def __init__(self, db_session: Optional["AsyncSession"] = None):
        """
        初始化 Gemini RAG 服务

        Args:
            db_session: 数据库会话，用于读取配置
        """
        if not genai:
            raise RuntimeError("缺少 google-generativeai 依赖，请先安装：pip install google-generativeai")

        self._db_session = db_session
        self._enabled = False
        self._api_key: Optional[str] = None

    async def _ensure_configured(self) -> bool:
        """
        确保服务已配置

        从数据库或环境变量读取配置
        """
        if self._enabled:
            return True

        # 1. 尝试从数据库读取配置
        api_key = await self._get_api_key()

        if not api_key:
            logger.debug("未配置 Gemini API Key，RAG 功能不可用")
            return False

        try:
            genai.configure(api_key=api_key)
            self._enabled = True
            self._api_key = api_key
            logger.info("✅ Gemini RAG 服务初始化成功")
            return True
        except Exception as e:
            logger.error(f"❌ Gemini RAG 初始化失败: {e}")
            return False

    async def _get_api_key(self) -> Optional[str]:
        """
        获取 Gemini API Key

        优先级：
        1. 数据库 system_configs 表（gemini.api_key）
        2. 环境变量（GEMINI_API_KEY）
        """
        # 优先从数据库读取
        if self._db_session:
            try:
                from ..repositories.system_config_repository import SystemConfigRepository
                repo = SystemConfigRepository(self._db_session)
                record = await repo.get_by_key("gemini.api_key")
                if record and record.value:
                    return record.value.strip()
            except Exception as e:
                logger.warning(f"从数据库读取 Gemini API Key 失败: {e}")

        # 回退到环境变量
        return os.getenv("GEMINI_API_KEY")

    async def _get_rag_provider(self) -> str:
        """
        获取 RAG 提供方配置

        优先级：
        1. 数据库 system_configs 表（rag.provider）
        2. 环境变量（RAG_PROVIDER）
        3. 默认值（libsql）
        """
        # 优先从数据库读取
        if self._db_session:
            try:
                from ..repositories.system_config_repository import SystemConfigRepository
                repo = SystemConfigRepository(self._db_session)
                record = await repo.get_by_key("rag.provider")
                if record and record.value:
                    return record.value.strip().lower()
            except Exception as e:
                logger.warning(f"从数据库读取 RAG Provider 失败: {e}")

        # 回退到环境变量
        provider = os.getenv("RAG_PROVIDER", "libsql")
        return provider.strip().lower()

    @property
    def enabled(self) -> bool:
        """RAG 服务是否可用"""
        return self._enabled

    def _get_corpus_name(self, project_id: str) -> str:
        """
        生成 Corpus 名称

        格式：corpora/novel-project-{project_id}
        注意：Gemini API 要求 display_name 必须唯一
        """
        return f"novel-project-{project_id}"

    async def ensure_corpus(self, project_id: str) -> Optional[str]:
        """
        确保项目的 Corpus 存在，不存在则创建

        Args:
            project_id: 小说项目ID

        Returns:
            corpus_name: Corpus 资源名称，格式 corpora/xxx
        """
        if not await self._ensure_configured():
            return None

        display_name = self._get_corpus_name(project_id)

        try:
            # 1. 尝试列出所有 corpus，查找是否已存在
            for corpus in genai.list_corpora():
                if corpus.display_name == display_name:
                    logger.info(f"📚 找到已存在的 Corpus: {corpus.name}")
                    return corpus.name

            # 2. 不存在则创建新 corpus
            corpus = genai.create_corpus(display_name=display_name)
            logger.info(f"✅ 创建 Corpus 成功: {corpus.name}")
            return corpus.name

        except Exception as e:
            logger.error(f"❌ 确保 Corpus 存在失败: {e}")
            return None

    async def add_chapter(
        self,
        project_id: str,
        chapter_number: int,
        chapter_title: str,
        content: str,
        summary: Optional[str] = None,
    ) -> bool:
        """
        添加章节到 Gemini Corpus

        Args:
            project_id: 项目ID
            chapter_number: 章节编号
            chapter_title: 章节标题
            content: 章节完整内容
            summary: 章节摘要（可选）

        Returns:
            bool: 是否成功
        """
        if not await self._ensure_configured():
            logger.debug("Gemini RAG 未启用，跳过章节入库")
            return False

        corpus_name = await self.ensure_corpus(project_id)
        if not corpus_name:
            return False

        try:
            # 构建文档内容：标题 + 摘要 + 正文
            document_content = f"# {chapter_title}\n\n"
            if summary:
                document_content += f"【摘要】{summary}\n\n"
            document_content += content

            # 创建文档
            document = genai.create_document(
                corpus_name=corpus_name,
                display_name=f"第{chapter_number}章",
                custom_metadata=[
                    {"key": "chapter_number", "numeric_value": float(chapter_number)},
                    {"key": "chapter_title", "string_value": chapter_title},
                ],
                parts=[{"text": document_content}],
            )

            logger.info(f"✅ 章节入库成功: 第{chapter_number}章 {chapter_title}")
            return True

        except Exception as e:
            logger.error(f"❌ 章节入库失败（第{chapter_number}章）: {e}")
            return False

    async def search(
        self,
        project_id: str,
        query: str,
        top_k: int = 5,
    ) -> List[GeminiSearchResult]:
        """
        在项目语料库中搜索相关章节

        Args:
            project_id: 项目ID
            query: 搜索查询（自然语言）
            top_k: 返回结果数量

        Returns:
            搜索结果列表
        """
        if not await self._ensure_configured():
            logger.debug("Gemini RAG 未启用，返回空结果")
            return []

        corpus_name = await self.ensure_corpus(project_id)
        if not corpus_name:
            return []

        try:
            # 调用 Gemini Semantic Retrieval API
            results = genai.query_corpus(
                corpus_name=corpus_name,
                query=query,
                results_count=top_k,
                metadata_filters=[],  # 可以添加过滤条件，如章节范围
            )

            # 解析结果
            search_results = []
            for item in results:
                # 提取元数据
                chapter_number = 0
                chapter_title = "未知章节"

                if hasattr(item, 'document') and item.document:
                    doc = item.document
                    # 从 custom_metadata 提取
                    if hasattr(doc, 'custom_metadata'):
                        for meta in doc.custom_metadata:
                            if meta.key == "chapter_number":
                                chapter_number = int(meta.numeric_value)
                            elif meta.key == "chapter_title":
                                chapter_title = meta.string_value

                    # 从 display_name 提取（备用）
                    if chapter_number == 0 and hasattr(doc, 'display_name'):
                        import re
                        match = re.search(r'第(\d+)章', doc.display_name)
                        if match:
                            chapter_number = int(match.group(1))

                # 提取内容片段
                content_snippet = ""
                if hasattr(item, 'chunk') and item.chunk:
                    chunk = item.chunk
                    if hasattr(chunk, 'data'):
                        if hasattr(chunk.data, 'string_value'):
                            content_snippet = chunk.data.string_value
                        elif hasattr(chunk.data, 'text'):
                            content_snippet = chunk.data.text

                # 提取相关度分数
                relevance_score = 0.0
                if hasattr(item, 'score'):
                    relevance_score = float(item.score)

                search_results.append(GeminiSearchResult(
                    chapter_number=chapter_number,
                    chapter_title=chapter_title,
                    content_snippet=content_snippet[:500],  # 限制长度
                    relevance_score=relevance_score,
                    metadata={"raw_item": str(item)},
                ))

            logger.info(f"🔍 搜索完成: 查询='{query}', 结果数={len(search_results)}")
            return search_results

        except Exception as e:
            logger.error(f"❌ 搜索失败: query='{query}', error={e}")
            return []

    async def delete_corpus(self, project_id: str) -> bool:
        """
        删除项目的 Corpus（项目删除时调用）

        Args:
            project_id: 项目ID

        Returns:
            bool: 是否成功
        """
        if not await self._ensure_configured():
            return False

        display_name = self._get_corpus_name(project_id)

        try:
            # 查找 corpus
            for corpus in genai.list_corpora():
                if corpus.display_name == display_name:
                    genai.delete_corpus(name=corpus.name)
                    logger.info(f"🗑️  删除 Corpus 成功: {corpus.name}")
                    return True

            logger.warning(f"⚠️  未找到 Corpus: {display_name}")
            return False

        except Exception as e:
            logger.error(f"❌ 删除 Corpus 失败: {e}")
            return False

    async def delete_chapter(
        self,
        project_id: str,
        chapter_number: int,
    ) -> bool:
        """
        删除单个章节（章节重生成时调用）

        Args:
            project_id: 项目ID
            chapter_number: 章节编号

        Returns:
            bool: 是否成功
        """
        if not await self._ensure_configured():
            return False

        corpus_name = await self.ensure_corpus(project_id)
        if not corpus_name:
            return False

        try:
            # 列出该 corpus 下的所有文档
            documents = genai.list_documents(corpus_name=corpus_name)

            for doc in documents:
                # 检查元数据
                if hasattr(doc, 'custom_metadata'):
                    for meta in doc.custom_metadata:
                        if meta.key == "chapter_number" and int(meta.numeric_value) == chapter_number:
                            genai.delete_document(name=doc.name)
                            logger.info(f"🗑️  删除章节成功: 第{chapter_number}章")
                            return True

            logger.warning(f"⚠️  未找到章节: 第{chapter_number}章")
            return False

        except Exception as e:
            logger.error(f"❌ 删除章节失败（第{chapter_number}章）: {e}")
            return False


__all__ = ["GeminiRAGService", "GeminiSearchResult"]
