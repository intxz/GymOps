from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CoachProfile(Base):
    __tablename__ = "coach_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    persona_prompt: Mapped[str] = mapped_column(String(4000), nullable=False)
    rules_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    scientific_basis: Mapped[str] = mapped_column(String(1000), nullable=False)
    emoji: Mapped[str] = mapped_column(String(16), nullable=False, default="🤖")
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class UserPreference(Base):
    __tablename__ = "user_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_preferences_user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    selected_coach_id: Mapped[int | None] = mapped_column(ForeignKey("coach_profiles.id"), nullable=True)
    privacy_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="private")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
