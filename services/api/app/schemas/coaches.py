from pydantic import BaseModel, Field


class CoachProfileResponse(BaseModel):
    id: int
    slug: str
    name: str
    description: str
    scientific_basis: str
    emoji: str = Field(default="🤖")
    is_builtin: bool = True

    class Config:
        from_attributes = True


class CoachListResponse(BaseModel):
    coaches: list[CoachProfileResponse]


class CoachSelectionRequest(BaseModel):
    coach_slug: str | None = None


class CoachSelectionResponse(BaseModel):
    message: str
    selected_coach: CoachProfileResponse | None = None


class UserCoachResponse(BaseModel):
    user_id: int
    selected_coach: CoachProfileResponse | None = None
    privacy_mode: str = "private"

    class Config:
        from_attributes = True
