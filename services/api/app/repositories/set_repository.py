from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db.models.set_entry import SetEntry
from app.db.models.workout_session import WorkoutSession, WorkoutStatus


def create_set(
    db: Session,
    workout_session_id: int,
    exercise_id: int,
    weight: float,
    reps: int,
    rpe: float,
    is_warmup: bool,
) -> SetEntry:
    set_entry = SetEntry(
        workout_session_id=workout_session_id,
        exercise_id=exercise_id,
        weight=weight,
        reps=reps,
        rpe=rpe,
        is_warmup=is_warmup,
    )
    db.add(set_entry)
    db.flush()
    return set_entry


def get_by_session_id(db: Session, workout_session_id: int) -> list[SetEntry]:
    stmt = select(SetEntry).where(SetEntry.workout_session_id == workout_session_id).order_by(SetEntry.id.asc())
    return list(db.execute(stmt).scalars().all())


def count_for_session_exercise(db: Session, workout_session_id: int, exercise_id: int) -> tuple[int, int]:
    stmt = (
        select(
            func.sum(case((SetEntry.is_warmup.is_(False), 1), else_=0)).label("effective_count"),
            func.sum(case((SetEntry.is_warmup.is_(True), 1), else_=0)).label("warmup_count"),
        )
        .where(SetEntry.workout_session_id == workout_session_id, SetEntry.exercise_id == exercise_id)
    )
    row = db.execute(stmt).one()
    return int(row.effective_count or 0), int(row.warmup_count or 0)


def get_historical_best_effective_set_volume(
    db: Session, user_id: int, exercise_id: int, exclude_session_id: int
) -> float | None:
    stmt = (
        select(func.max(SetEntry.weight * SetEntry.reps))
        .join(WorkoutSession, WorkoutSession.id == SetEntry.workout_session_id)
        .where(
            WorkoutSession.user_id == user_id,
            WorkoutSession.status == WorkoutStatus.completed,
            SetEntry.exercise_id == exercise_id,
            SetEntry.is_warmup.is_(False),
            SetEntry.workout_session_id != exclude_session_id,
        )
    )
    return db.execute(stmt).scalar_one_or_none()
