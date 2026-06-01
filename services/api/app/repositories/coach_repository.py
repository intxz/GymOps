from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.coach_profile import CoachProfile, UserPreference


def get_builtin_coaches(db: Session) -> list[CoachProfile]:
    stmt = select(CoachProfile).where(CoachProfile.is_builtin.is_(True)).order_by(CoachProfile.id)
    return list(db.execute(stmt).scalars().all())


def get_by_slug(db: Session, slug: str) -> CoachProfile | None:
    stmt = select(CoachProfile).where(CoachProfile.slug == slug)
    return db.execute(stmt).scalar_one_or_none()


def get_by_id(db: Session, coach_id: int) -> CoachProfile | None:
    stmt = select(CoachProfile).where(CoachProfile.id == coach_id)
    return db.execute(stmt).scalar_one_or_none()
