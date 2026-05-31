from pydantic import BaseModel


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

