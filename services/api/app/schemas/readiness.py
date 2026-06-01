from datetime import date, datetime

from pydantic import BaseModel, Field


class ReadinessEntryRequest(BaseModel):
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    stress_level: int | None = Field(default=None, ge=1, le=10)
    soreness: int | None = Field(default=None, ge=1, le=10)
    body_weight: float | None = Field(default=None, gt=0)
    notes: str | None = None


class ReadinessEntryResponse(BaseModel):
    id: int
    user_id: int
    date: date
    sleep_hours: float | None = None
    stress_level: int | None = None
    soreness: int | None = None
    body_weight: float | None = None
    readiness_score: int | None = None
    notes: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class ReadinessScoreResponse(BaseModel):
    score: int | None
    date: date | None
    sleep_hours: float | None = None
    stress_level: int | None = None
    soreness: int | None = None
    interpretation: str = ""
    recent_entries: list[ReadinessEntryResponse] = Field(default_factory=list)
