from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key
from app.schemas.sessions import (
    ActiveSessionStatusResponse,
    EndSessionResponse,
    SessionActionRequest,
    SessionActionResponse,
    SessionInfo,
    StartSessionRequest,
)
from app.schemas.sets import SetCreateRequest, SetCreateResponse
from app.schemas.stats import ExerciseHistoryResponse, ExerciseStatsResponse
from app.schemas.summary import WorkoutSummaryResponse
from app.services.errors import ServiceError
from app.services.workout_service import (
    add_set,
    build_summary,
    cancel_session,
    end_session,
    get_active_session_status,
    get_exercise_history,
    get_exercise_stats,
    get_session_info,
    start_session,
)

router = APIRouter(dependencies=[Depends(verify_api_key)])


def _raise_http_error(exc: ServiceError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"error": exc.error_code, "message": exc.message},
    ) from exc


@router.post("/sessions/start", response_model=SessionActionResponse, status_code=status.HTTP_201_CREATED)
def start_workout(payload: StartSessionRequest, db: Session = Depends(get_db)) -> SessionActionResponse:
    try:
        session = start_session(db=db, telegram_user_id=payload.telegram_user_id, username=payload.username)
        return SessionActionResponse(message="Entrenamiento iniciado.", session=session)
    except ServiceError as exc:
        _raise_http_error(exc)


@router.post("/sessions/end", response_model=EndSessionResponse)
def end_workout(payload: SessionActionRequest, db: Session = Depends(get_db)) -> EndSessionResponse:
    try:
        session, summary = end_session(db=db, telegram_user_id=payload.telegram_user_id)
        return EndSessionResponse(message="Entrenamiento finalizado.", session=session, summary=summary)
    except ServiceError as exc:
        _raise_http_error(exc)


@router.post("/sessions/cancel", response_model=SessionActionResponse)
def cancel_workout(payload: SessionActionRequest, db: Session = Depends(get_db)) -> SessionActionResponse:
    try:
        session = cancel_session(db=db, telegram_user_id=payload.telegram_user_id)
        return SessionActionResponse(message="Entrenamiento cancelado.", session=session)
    except ServiceError as exc:
        _raise_http_error(exc)


@router.get("/sessions/active", response_model=ActiveSessionStatusResponse)
def active_workout_status(
    telegram_user_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
) -> ActiveSessionStatusResponse:
    try:
        return get_active_session_status(db=db, telegram_user_id=telegram_user_id)
    except ServiceError as exc:
        _raise_http_error(exc)


@router.post("/sets", response_model=SetCreateResponse, status_code=status.HTTP_201_CREATED)
def register_set(payload: SetCreateRequest, db: Session = Depends(get_db)) -> SetCreateResponse:
    try:
        return add_set(
            db=db,
            telegram_user_id=payload.telegram_user_id,
            exercise_name=payload.exercise_name,
            weight=payload.weight,
            reps=payload.reps,
            rpe=payload.rpe,
        )
    except ServiceError as exc:
        _raise_http_error(exc)


@router.get("/sessions/{session_id}", response_model=SessionInfo)
def get_session(
    session_id: int,
    telegram_user_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
) -> SessionInfo:
    try:
        return get_session_info(db=db, telegram_user_id=telegram_user_id, session_id=session_id)
    except ServiceError as exc:
        _raise_http_error(exc)


@router.get("/stats/exercise/{exercise}", response_model=ExerciseStatsResponse)
def exercise_stats(
    exercise: str,
    telegram_user_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
) -> ExerciseStatsResponse:
    try:
        return get_exercise_stats(db=db, telegram_user_id=telegram_user_id, exercise_name=exercise)
    except ServiceError as exc:
        _raise_http_error(exc)


@router.get("/history/exercise/{exercise}", response_model=ExerciseHistoryResponse)
def exercise_history(
    exercise: str,
    telegram_user_id: int = Query(..., gt=0),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ExerciseHistoryResponse:
    try:
        return get_exercise_history(
            db=db,
            telegram_user_id=telegram_user_id,
            exercise_name=exercise,
            limit=limit,
        )
    except ServiceError as exc:
        _raise_http_error(exc)


@router.get("/summary/{session_id}", response_model=WorkoutSummaryResponse)
def session_summary(
    session_id: int,
    telegram_user_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
) -> WorkoutSummaryResponse:
    try:
        return build_summary(db=db, telegram_user_id=telegram_user_id, session_id=session_id)
    except ServiceError as exc:
        _raise_http_error(exc)
