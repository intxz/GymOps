from datetime import date, datetime
from enum import Enum

from sqlalchemy import Date, DateTime, Enum as SqlEnum, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MesocycleStatus(str, Enum):
    active = "active"
    completed = "completed"
    cancelled = "cancelled"


class Mesocycle(Base):
    __tablename__ = "mesocycles"
    __table_args__ = (
        Index(
            "uq_one_active_mesocycle_per_user",
            "user_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    goal: Mapped[str] = mapped_column(String(64), nullable=False, default="mixto")  # fuerza, hipertrofia, mixto
    weeks_total: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[MesocycleStatus] = mapped_column(
        SqlEnum(MesocycleStatus, native_enum=False), nullable=False, default=MesocycleStatus.active
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class MesocycleWeek(Base):
    __tablename__ = "mesocycle_weeks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mesocycle_id: Mapped[int] = mapped_column(ForeignKey("mesocycles.id"), nullable=False, index=True)
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    phase: Mapped[str] = mapped_column(String(64), nullable=False, default="accumulation")
    target_volume: Mapped[float | None] = mapped_column(Integer, nullable=True)  # kg objetivo de volumen efectivo total
    target_rpe_range: Mapped[str | None] = mapped_column(String(32), nullable=True, default="7-8")
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
