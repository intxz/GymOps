import logging
import time

from fastapi import FastAPI, Request, Response
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1 import router as v1_router
from app.core.limiter import limiter
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.base import Base
from app.db.models import CoachProfile, Exercise, Mesocycle, MesocycleWeek, SetEntry, User, UserPreference, WorkoutSession  # noqa: F401
from app.db.session import SessionLocal, engine
from app.observability.metrics import metrics_asgi_app
from app.observability.middleware import prometheus_http_metrics_middleware
from app.db.migrations import run_sqlite_migrations
from app.db.seed_coaches import seed_builtin_coaches
from app.repositories import user_repository
from app.services.workout_service import hydrate_training_observability

logger = logging.getLogger(__name__)

app = FastAPI(title="GymOps API", version="0.9.0-nippard")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.on_event("startup")
def on_startup() -> None:
    setup_logging(settings.log_level)
    run_sqlite_migrations(engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_builtin_coaches(db)
        # Make the first ever user an admin and authorized automatically
        first_user = user_repository.get_first_user(db=db)
        if first_user is not None and not first_user.is_admin:
            first_user.is_admin = True
            first_user.is_authorized = True
            db.add(first_user)
            db.commit()
            logger.info("First user %s promoted to admin", first_user.telegram_user_id)
        hydrate_training_observability(db)


app.include_router(v1_router)
app.mount("/metrics", metrics_asgi_app)
app.middleware("http")(prometheus_http_metrics_middleware)


@app.get("/health")
@limiter.limit("30/minute")
def health(request: Request) -> dict[str, str]:
    return {"status": "ok", "phase": "6"}


# Audit logging middleware.
@app.middleware("http")
async def audit_log_middleware(request: Request, call_next: callable) -> Response:
    start = time.time()
    response = await call_next(request)
    duration = (time.time() - start) * 1000

    # Only log API requests (skip metrics/health noise).
    path = request.url.path
    if path.startswith("/api/") or path.startswith("/sessions") or path.startswith("/sets"):
        client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
        telegram_user_id = request.query_params.get("telegram_user_id") or "-"
        logger.info(
            "AUDIT method=%s path=%s status=%s user_id=%s ip=%s duration_ms=%.2f",
            request.method,
            path,
            response.status_code,
            telegram_user_id,
            client_ip,
            duration,
        )
    return response
