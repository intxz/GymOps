from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.workout_session import WorkoutSession, WorkoutStatus


def get_active_by_user_id(db: Session, user_id: int) -> WorkoutSession | None:
    stmt = select(WorkoutSession).where(
        WorkoutSession.user_id == user_id,
        WorkoutSession.status == WorkoutStatus.active,
    )
    return db.execute(stmt).scalar_one_or_none()


def create_active(db: Session, user_id: int, started_at) -> WorkoutSession:
    session = WorkoutSession(user_id=user_id, started_at=started_at, status=WorkoutStatus.active)
    db.add(session)
    db.flush()
    return session


def get_by_id_for_user(db: Session, session_id: int, user_id: int) -> WorkoutSession | None:
    stmt = select(WorkoutSession).where(WorkoutSession.id == session_id, WorkoutSession.user_id == user_id)
    return db.execute(stmt).scalar_one_or_none()

