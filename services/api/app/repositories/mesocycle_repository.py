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
    """Generate phases based on Nippard's 12-week Bodybuilding Transformation System."""
    # For 12 weeks: Foundation Block (5w) + Ramping Block (7w)
    if weeks_total == 12:
        return [
            "intro",          # Week 1: Foundation Block intro/deload
            "accumulation",   # Week 2: baseline volume
            "accumulation",   # Week 3
            "accumulation",   # Week 4
            "accumulation",   # Week 5: peak Foundation volume
            "intro",          # Week 6: Ramping Block intro/deload
            "ramping_1",      # Week 7: volume increases from baseline
            "ramping_1",      # Week 8
            "ramping_2",      # Week 9: volume increases again
            "ramping_2",      # Week 10
            "ramping_3",      # Week 11: final volume increase
            "ramping_3",      # Week 12: peak volume
        ]
    # Fallback to generic block periodization for other durations
    if weeks_total <= 3:
        return ["accumulation"] * (weeks_total - 1) + ["intensification"]
    accumulation = max(1, weeks_total // 2)
    intensification = max(1, (weeks_total - accumulation) // 2)
    deload = max(1, weeks_total - accumulation - intensification)
    phases: list[str] = []
    phases.extend(["accumulation"] * accumulation)
    phases.extend(["intensification"] * intensification)
    phases.extend(["deload"] * deload)
    while len(phases) < weeks_total:
        phases.append("accumulation")
    return phases[:weeks_total]


def _rpe_range_for_phase(phase: str) -> str:
    if phase == "intro":
        return "6-7"
    if phase == "accumulation":
        return "7-8"
    if phase in ("ramping_1", "ramping_2"):
        return "8-8.5"
    if phase == "ramping_3":
        return "8.5-9"
    if phase == "intensification":
        return "8.5-9"
    if phase == "deload":
        return "6-7"
    if phase == "realization":
        return "8.5-9.5"
    return "7-8"


def get_week_techniques(week_number: int, total_weeks: int) -> list[str]:
    """Return special training techniques for a given week (Nippard style)."""
    if total_weeks != 12:
        return []
    techniques: list[str] = []
    if week_number == 1:
        techniques.append("Semana intro: familiarízate con los ejercicios, no busques máximos.")
    elif week_number == 2:
        techniques.append("Técnica: myo-reps en el último set de ejercicios de aislamiento.")
    elif week_number == 3:
        techniques.append("Técnica: lengthened partials para extender el último set al fallo.")
    elif week_number == 4:
        techniques.append("Técnica: static stretch de 30s después del último set de calves.")
    elif week_number == 5:
        techniques.append("Pico Foundation: mantén la misma técnica, logra todas las reps.")
    elif week_number == 6:
        techniques.append("Semana intro Ramping: nuevos ejercicios, reduce volumen ~30%.")
    elif week_number == 7:
        techniques.append("Ramping ↑: vuelve al volumen de la semana 5.")
    elif week_number == 8:
        techniques.append("Ramping ↑↑: añade 1-2 sets por grupo muscular vs. semana 7.")
    elif week_number == 9:
        techniques.append("Ramping ↑↑↑: otro aumento de 1-2 sets. Prioriza compuestos.")
    elif week_number == 10:
        techniques.append("Ramping máximo: técnica myo-reps en último set.")
    elif week_number == 11:
        techniques.append("Pico de volumen: añade dropset o rest-pause en aislamiento.")
    elif week_number == 12:
        techniques.append("Pico del programa: empuja al límite controlado. RPE 8.5-9.")
    return techniques
