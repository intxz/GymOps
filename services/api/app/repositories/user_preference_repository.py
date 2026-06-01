from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.coach_profile import UserPreference


def get_by_user_id(db: Session, user_id: int) -> UserPreference | None:
    stmt = select(UserPreference).where(UserPreference.user_id == user_id)
    return db.execute(stmt).scalar_one_or_none()


def get_or_create(db: Session, user_id: int) -> UserPreference:
    pref = get_by_user_id(db=db, user_id=user_id)
    if pref is not None:
        return pref
    pref = UserPreference(user_id=user_id)
    db.add(pref)
    db.flush()
    return pref


def set_coach(db: Session, user_id: int, coach_id: int | None) -> UserPreference:
    pref = get_or_create(db=db, user_id=user_id)
    pref.selected_coach_id = coach_id
    db.add(pref)
    db.commit()
    db.refresh(pref)
    return pref
