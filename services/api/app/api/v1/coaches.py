from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key
from app.core.limiter import limiter
from app.repositories import coach_repository, user_preference_repository, user_repository
from app.schemas.coaches import (
    CoachListResponse,
    CoachProfileResponse,
    CoachSelectionRequest,
    CoachSelectionResponse,
    UserCoachResponse,
)

router = APIRouter(prefix="/coaches", dependencies=[Depends(verify_api_key)])


@router.get("", response_model=CoachListResponse)
@limiter.limit("60/minute")
def list_coaches(request: Request, db: Session = Depends(get_db)) -> CoachListResponse:
    coaches = coach_repository.get_builtin_coaches(db=db)
    return CoachListResponse(
        coaches=[CoachProfileResponse.model_validate(c) for c in coaches]
    )


@router.get("/me", response_model=UserCoachResponse)
@limiter.limit("60/minute")
def my_coach(
    request: Request,
    telegram_user_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
) -> UserCoachResponse:
    user = user_repository.get_by_telegram_user_id(db=db, telegram_user_id=telegram_user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")

    pref = user_preference_repository.get_or_create(db=db, user_id=user.id)
    coach = None
    if pref.selected_coach_id is not None:
        coach = coach_repository.get_by_id(db=db, coach_id=pref.selected_coach_id)

    return UserCoachResponse(
        user_id=user.id,
        selected_coach=CoachProfileResponse.model_validate(coach) if coach else None,
        privacy_mode=pref.privacy_mode,
    )


@router.post("/select", response_model=CoachSelectionResponse)
@limiter.limit("30/minute")
def select_coach(
    request: Request,
    payload: CoachSelectionRequest,
    telegram_user_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
) -> CoachSelectionResponse:
    user = user_repository.get_by_telegram_user_id(db=db, telegram_user_id=telegram_user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")

    if payload.coach_slug is None:
        user_preference_repository.set_coach(db=db, user_id=user.id, coach_id=None)
        return CoachSelectionResponse(
            message="Coach deseleccionado. Usarás el análisis local por defecto.",
            selected_coach=None,
        )

    coach = coach_repository.get_by_slug(db=db, slug=payload.coach_slug)
    if coach is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Coach '{payload.coach_slug}' no encontrado.",
        )

    user_preference_repository.set_coach(db=db, user_id=user.id, coach_id=coach.id)
    return CoachSelectionResponse(
        message=f"Coach seleccionado: {coach.name} {coach.emoji}.",
        selected_coach=CoachProfileResponse.model_validate(coach),
    )
