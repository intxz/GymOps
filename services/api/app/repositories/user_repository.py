from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.user import User


def get_by_telegram_user_id(db: Session, telegram_user_id: int) -> User | None:
    stmt = select(User).where(User.telegram_user_id == telegram_user_id)
    return db.execute(stmt).scalar_one_or_none()


def get_or_create(db: Session, telegram_user_id: int, username: str | None = None) -> User:
    user = get_by_telegram_user_id(db=db, telegram_user_id=telegram_user_id)
    if user is not None:
        if username and username != user.username:
            user.username = username
            db.add(user)
            db.flush()
        return user

    user = User(telegram_user_id=telegram_user_id, username=username)
    db.add(user)
    try:
        db.flush()
        return user
    except IntegrityError:
        db.rollback()
        # Handles concurrent create race on unique telegram_user_id.
        existing = get_by_telegram_user_id(db=db, telegram_user_id=telegram_user_id)
        if existing is None:
            raise
        return existing
