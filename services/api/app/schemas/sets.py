from pydantic import BaseModel, Field


class SetCreateRequest(BaseModel):
    telegram_user_id: int = Field(gt=0)
    exercise_name: str = Field(min_length=1, max_length=100)
    weight: float = Field(ge=0)
    reps: int = Field(gt=0)
    rpe: float = Field(ge=0, le=10)


class SetCreateResponse(BaseModel):
    set_id: int
    session_id: int
    exercise_name: str
    normalized_exercise_name: str
    weight: float
    reps: int
    rpe: float
    is_warmup: bool
    message: str
    effective_set_count_for_exercise: int
    warmup_set_count_for_exercise: int

