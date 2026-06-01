from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key
from app.core.limiter import limiter
from app.repositories import mesocycle_repository, user_repository
from app.schemas.mesocycles import (
    ActiveMesocycleWeekResponse,
    CreateMesocycleRequest,
    CreateMesocycleResponse,
    MesocycleActionResponse,
    MesocycleDetailResponse,
    MesocycleListResponse,
    MesocycleResponse,
    MesocycleWeekResponse,
)

router = APIRouter(prefix="/mesocycles", dependencies=[Depends(verify_api_key)])


@router.get("", response_model=MesocycleListResponse)
@limiter.limit("60/minute")
def list_mesocycles(
    request: Request,
    telegram_user_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
) -> MesocycleListResponse:
    user = user_repository.get_by_telegram_user_id(db=db, telegram_user_id=telegram_user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")

    mesocycles = mesocycle_repository.list_by_user(db=db, user_id=user.id)
    return MesocycleListResponse(
        mesocycles=[MesocycleResponse.model_validate(m) for m in mesocycles]
    )


@router.post("", response_model=CreateMesocycleResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def create_mesocycle(
    request: Request,
    payload: CreateMesocycleRequest,
    telegram_user_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
) -> CreateMesocycleResponse:
    user = user_repository.get_by_telegram_user_id(db=db, telegram_user_id=telegram_user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")

    # Check if user already has an active mesocycle
    active = mesocycle_repository.get_active_by_user_id(db=db, user_id=user.id)
    if active is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya tienes un mesociclo activo: {active.name}. Úsalo o finalízalo primero.",
        )

    start_date = payload.start_date or date.today()
    mesocycle = mesocycle_repository.create(
        db=db,
        user_id=user.id,
        name=payload.name,
        goal=payload.goal,
        weeks_total=payload.weeks_total,
        start_date=start_date,
    )
    weeks = mesocycle_repository.get_weeks(db=db, mesocycle_id=mesocycle.id)
    return CreateMesocycleResponse(
        message="Mesociclo creado correctamente.",
        mesocycle=MesocycleDetailResponse(
            **MesocycleResponse.model_validate(mesocycle).model_dump(),
            weeks=[MesocycleWeekResponse.model_validate(w) for w in weeks],
        ),
    )


@router.get("/active/week", response_model=ActiveMesocycleWeekResponse)
@limiter.limit("60/minute")
def active_mesocycle_week(
    request: Request,
    telegram_user_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
) -> ActiveMesocycleWeekResponse:
    user = user_repository.get_by_telegram_user_id(db=db, telegram_user_id=telegram_user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")

    mesocycle = mesocycle_repository.get_active_by_user_id(db=db, user_id=user.id)
    if mesocycle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No tienes un mesociclo activo. Crea uno con /plan nuevo.",
        )

    current_week = mesocycle_repository.get_current_week(db=db, mesocycle=mesocycle)
    if current_week is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró la semana actual del mesociclo.",
        )

    total_weeks = mesocycle.weeks_total
    week_num = current_week.week_number
    progress_text = f"Semana {week_num} de {total_weeks} ({current_week.phase}) - RPE objetivo: {current_week.target_rpe_range}"

    return ActiveMesocycleWeekResponse(
        mesocycle=MesocycleResponse.model_validate(mesocycle),
        current_week=MesocycleWeekResponse.model_validate(current_week),
        week_progress_text=progress_text,
    )


@router.post("/{mesocycle_id}/complete", response_model=MesocycleActionResponse)
@limiter.limit("30/minute")
def complete_mesocycle(
    request: Request,
    mesocycle_id: int,
    telegram_user_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
) -> MesocycleActionResponse:
    user = user_repository.get_by_telegram_user_id(db=db, telegram_user_id=telegram_user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")

    mesocycle = mesocycle_repository.get_by_id_for_user(db=db, mesocycle_id=mesocycle_id, user_id=user.id)
    if mesocycle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mesociclo no encontrado.")

    mesocycle = mesocycle_repository.complete(db=db, mesocycle=mesocycle)
    return MesocycleActionResponse(
        message=f"Mesociclo '{mesocycle.name}' finalizado.",
        mesocycle=MesocycleResponse.model_validate(mesocycle),
    )


@router.post("/{mesocycle_id}/cancel", response_model=MesocycleActionResponse)
@limiter.limit("30/minute")
def cancel_mesocycle(
    request: Request,
    mesocycle_id: int,
    telegram_user_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
) -> MesocycleActionResponse:
    user = user_repository.get_by_telegram_user_id(db=db, telegram_user_id=telegram_user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")

    mesocycle = mesocycle_repository.get_by_id_for_user(db=db, mesocycle_id=mesocycle_id, user_id=user.id)
    if mesocycle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mesociclo no encontrado.")

    mesocycle = mesocycle_repository.cancel(db=db, mesocycle=mesocycle)
    return MesocycleActionResponse(
        message=f"Mesociclo '{mesocycle.name}' cancelado.",
        mesocycle=MesocycleResponse.model_validate(mesocycle),
    )
