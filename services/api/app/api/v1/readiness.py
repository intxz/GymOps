from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key
from app.core.limiter import limiter
from app.repositories import daily_readiness_repository, user_repository
from app.schemas.readiness import (
    ReadinessEntryRequest,
    ReadinessEntryResponse,
    ReadinessScoreResponse,
)
from app.services.workout_service import calculate_readiness_score

router = APIRouter(prefix="/readiness", dependencies=[Depends(verify_api_key)])


@router.post("", response_model=ReadinessEntryResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
def log_readiness(
    request: Request,
    payload: ReadinessEntryRequest,
    telegram_user_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
) -> ReadinessEntryResponse:
    user = user_repository.get_by_telegram_user_id(db=db, telegram_user_id=telegram_user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")

    today = date.today()
    score = calculate_readiness_score(
        sleep_hours=payload.sleep_hours,
        stress_level=payload.stress_level,
        soreness=payload.soreness,
    )

    entry = daily_readiness_repository.create_or_update(
        db=db,
        user_id=user.id,
        entry_date=today,
        sleep_hours=payload.sleep_hours,
        stress_level=payload.stress_level,
        soreness=payload.soreness,
        body_weight=payload.body_weight,
        notes=payload.notes,
        readiness_score=score,
    )
    return ReadinessEntryResponse.model_validate(entry)


@router.get("", response_model=ReadinessScoreResponse)
@limiter.limit("60/minute")
def get_readiness(
    request: Request,
    telegram_user_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
) -> ReadinessScoreResponse:
    user = user_repository.get_by_telegram_user_id(db=db, telegram_user_id=telegram_user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")

    latest = daily_readiness_repository.get_latest(db=db, user_id=user.id)
    recent = daily_readiness_repository.get_last_n_days(db=db, user_id=user.id, days=7)

    interpretation = ""
    if latest is not None and latest.readiness_score is not None:
        score = latest.readiness_score
        if score >= 80:
            interpretation = "Readiness óptimo. Puedes entrenar con alta intensidad."
        elif score >= 60:
            interpretation = "Readiness moderado. Entrena con cuidado y no empujes al máximo."
        elif score >= 40:
            interpretation = "Readiness bajo. Considera reducir volumen o intensidad hoy."
        else:
            interpretation = "Readiness muy bajo. Descansa o haz solo movilidad/calentamiento."

    return ReadinessScoreResponse(
        score=latest.readiness_score if latest else None,
        date=latest.date if latest else None,
        sleep_hours=latest.sleep_hours if latest else None,
        stress_level=latest.stress_level if latest else None,
        soreness=latest.soreness if latest else None,
        interpretation=interpretation,
        recent_entries=[ReadinessEntryResponse.model_validate(e) for e in recent],
    )
