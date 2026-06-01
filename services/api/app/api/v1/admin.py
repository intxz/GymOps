from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key
from app.core.limiter import limiter
from app.repositories import user_repository

router = APIRouter(prefix="/admin", dependencies=[Depends(verify_api_key)])


@router.post("/authorize")
@limiter.limit("30/minute")
def authorize_user(
    request: Request,
    admin_telegram_user_id: int = Query(..., gt=0),
    target_telegram_user_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    # Check admin
    if not user_repository.is_admin(db=db, telegram_user_id=admin_telegram_user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos de administrador.",
        )

    user = user_repository.authorize_user(db=db, telegram_user_id=target_telegram_user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario {target_telegram_user_id} no encontrado.",
        )

    return {
        "message": f"Usuario {target_telegram_user_id} autorizado correctamente.",
        "username": user.username or "",
    }


@router.get("/check")
@limiter.limit("60/minute")
def check_user(
    request: Request,
    telegram_user_id: int = Query(..., gt=0),
    username: str | None = Query(None),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    # Always ensure user exists so admins can authorize them later
    user = user_repository.get_or_create(db=db, telegram_user_id=telegram_user_id, username=username)
    db.commit()
    return {
        "exists": True,
        "authorized": user.is_authorized,
        "admin": user.is_admin,
        "telegram_user_id": user.telegram_user_id,
    }
