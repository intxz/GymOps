from pydantic import BaseModel
from datetime import datetime


class ExerciseStatsResponse(BaseModel):
    exercise_name: str
    normalized_exercise_name: str
    total_sets: int
    effective_sets: int
    warmup_sets: int
    total_volume: float
    effective_volume: float
    best_weight: float | None
    best_volume_set: float | None
    avg_rpe_effective: float | None


class ExerciseHistoryEntry(BaseModel):
    session_id: int
    performed_at: datetime
    exercise_name: str
    normalized_exercise_name: str
    weight: float
    reps: int
    rpe: float
    is_warmup: bool
    volume: float
    estimated_1rm: float | None


class ExerciseHistoryResponse(BaseModel):
    exercise_name: str
    normalized_exercise_name: str
    entries: list[ExerciseHistoryEntry]
