from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.daily_readiness import DailyReadiness


def get_latest(db: Session, user_id: int) -> DailyReadiness | None:
    stmt = (
        select(DailyReadiness)
        .where(DailyReadiness.user_id == user_id)
        .order_by(DailyReadiness.date.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def get_by_date(db: Session, user_id: int, entry_date: date) -> DailyReadiness | None:
    stmt = select(DailyReadiness).where(
        DailyReadiness.user_id == user_id,
        DailyReadiness.date == entry_date,
    )
    return db.execute(stmt).scalar_one_or_none()


def create_or_update(
    db: Session,
    user_id: int,
    entry_date: date,
    sleep_hours: float | None,
    stress_level: int | None,
    soreness: int | None,
    body_weight: float | None,
    notes: str | None,
    readiness_score: int | None,
) -> DailyReadiness:
    existing = get_by_date(db=db, user_id=user_id, entry_date=entry_date)
    if existing is not None:
        existing.sleep_hours = sleep_hours
        existing.stress_level = stress_level
        existing.soreness = soreness
        existing.body_weight = body_weight
        existing.notes = notes
        existing.readiness_score = readiness_score
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    entry = DailyReadiness(
        user_id=user_id,
        date=entry_date,
        sleep_hours=sleep_hours,
        stress_level=stress_level,
        soreness=soreness,
        body_weight=body_weight,
        notes=notes,
        readiness_score=readiness_score,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_last_n_days(db: Session, user_id: int, days: int) -> list[DailyReadiness]:
    since = date.today() - timedelta(days=days)
    stmt = (
        select(DailyReadiness)
        .where(DailyReadiness.user_id == user_id, DailyReadiness.date >= since)
        .order_by(DailyReadiness.date.desc())
    )
    return list(db.execute(stmt).scalars().all())
