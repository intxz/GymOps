import logging
import time

from fastapi import FastAPI, Request, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.v1 import router as v1_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.base import Base
from app.db.models import Exercise, SetEntry, User, WorkoutSession  # noqa: F401
from app.db.session import SessionLocal, engine
from app.observability.metrics import metrics_asgi_app
from app.observability.middleware import prometheus_http_metrics_middleware
from app.services.workout_service import hydrate_training_observability

logger = logging.getLogger(__name__)

# Rate limiter: 100 requests per minute per IP.
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="GymOps API", version="0.6.0-phase6")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.on_event("startup")
def on_startup() -> None:
    setup_logging(settings.log_level)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
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
