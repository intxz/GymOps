from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.user import User


def get_by_telegram_user_id(db: Session, telegram_user_id: int) -> User | None:
    stmt = select(User).where(User.telegram_user_id == telegram_user_id)
    return db.execute(stmt).scalar_one_or_none()


def get_first_user(db: Session) -> User | None:
    stmt = select(User).order_by(User.created_at.asc()).limit(1)
    return db.execute(stmt).scalar_one_or_none()


def is_authorized(db: Session, telegram_user_id: int) -> bool:
    user = get_by_telegram_user_id(db=db, telegram_user_id=telegram_user_id)
    if user is None:
        return False
    return user.is_authorized


def is_admin(db: Session, telegram_user_id: int) -> bool:
    user = get_by_telegram_user_id(db=db, telegram_user_id=telegram_user_id)
    if user is None:
        return False
    return user.is_admin


def authorize_user(db: Session, telegram_user_id: int) -> User | None:
    user = get_by_telegram_user_id(db=db, telegram_user_id=telegram_user_id)
    if user is None:
        return None
    user.is_authorized = True
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


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
