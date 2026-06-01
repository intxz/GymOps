from datetime import date, datetime

from pydantic import BaseModel, Field


class MesocycleWeekResponse(BaseModel):
    id: int
    week_number: int
    phase: str
    target_volume: int | None = None
    target_rpe_range: str | None = None
    start_date: date
    end_date: date

    class Config:
        from_attributes = True


class MesocycleResponse(BaseModel):
    id: int
    user_id: int
    name: str
    goal: str
    weeks_total: int
    start_date: date
    end_date: date | None = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class MesocycleDetailResponse(MesocycleResponse):
    weeks: list[MesocycleWeekResponse] = Field(default_factory=list)


class MesocycleListResponse(BaseModel):
    mesocycles: list[MesocycleResponse]


class CreateMesocycleRequest(BaseModel):
    name: str
    goal: str = "mixto"
    weeks_total: int = Field(default=4, ge=2, le=12)
    start_date: date | None = None  # Defaults to today


class CreateMesocycleResponse(BaseModel):
    message: str
    mesocycle: MesocycleDetailResponse


class ActiveMesocycleWeekResponse(BaseModel):
    mesocycle: MesocycleResponse
    current_week: MesocycleWeekResponse
    week_progress_text: str


class MesocycleActionResponse(BaseModel):
    message: str
    mesocycle: MesocycleResponse
