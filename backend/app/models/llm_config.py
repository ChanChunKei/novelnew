from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class LLMConfig(Base):
    """用户自定义的 LLM 接入配置。

    llm_provider_api_key 字段存储多个 API Key，格式为逗号分隔的字符串
    例如：key1,key2,key3
    """

    __tablename__ = "llm_configs"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    llm_provider_url: Mapped[str | None] = mapped_column(Text())
    llm_provider_api_key: Mapped[str | None] = mapped_column(Text(), comment="多个 API Key，逗号分隔")
    llm_provider_model: Mapped[str | None] = mapped_column(Text())

    user: Mapped["User"] = relationship("User", back_populates="llm_config")
