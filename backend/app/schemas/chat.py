from typing import Literal

from pydantic import BaseModel, Field

from app.ai.schemas import ChatLanguage

ConversationType = Literal["real_user", "test_script", "automated_test"]


class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class ChatRequestIn(BaseModel):
    messages: list[ChatMessageIn] = Field(min_length=1, max_length=20)
    page: str | None = Field(default=None, max_length=200)
    lang: ChatLanguage = "de"
    conversation_id: str | None = Field(default=None, max_length=80)
    conversation_type: ConversationType = "real_user"
    source_label: str | None = Field(default=None, max_length=80)
    test_run_id: str | None = Field(default=None, max_length=80)
    memory_review_required: bool | None = None
