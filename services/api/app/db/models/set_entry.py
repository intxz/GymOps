from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SetEntry(Base):
    __tablename__ = "set_entries"
    __table_args__ = (
        CheckConstraint("weight >= 0", name="ck_set_entries_weight_nonnegative"),
        CheckConstraint("reps > 0", name="ck_set_entries_reps_positive"),
        CheckConstraint("rpe >= 0 AND rpe <= 10", name="ck_set_entries_rpe_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workout_session_id: Mapped[int] = mapped_column(ForeignKey("workout_sessions.id"), nullable=False, index=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"), nullable=False, index=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    reps: Mapped[int] = mapped_column(Integer, nullable=False)
    rpe: Mapped[float] = mapped_column(Float, nullable=False)
    is_warmup: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
