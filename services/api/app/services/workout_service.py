import re
from collections import defaultdict
from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.exercise import Exercise
from app.db.models.set_entry import SetEntry
from app.db.models.workout_session import WorkoutSession, WorkoutStatus
from app.observability.metrics import (
    hydrate_training_exercise_metrics,
    record_session_cancelled,
    record_session_completed,
    record_session_started,
    record_set_added,
    record_summary_generated,
)
from app.repositories import coach_repository, exercise_repository, session_repository, set_repository, user_preference_repository, user_repository
from app.schemas.sessions import ActiveSessionStatusResponse, SessionInfo
from app.schemas.sets import SetCreateResponse
from app.schemas.stats import ExerciseHistoryEntry, ExerciseHistoryResponse, ExerciseStatsResponse
from app.schemas.summary import ExerciseHistoryLine, ExerciseSummary, SetLine, WorkoutSummaryResponse
from app.services.errors import ServiceError
from app.services.hermes_ai_service import enrich_exercise_history_with_hermes, enrich_summary_with_hermes_ai


_INVALID_EXERCISE_CHARS = re.compile(r"[^\w\s-]")
_SEPARATOR_PATTERN = re.compile(r"[\s-]+")
_MULTI_UNDERSCORE_PATTERN = re.compile(r"_+")
_LOWER_BODY_HINTS = (
    "sentadilla",
    "squat",
    "peso_muerto",
    "deadlift",
    "prensa",
    "hack_squat",
    "zancada",
    "lunge",
    "hip_thrust",
    "hipthrust",
)


def utc_now() -> datetime:
    return datetime.utcnow()


def hydrate_training_observability(db: Session) -> None:
    stats_stmt = (
        select(
            Exercise.normalized_name,
            func.sum(case((SetEntry.is_warmup.is_(False), 1), else_=0)),
            func.sum(case((SetEntry.is_warmup.is_(True), 1), else_=0)),
            func.sum(case((SetEntry.is_warmup.is_(False), SetEntry.weight * SetEntry.reps), else_=0.0)),
            func.max(case((SetEntry.is_warmup.is_(False), SetEntry.weight), else_=None)),
            func.max(case((SetEntry.is_warmup.is_(False), SetEntry.weight * (1 + SetEntry.reps / 30.0)), else_=None)),
        )
        .join(SetEntry, SetEntry.exercise_id == Exercise.id)
        .join(WorkoutSession, WorkoutSession.id == SetEntry.workout_session_id)
        .where(WorkoutSession.status == WorkoutStatus.completed)
        .group_by(Exercise.id)
    )

    for row in db.execute(stats_stmt).all():
        exercise_name = str(row[0])
        last_rpe_stmt = (
            select(SetEntry.rpe)
            .join(WorkoutSession, WorkoutSession.id == SetEntry.workout_session_id)
            .join(Exercise, Exercise.id == SetEntry.exercise_id)
            .where(
                Exercise.normalized_name == exercise_name,
                WorkoutSession.status == WorkoutStatus.completed,
                SetEntry.is_warmup.is_(False),
            )
            .order_by(WorkoutSession.ended_at.desc(), SetEntry.id.desc())
            .limit(1)
        )
        last_rpe = db.execute(last_rpe_stmt).scalar_one_or_none()
        hydrate_training_exercise_metrics(
            exercise=exercise_name,
            effective_sets=int(row[1] or 0),
            warmup_sets=int(row[2] or 0),
            effective_volume=float(row[3] or 0.0),
            top_weight=float(row[4]) if row[4] is not None else None,
            best_estimated_1rm=float(row[5]) if row[5] is not None else None,
            last_rpe=float(last_rpe) if last_rpe is not None else None,
        )


def normalize_exercise_name(raw_name: str) -> str:
    trimmed = raw_name.strip().lower()
    if not trimmed:
        raise ServiceError("Nombre de ejercicio vacío.", "INVALID_EXERCISE_NAME", status_code=422)

    cleaned = _INVALID_EXERCISE_CHARS.sub("_", trimmed)
    cleaned = _SEPARATOR_PATTERN.sub("_", cleaned)
    cleaned = _MULTI_UNDERSCORE_PATTERN.sub("_", cleaned).strip("_")
    if not cleaned:
        raise ServiceError("Nombre de ejercicio inválido.", "INVALID_EXERCISE_NAME", status_code=422)
    if len(cleaned) > 100:
        raise ServiceError("Nombre de ejercicio demasiado largo.", "INVALID_EXERCISE_NAME", status_code=422)
    return cleaned


def _session_info(session: WorkoutSession) -> SessionInfo:
    return SessionInfo(
        id=session.id,
        user_id=session.user_id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        status=session.status.value if isinstance(session.status, WorkoutStatus) else str(session.status),
        duration_seconds=session.duration_seconds,
    )


def start_session(db: Session, telegram_user_id: int, username: str | None = None) -> SessionInfo:
    user = user_repository.get_or_create(db=db, telegram_user_id=telegram_user_id, username=username)
    active_session = session_repository.get_active_by_user_id(db=db, user_id=user.id)
    if active_session is not None:
        raise ServiceError(
            "Ya hay un entrenamiento activo. Usa /status o /end.", "ACTIVE_SESSION_EXISTS", status_code=409
        )

    started_at = utc_now()
    try:
        session = session_repository.create_active(db=db, user_id=user.id, started_at=started_at)
        db.commit()
        db.refresh(session)
    except IntegrityError:
        db.rollback()
        raise ServiceError(
            "Ya hay un entrenamiento activo. Usa /status o /end.", "ACTIVE_SESSION_EXISTS", status_code=409
        ) from None
    record_session_started()
    return _session_info(session)


def cancel_session(db: Session, telegram_user_id: int) -> SessionInfo:
    user = user_repository.get_by_telegram_user_id(db=db, telegram_user_id=telegram_user_id)
    if user is None:
        raise ServiceError("No hay entrenamiento activo.", "NO_ACTIVE_SESSION", status_code=404)

    session = session_repository.get_active_by_user_id(db=db, user_id=user.id)
    if session is None:
        raise ServiceError("No hay entrenamiento activo.", "NO_ACTIVE_SESSION", status_code=404)

    ended_at = utc_now()
    duration_seconds = int((ended_at - session.started_at).total_seconds())
    session.ended_at = ended_at
    session.duration_seconds = max(duration_seconds, 0)
    session.status = WorkoutStatus.cancelled
    db.add(session)
    db.commit()
    db.refresh(session)
    record_session_cancelled()
    return _session_info(session)


def end_session(db: Session, telegram_user_id: int) -> tuple[SessionInfo, WorkoutSummaryResponse]:
    user = user_repository.get_by_telegram_user_id(db=db, telegram_user_id=telegram_user_id)
    if user is None:
        raise ServiceError("No hay entrenamiento activo.", "NO_ACTIVE_SESSION", status_code=404)

    session = session_repository.get_active_by_user_id(db=db, user_id=user.id)
    if session is None:
        raise ServiceError("No hay entrenamiento activo.", "NO_ACTIVE_SESSION", status_code=404)

    ended_at = utc_now()
    duration_seconds = int((ended_at - session.started_at).total_seconds())
    session.ended_at = ended_at
    session.duration_seconds = max(duration_seconds, 0)
    session.status = WorkoutStatus.completed
    db.add(session)
    db.commit()
    db.refresh(session)
    record_session_completed()

    summary = build_summary(db=db, telegram_user_id=telegram_user_id, session_id=session.id)

    # Load selected coach for AI enrichment
    coach = None
    pref = user_preference_repository.get_by_user_id(db=db, user_id=user.id)
    if pref is not None and pref.selected_coach_id is not None:
        coach = coach_repository.get_by_id(db=db, coach_id=pref.selected_coach_id)

    summary = enrich_summary_with_hermes_ai(summary, coach=coach)
    record_summary_generated(analysis_source=summary.analysis_source, ai_enabled=summary.ai_enabled)
    return _session_info(session), summary


def get_active_session_status(db: Session, telegram_user_id: int) -> ActiveSessionStatusResponse:
    user = user_repository.get_by_telegram_user_id(db=db, telegram_user_id=telegram_user_id)
    if user is None:
        return ActiveSessionStatusResponse(
            has_active_session=False,
            session=None,
            duration_seconds=0,
            exercises_count=0,
            effective_sets=0,
            warmup_sets=0,
        )

    session = session_repository.get_active_by_user_id(db=db, user_id=user.id)
    if session is None:
        return ActiveSessionStatusResponse(
            has_active_session=False,
            session=None,
            duration_seconds=0,
            exercises_count=0,
            effective_sets=0,
            warmup_sets=0,
        )

    counts_stmt = select(
        func.count(SetEntry.id),
        func.sum(case((SetEntry.is_warmup.is_(False), 1), else_=0)),
        func.sum(case((SetEntry.is_warmup.is_(True), 1), else_=0)),
        func.count(func.distinct(SetEntry.exercise_id)),
    ).where(SetEntry.workout_session_id == session.id)
    row = db.execute(counts_stmt).one()

    duration_seconds = int((utc_now() - session.started_at).total_seconds())

    return ActiveSessionStatusResponse(
        has_active_session=True,
        session=_session_info(session),
        duration_seconds=max(duration_seconds, 0),
        exercises_count=int(row[3] or 0),
        effective_sets=int(row[1] or 0),
        warmup_sets=int(row[2] or 0),
    )


def add_set(
    db: Session,
    telegram_user_id: int,
    exercise_name: str,
    weight: float,
    reps: int,
    rpe: float,
) -> SetCreateResponse:
    user = user_repository.get_or_create(db=db, telegram_user_id=telegram_user_id)
    session = session_repository.get_active_by_user_id(db=db, user_id=user.id)
    if session is None:
        raise ServiceError("No hay entrenamiento activo. Usa /start primero.", "NO_ACTIVE_SESSION", status_code=409)

    normalized = normalize_exercise_name(exercise_name)
    exercise = exercise_repository.get_or_create(db=db, raw_name=exercise_name.strip(), normalized_name=normalized)
    is_warmup = rpe == 0

    set_entry = set_repository.create_set(
        db=db,
        workout_session_id=session.id,
        exercise_id=exercise.id,
        weight=weight,
        reps=reps,
        rpe=rpe,
        is_warmup=is_warmup,
    )
    db.commit()
    db.refresh(set_entry)
    record_set_added(
        is_warmup=is_warmup,
        weight=weight,
        reps=reps,
        exercise=exercise.normalized_name,
        rpe=rpe,
    )

    effective_count, warmup_count = set_repository.count_for_session_exercise(
        db=db, workout_session_id=session.id, exercise_id=exercise.id
    )
    if is_warmup:
        message = f"Añadido calentamiento: {normalized} {weight}x{reps}."
    else:
        message = f"Añadido: {normalized} {weight}x{reps} @RPE{rpe}"

    return SetCreateResponse(
        set_id=set_entry.id,
        session_id=session.id,
        exercise_name=exercise.name,
        normalized_exercise_name=exercise.normalized_name,
        weight=set_entry.weight,
        reps=set_entry.reps,
        rpe=set_entry.rpe,
        is_warmup=set_entry.is_warmup,
        message=message,
        effective_set_count_for_exercise=effective_count,
        warmup_set_count_for_exercise=warmup_count,
    )


def _get_session_for_user(db: Session, telegram_user_id: int, session_id: int) -> tuple[WorkoutSession, int]:
    user = user_repository.get_by_telegram_user_id(db=db, telegram_user_id=telegram_user_id)
    if user is None:
        raise ServiceError("Usuario no encontrado.", "USER_NOT_FOUND", status_code=404)

    session = session_repository.get_by_id_for_user(db=db, session_id=session_id, user_id=user.id)
    if session is None:
        raise ServiceError("Sesión no encontrada.", "SESSION_NOT_FOUND", status_code=404)
    return session, user.id


def get_session_info(db: Session, telegram_user_id: int, session_id: int) -> SessionInfo:
    session, _ = _get_session_for_user(db=db, telegram_user_id=telegram_user_id, session_id=session_id)
    return _session_info(session)


def _exercise_load_step_kg(exercise_name: str) -> float:
    normalized = normalize_exercise_name(exercise_name)
    if any(hint in normalized for hint in _LOWER_BODY_HINTS):
        return 5.0
    return 2.5


def _estimated_1rm(weight: float, reps: int, is_warmup: bool) -> float | None:
    if is_warmup:
        return None
    return round(max(weight, 0.0) * (1 + max(reps, 0) / 30), 2)


def _recent_history_for_summary(
    db: Session,
    *,
    user_id: int,
    exercise_ids: list[int],
    exclude_session_id: int,
    limit: int = 24,
) -> list[ExerciseHistoryLine]:
    if not exercise_ids:
        return []

    stmt = (
        select(
            WorkoutSession.ended_at,
            Exercise.name,
            SetEntry.weight,
            SetEntry.reps,
            SetEntry.rpe,
            SetEntry.is_warmup,
        )
        .join(WorkoutSession, WorkoutSession.id == SetEntry.workout_session_id)
        .join(Exercise, Exercise.id == SetEntry.exercise_id)
        .where(
            WorkoutSession.user_id == user_id,
            WorkoutSession.status == WorkoutStatus.completed,
            WorkoutSession.id != exclude_session_id,
            SetEntry.exercise_id.in_(exercise_ids),
            WorkoutSession.ended_at.is_not(None),
        )
        .order_by(WorkoutSession.ended_at.desc(), SetEntry.id.desc())
        .limit(limit)
    )

    history: list[ExerciseHistoryLine] = []
    for row in db.execute(stmt).all():
        performed_at = row[0]
        weight = float(row[2])
        reps = int(row[3])
        is_warmup = bool(row[5])
        volume = weight * reps
        history.append(
            ExerciseHistoryLine(
                performed_at=performed_at,
                exercise_name=str(row[1]),
                weight=weight,
                reps=reps,
                rpe=float(row[4]),
                is_warmup=is_warmup,
                volume=round(volume, 2),
                estimated_1rm=_estimated_1rm(weight=weight, reps=reps, is_warmup=is_warmup),
            )
        )
    return history


def _recommendation_for_exercise(exercise_name: str, effective_lines: list[SetLine], pr_achieved: bool) -> str | None:
    if not effective_lines:
        return None

    avg_rpe = sum(set_line.rpe for set_line in effective_lines) / len(effective_lines)
    last_set = effective_lines[-1]
    top_set = max(effective_lines, key=lambda s: s.volume)
    same_weight_sets = [s for s in effective_lines if s.weight == top_set.weight]
    reps_drop = 0
    if len(same_weight_sets) >= 2:
        reps_drop = same_weight_sets[0].reps - same_weight_sets[-1].reps

    load_step = _exercise_load_step_kg(exercise_name)
    if avg_rpe >= 9 or last_set.rpe >= 9.5:
        return (
            f"{exercise_name}: fatiga alta (RPE medio {avg_rpe:.1f}). "
            f"Prueba bajar {load_step:.1f} kg o recortar una serie."
        )
    if reps_drop >= 2 and last_set.rpe >= 8.5:
        return (
            f"{exercise_name}: caída de repeticiones en sets pesados. "
            "Mantén carga y busca igualar reps en todas las series."
        )
    if avg_rpe <= 7.5 and reps_drop <= 1:
        return (
            f"{exercise_name}: margen claro de progresión (RPE medio {avg_rpe:.1f}). "
            f"Prueba subir {load_step:.1f} kg la próxima semana."
        )
    if pr_achieved:
        return f"{exercise_name}: hubo PR, repite una sesión similar para consolidarlo."

    return (
        f"{exercise_name}: progreso estable. Mantén carga e intenta sumar 1-2 repeticiones totales."
    )


def build_summary(db: Session, telegram_user_id: int, session_id: int) -> WorkoutSummaryResponse:
    session, user_id = _get_session_for_user(db=db, telegram_user_id=telegram_user_id, session_id=session_id)
    set_entries = set_repository.get_by_session_id(db=db, workout_session_id=session.id)

    if not set_entries:
        return WorkoutSummaryResponse(
            session_id=session.id,
            user_id=user_id,
            status=session.status.value,
            started_at=session.started_at,
            ended_at=session.ended_at,
            duration_seconds=session.duration_seconds or 0,
            total_sets=0,
            effective_sets=0,
            warmup_sets=0,
            volume_total=0.0,
            volume_effective=0.0,
            exercises=[],
            observations=["Sesión sin series registradas."],
            recommendations=["Empieza con un bloque base de 2-4 series efectivas por ejercicio principal."],
        )

    exercise_ids = sorted({s.exercise_id for s in set_entries})
    exercise_history = _recent_history_for_summary(
        db=db,
        user_id=user_id,
        exercise_ids=exercise_ids,
        exclude_session_id=session.id,
    )
    exercise_map_stmt = select(Exercise).where(Exercise.id.in_(exercise_ids))
    exercise_rows = db.execute(exercise_map_stmt).scalars().all()
    exercise_map = {ex.id: ex for ex in exercise_rows}

    grouped: dict[int, list[SetEntry]] = defaultdict(list)
    for entry in set_entries:
        grouped[entry.exercise_id].append(entry)

    exercises_output: list[ExerciseSummary] = []
    total_sets = len(set_entries)
    total_warmup = 0
    total_effective = 0
    volume_total = 0.0
    volume_effective = 0.0
    high_rpe_count = 0
    per_exercise_recommendations: list[str] = []

    for exercise_id, exercise_sets in grouped.items():
        exercise = exercise_map[exercise_id]
        warmup_lines: list[SetLine] = []
        effective_lines: list[SetLine] = []

        historical_best = set_repository.get_historical_best_effective_set_volume(
            db=db, user_id=user_id, exercise_id=exercise_id, exclude_session_id=session.id
        )
        historical_best = historical_best or 0.0

        pr_achieved = False
        for row in exercise_sets:
            volume = row.weight * row.reps
            is_pr = False
            if not row.is_warmup and volume > historical_best:
                is_pr = True
                pr_achieved = True
                historical_best = volume

            set_line = SetLine(
                weight=row.weight,
                reps=row.reps,
                rpe=row.rpe,
                is_warmup=row.is_warmup,
                volume=volume,
                is_pr=is_pr,
            )

            volume_total += volume
            if row.is_warmup:
                warmup_lines.append(set_line)
                total_warmup += 1
            else:
                effective_lines.append(set_line)
                total_effective += 1
                volume_effective += volume
                if row.rpe >= 9:
                    high_rpe_count += 1

        top_set = max(effective_lines, key=lambda s: s.volume, default=None)
        exercises_output.append(
            ExerciseSummary(
                exercise_name=exercise.name,
                warmup_sets=warmup_lines,
                effective_sets=effective_lines,
                volume_total=sum(s.volume for s in warmup_lines + effective_lines),
                volume_effective=sum(s.volume for s in effective_lines),
                top_set=top_set,
                pr_achieved=pr_achieved,
            )
        )

        exercise_recommendation = _recommendation_for_exercise(
            exercise_name=exercise.name,
            effective_lines=effective_lines,
            pr_achieved=pr_achieved,
        )
        if exercise_recommendation:
            per_exercise_recommendations.append(exercise_recommendation)

    observations: list[str] = []
    recommendations: list[str] = []
    if total_effective == 0:
        observations.append("No hubo series efectivas (RPE > 0).")
        recommendations.append("Añade al menos 1-2 series efectivas por ejercicio principal.")
    else:
        observations.append(f"Se registraron {total_effective} series efectivas y {total_warmup} de calentamiento.")
        if high_rpe_count >= max(1, total_effective // 2):
            observations.append("Fatiga alta detectada: muchas series cerca del límite (RPE >= 9).")
        else:
            observations.append("La mayoría de series quedaron por debajo de RPE 9.")

    if any(ex.pr_achieved for ex in exercises_output):
        observations.append("Se detectaron PRs en al menos un ejercicio.")
    recommendations.extend(per_exercise_recommendations[:6])

    return WorkoutSummaryResponse(
        session_id=session.id,
        user_id=user_id,
        status=session.status.value,
        started_at=session.started_at,
        ended_at=session.ended_at,
        duration_seconds=session.duration_seconds or 0,
        total_sets=total_sets,
        effective_sets=total_effective,
        warmup_sets=total_warmup,
        volume_total=round(volume_total, 2),
        volume_effective=round(volume_effective, 2),
        exercises=exercises_output,
        exercise_history=exercise_history,
        observations=observations,
        recommendations=recommendations,
    )


def get_exercise_stats(db: Session, telegram_user_id: int, exercise_name: str) -> ExerciseStatsResponse:
    user = user_repository.get_by_telegram_user_id(db=db, telegram_user_id=telegram_user_id)
    if user is None:
        raise ServiceError("Usuario no encontrado.", "USER_NOT_FOUND", status_code=404)

    normalized = normalize_exercise_name(exercise_name)
    exercise = exercise_repository.get_by_normalized_name(db=db, normalized_name=normalized)
    if exercise is None:
        raise ServiceError("Ejercicio no encontrado.", "EXERCISE_NOT_FOUND", status_code=404)

    stmt = (
        select(
            func.count(SetEntry.id),
            func.sum(case((SetEntry.is_warmup.is_(False), 1), else_=0)),
            func.sum(case((SetEntry.is_warmup.is_(True), 1), else_=0)),
            func.sum(SetEntry.weight * SetEntry.reps),
            func.sum(case((SetEntry.is_warmup.is_(False), SetEntry.weight * SetEntry.reps), else_=0.0)),
            func.max(SetEntry.weight),
            func.max(SetEntry.weight * SetEntry.reps),
            func.avg(case((SetEntry.is_warmup.is_(False), SetEntry.rpe), else_=None)),
        )
        .join(WorkoutSession, WorkoutSession.id == SetEntry.workout_session_id)
        .where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == WorkoutStatus.completed,
            SetEntry.exercise_id == exercise.id,
        )
    )
    row = db.execute(stmt).one()

    return ExerciseStatsResponse(
        exercise_name=exercise.name,
        normalized_exercise_name=exercise.normalized_name,
        total_sets=int(row[0] or 0),
        effective_sets=int(row[1] or 0),
        warmup_sets=int(row[2] or 0),
        total_volume=round(float(row[3] or 0.0), 2),
        effective_volume=round(float(row[4] or 0.0), 2),
        best_weight=float(row[5]) if row[5] is not None else None,
        best_volume_set=float(row[6]) if row[6] is not None else None,
        avg_rpe_effective=round(float(row[7]), 2) if row[7] is not None else None,
    )


def get_exercise_history(
    db: Session,
    telegram_user_id: int,
    exercise_name: str,
    limit: int = 30,
) -> ExerciseHistoryResponse:
    user = user_repository.get_by_telegram_user_id(db=db, telegram_user_id=telegram_user_id)
    if user is None:
        raise ServiceError("Usuario no encontrado.", "USER_NOT_FOUND", status_code=404)

    normalized = normalize_exercise_name(exercise_name)
    exercise = exercise_repository.get_by_normalized_name(db=db, normalized_name=normalized)
    if exercise is None:
        raise ServiceError("Ejercicio no encontrado.", "EXERCISE_NOT_FOUND", status_code=404)

    safe_limit = max(1, min(limit, 100))
    stmt = (
        select(
            WorkoutSession.id,
            WorkoutSession.ended_at,
            SetEntry.weight,
            SetEntry.reps,
            SetEntry.rpe,
            SetEntry.is_warmup,
        )
        .join(WorkoutSession, WorkoutSession.id == SetEntry.workout_session_id)
        .where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == WorkoutStatus.completed,
            WorkoutSession.ended_at.is_not(None),
            SetEntry.exercise_id == exercise.id,
        )
        .order_by(WorkoutSession.ended_at.desc(), SetEntry.id.asc())
        .limit(safe_limit)
    )

    entries: list[ExerciseHistoryEntry] = []
    for row in db.execute(stmt).all():
        weight = float(row[2])
        reps = int(row[3])
        is_warmup = bool(row[5])
        volume = weight * reps
        entries.append(
            ExerciseHistoryEntry(
                session_id=int(row[0]),
                performed_at=row[1],
                exercise_name=exercise.name,
                normalized_exercise_name=exercise.normalized_name,
                weight=weight,
                reps=reps,
                rpe=float(row[4]),
                is_warmup=is_warmup,
                volume=round(volume, 2),
                estimated_1rm=_estimated_1rm(weight=weight, reps=reps, is_warmup=is_warmup),
            )
        )

    history = ExerciseHistoryResponse(
        exercise_name=exercise.name,
        normalized_exercise_name=exercise.normalized_name,
        entries=entries,
    )
    return enrich_exercise_history_with_hermes(history)
