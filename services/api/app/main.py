from fastapi import FastAPI

from app.api.v1 import router as v1_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.base import Base
from app.db.models import Exercise, SetEntry, User, WorkoutSession  # noqa: F401
from app.db.session import engine
from app.observability.metrics import metrics_asgi_app
from app.observability.middleware import prometheus_http_metrics_middleware

app = FastAPI(title="GymOps API", version="0.6.0-phase6")


@app.on_event("startup")
def on_startup() -> None:
    setup_logging(settings.log_level)
    Base.metadata.create_all(bind=engine)


app.include_router(v1_router)
app.mount("/metrics", metrics_asgi_app)
app.middleware("http")(prometheus_http_metrics_middleware)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "phase": "6"}
