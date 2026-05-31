from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.summary import WorkoutSummaryResponse


class SessionActionRequest(BaseModel):
    telegram_user_id: int = Field(gt=0)


class StartSessionRequest(SessionActionRequest):
    username: str | None = Field(default=None, max_length=255)


class SessionInfo(BaseModel):
    id: int
    user_id: int
    started_at: datetime
    ended_at: datetime | None
    status: str
    duration_seconds: int | None


class ActiveSessionStatusResponse(BaseModel):
    has_active_session: bool
    session: SessionInfo | None
    duration_seconds: int
    exercises_count: int
    effective_sets: int
    warmup_sets: int


class SessionActionResponse(BaseModel):
    message: str
    session: SessionInfo


class EndSessionResponse(BaseModel):
    message: str
    session: SessionInfo
    summary: WorkoutSummaryResponse
