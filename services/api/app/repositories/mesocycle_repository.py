from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.mesocycle import Mesocycle, MesocycleStatus, MesocycleWeek


def get_active_by_user_id(db: Session, user_id: int) -> Mesocycle | None:
    stmt = (
        select(Mesocycle)
        .where(Mesocycle.user_id == user_id, Mesocycle.status == MesocycleStatus.active)
        .order_by(Mesocycle.start_date.desc())
    )
    return db.execute(stmt).scalar_one_or_none()


def get_by_id_for_user(db: Session, mesocycle_id: int, user_id: int) -> Mesocycle | None:
    stmt = select(Mesocycle).where(Mesocycle.id == mesocycle_id, Mesocycle.user_id == user_id)
    return db.execute(stmt).scalar_one_or_none()


def list_by_user(db: Session, user_id: int, limit: int = 10) -> list[Mesocycle]:
    stmt = (
        select(Mesocycle)
        .where(Mesocycle.user_id == user_id)
        .order_by(Mesocycle.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def create(
    db: Session,
    user_id: int,
    name: str,
    goal: str,
    weeks_total: int,
    start_date: date,
) -> Mesocycle:
    mesocycle = Mesocycle(
        user_id=user_id,
        name=name,
        goal=goal,
        weeks_total=weeks_total,
        start_date=start_date,
        status=MesocycleStatus.active,
    )
    db.add(mesocycle)
    db.flush()

    # Generate weeks with phases
    phases = _compute_phases(weeks_total)
    for i, phase in enumerate(phases, start=1):
        week_start = start_date + timedelta(weeks=i - 1)
        week_end = week_start + timedelta(days=6)
        week = MesocycleWeek(
            mesocycle_id=mesocycle.id,
            week_number=i,
            phase=phase,
            start_date=week_start,
            end_date=week_end,
            target_rpe_range=_rpe_range_for_phase(phase),
        )
        db.add(week)

    db.commit()
    db.refresh(mesocycle)
    return mesocycle


def complete(db: Session, mesocycle: Mesocycle) -> Mesocycle:
    mesocycle.status = MesocycleStatus.completed
    mesocycle.end_date = date.today()
    db.add(mesocycle)
    db.commit()
    db.refresh(mesocycle)
    return mesocycle


def cancel(db: Session, mesocycle: Mesocycle) -> Mesocycle:
    mesocycle.status = MesocycleStatus.cancelled
    db.add(mesocycle)
    db.commit()
    db.refresh(mesocycle)
    return mesocycle


def get_weeks(db: Session, mesocycle_id: int) -> list[MesocycleWeek]:
    stmt = select(MesocycleWeek).where(MesocycleWeek.mesocycle_id == mesocycle_id).order_by(MesocycleWeek.week_number)
    return list(db.execute(stmt).scalars().all())


def get_current_week(db: Session, mesocycle: Mesocycle) -> MesocycleWeek | None:
    today = date.today()
    stmt = (
        select(MesocycleWeek)
        .where(
            MesocycleWeek.mesocycle_id == mesocycle.id,
            MesocycleWeek.start_date <= today,
            MesocycleWeek.end_date >= today,
        )
        .order_by(MesocycleWeek.week_number)
    )
    return db.execute(stmt).scalar_one_or_none()


def _compute_phases(weeks_total: int) -> list[str]:
    """Generate phases for a mesocycle. Default block periodization."""
    if weeks_total <= 3:
        return ["accumulation"] * (weeks_total - 1) + ["intensification"]
    # Standard 4-week block
    accumulation = max(1, weeks_total // 2)
    intensification = max(1, (weeks_total - accumulation) // 2)
    deload = max(1, weeks_total - accumulation - intensification)
    phases: list[str] = []
    phases.extend(["accumulation"] * accumulation)
    phases.extend(["intensification"] * intensification)
    phases.extend(["deload"] * deload)
    # Trim or extend to match exact weeks_total
    while len(phases) < weeks_total:
        phases.append("accumulation")
    return phases[:weeks_total]


def _rpe_range_for_phase(phase: str) -> str:
    if phase == "accumulation":
        return "7-8"
    if phase == "intensification":
        return "8.5-9"
    if phase == "deload":
        return "6-7"
    if phase == "realization":
        return "8.5-9.5"
    return "7-8"
