from datetime import datetime

from pydantic import BaseModel, Field


class SetLine(BaseModel):
    weight: float
    reps: int
    rpe: float
    is_warmup: bool
    volume: float
    is_pr: bool


class ExerciseSummary(BaseModel):
    exercise_name: str
    warmup_sets: list[SetLine]
    effective_sets: list[SetLine]
    volume_total: float
    volume_effective: float
    top_set: SetLine | None
    pr_achieved: bool


class ExerciseHistoryLine(BaseModel):
    performed_at: datetime
    exercise_name: str
    weight: float
    reps: int
    rpe: float
    is_warmup: bool
    volume: float
    estimated_1rm: float | None


class WorkoutSummaryResponse(BaseModel):
    session_id: int
    user_id: int
    status: str
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int
    total_sets: int
    effective_sets: int
    warmup_sets: int
    volume_total: float
    volume_effective: float
    exercises: list[ExerciseSummary]
    exercise_history: list[ExerciseHistoryLine] = Field(default_factory=list)
    observations: list[str]
    recommendations: list[str]
    analysis_source: str = "local_rules"
    ai_enabled: bool = False
    ai_model: str | None = None
    ai_observations: list[str] = Field(default_factory=list)
    ai_recommendations: list[str] = Field(default_factory=list)
