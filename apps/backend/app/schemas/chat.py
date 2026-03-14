from datetime import datetime

from pydantic import BaseModel


class ChatMessageResponse(BaseModel):
    id: str
    thread_id: str
    role: str
    content: str
    source_record_id: str | None = None
    created_at: datetime


class ChatThreadSummaryResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime
    message_count: int
    last_message_preview: str | None = None


class ChatThreadListResponse(BaseModel):
    threads: list[ChatThreadSummaryResponse]


class ChatThreadDetailResponse(BaseModel):
    thread: ChatThreadSummaryResponse
    messages: list[ChatMessageResponse]
