from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Index, Integer, text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class WorkoutStatus(str, Enum):
    active = "active"
    completed = "completed"
    cancelled = "cancelled"


class WorkoutSession(Base):
    __tablename__ = "workout_sessions"
    __table_args__ = (
        Index(
            "uq_one_active_session_per_user",
            "user_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[WorkoutStatus] = mapped_column(
        SqlEnum(WorkoutStatus, native_enum=False), nullable=False, default=WorkoutStatus.active
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mesocycle_week_id: Mapped[int | None] = mapped_column(ForeignKey("mesocycle_weeks.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
