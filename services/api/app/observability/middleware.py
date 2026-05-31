import time

from fastapi import Request

from app.observability.metrics import HTTP_IN_PROGRESS, HTTP_REQUEST_DURATION_SECONDS, HTTP_REQUESTS_TOTAL


def _resolve_route_path(request: Request) -> str:
    route = request.scope.get("route")
    if route is not None:
        path = getattr(route, "path", None)
        if isinstance(path, str) and path:
            return path
    return request.url.path or "unknown"


async def prometheus_http_metrics_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    method = request.method
    start_time = time.perf_counter()
    status_code = 500

    HTTP_IN_PROGRESS.labels(method=method).inc()
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        route_path = _resolve_route_path(request)
        elapsed = time.perf_counter() - start_time
        HTTP_REQUESTS_TOTAL.labels(method=method, path=route_path, status_code=str(status_code)).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=route_path).observe(elapsed)
        HTTP_IN_PROGRESS.labels(method=method).dec()

