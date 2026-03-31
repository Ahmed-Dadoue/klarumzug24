from typing import Literal

from pydantic import BaseModel, Field

from app.ai.schemas import ChatLanguage


class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class ChatRequestIn(BaseModel):
    messages: list[ChatMessageIn] = Field(min_length=1, max_length=20)
    page: str | None = Field(default=None, max_length=200)
    lang: ChatLanguage = "de"
    conversation_id: str | None = Field(default=None, max_length=80)
