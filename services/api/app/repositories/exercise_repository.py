from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.exercise import Exercise


def get_by_normalized_name(db: Session, normalized_name: str) -> Exercise | None:
    stmt = select(Exercise).where(Exercise.normalized_name == normalized_name)
    return db.execute(stmt).scalar_one_or_none()


def get_or_create(db: Session, raw_name: str, normalized_name: str) -> Exercise:
    exercise = get_by_normalized_name(db=db, normalized_name=normalized_name)
    if exercise is not None:
        return exercise

    exercise = Exercise(name=raw_name, normalized_name=normalized_name)
    db.add(exercise)
    try:
        db.flush()
        return exercise
    except IntegrityError:
        db.rollback()
        # Handles concurrent create race on unique normalized_name.
        existing = get_by_normalized_name(db=db, normalized_name=normalized_name)
        if existing is None:
            raise
        return existing
