from collections.abc import Callable, Coroutine

from fastapi import FastAPI, Request, Response
from starlette.types import Receive, Scope, Send

from app.api.v1 import router as v1_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.base import Base
from app.db.models import Exercise, SetEntry, User, WorkoutSession  # noqa: F401
from app.db.session import SessionLocal, engine
from app.observability.metrics import metrics_asgi_app
from app.observability.middleware import prometheus_http_metrics_middleware
from app.services.workout_service import hydrate_training_observability

app = FastAPI(title="GymOps API", version="0.6.0-phase6")


@app.on_event("startup")
def on_startup() -> None:
    setup_logging(settings.log_level)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        hydrate_training_observability(db)


app.include_router(v1_router)
app.middleware("http")(prometheus_http_metrics_middleware)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "phase": "6"}


# Protect /metrics with API key if configured.
class _ProtectedMetricsApp:
    def __init__(self, inner: Callable[[Scope, Receive, Send], Coroutine[None, None, None]]) -> None:
        self._inner = inner

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            x_api_key = headers.get(b"x-api-key", b"").decode("utf-8")
            if settings.api_secret_key and x_api_key != settings.api_secret_key:
                await send({"type": "http.response.start", "status": 403, "headers": [[b"content-type", b"application/json"]]})
                await send({"type": "http.response.body", "body": b'{"detail":"Invalid or missing API key"}'})
                return
        await self._inner(scope, receive, send)


app.mount("/metrics", _ProtectedMetricsApp(metrics_asgi_app))  # type: ignore[arg-type]
