from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class ApiResult:
    ok: bool
    status_code: int
    data: dict[str, Any] | None = None
    error: str | None = None
    message: str | None = None


class GymApiClient:
    def __init__(self, base_url: str, timeout_seconds: float = 8.0, api_key: str | None = None) -> None:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            headers=headers,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def start_session(self, telegram_user_id: int, username: str | None) -> ApiResult:
        return await self._post(
            "/sessions/start",
            {
                "telegram_user_id": telegram_user_id,
                "username": username,
            },
        )

    async def end_session(self, telegram_user_id: int) -> ApiResult:
        return await self._post("/sessions/end", {"telegram_user_id": telegram_user_id})

    async def cancel_session(self, telegram_user_id: int) -> ApiResult:
        return await self._post("/sessions/cancel", {"telegram_user_id": telegram_user_id})

    async def active_session(self, telegram_user_id: int) -> ApiResult:
        return await self._get("/sessions/active", params={"telegram_user_id": telegram_user_id})

    async def exercise_history(self, telegram_user_id: int, exercise_name: str, limit: int = 20) -> ApiResult:
        return await self._get(
            f"/history/exercise/{exercise_name}",
            params={"telegram_user_id": telegram_user_id, "limit": limit},
        )

    async def add_set(
        self,
        telegram_user_id: int,
        exercise_name: str,
        weight: float,
        reps: int,
        rpe: float,
    ) -> ApiResult:
        return await self._post(
            "/sets",
            {
                "telegram_user_id": telegram_user_id,
                "exercise_name": exercise_name,
                "weight": weight,
                "reps": reps,
                "rpe": rpe,
            },
        )

    async def list_coaches(self) -> ApiResult:
        return await self._get("/coaches", {})

    async def my_coach(self, telegram_user_id: int) -> ApiResult:
        return await self._get("/coaches/me", params={"telegram_user_id": telegram_user_id})

    async def select_coach(self, telegram_user_id: int, coach_slug: str | None) -> ApiResult:
        return await self._post(
            "/coaches/select",
            {"coach_slug": coach_slug},
            params={"telegram_user_id": telegram_user_id},
        )

    async def list_mesocycles(self, telegram_user_id: int) -> ApiResult:
        return await self._get("/mesocycles", params={"telegram_user_id": telegram_user_id})

    async def create_mesocycle(
        self,
        telegram_user_id: int,
        name: str,
        goal: str = "mixto",
        weeks_total: int = 4,
    ) -> ApiResult:
        return await self._post(
            "/mesocycles",
            {"name": name, "goal": goal, "weeks_total": weeks_total},
            params={"telegram_user_id": telegram_user_id},
        )

    async def get_active_mesocycle_week(self, telegram_user_id: int) -> ApiResult:
        return await self._get("/mesocycles/active/week", params={"telegram_user_id": telegram_user_id})

    async def complete_mesocycle(self, telegram_user_id: int, mesocycle_id: int) -> ApiResult:
        return await self._post(
            f"/mesocycles/{mesocycle_id}/complete",
            {},
            params={"telegram_user_id": telegram_user_id},
        )

    async def cancel_mesocycle(self, telegram_user_id: int, mesocycle_id: int) -> ApiResult:
        return await self._post(
            f"/mesocycles/{mesocycle_id}/cancel",
            {},
            params={"telegram_user_id": telegram_user_id},
        )

    async def _post(self, path: str, payload: dict[str, Any], params: dict[str, Any] | None = None) -> ApiResult:
        try:
            response = await self._client.post(path, json=payload, params=params)
            return self._to_result(response)
        except httpx.RequestError:
            return ApiResult(
                ok=False,
                status_code=503,
                error="API_UNAVAILABLE",
                message="No puedo conectar con la API de GymOps ahora mismo.",
            )

    async def _get(self, path: str, params: dict[str, Any]) -> ApiResult:
        try:
            response = await self._client.get(path, params=params)
            return self._to_result(response)
        except httpx.RequestError:
            return ApiResult(
                ok=False,
                status_code=503,
                error="API_UNAVAILABLE",
                message="No puedo conectar con la API de GymOps ahora mismo.",
            )

    @staticmethod
    def _to_result(response: httpx.Response) -> ApiResult:
        status_code = response.status_code
        try:
            payload = response.json()
        except ValueError:
            payload = {"message": "Respuesta inválida de la API."}

        if 200 <= status_code < 300:
            return ApiResult(ok=True, status_code=status_code, data=payload)

        detail = payload.get("detail")
        if isinstance(detail, dict):
            return ApiResult(
                ok=False,
                status_code=status_code,
                error=detail.get("error", "API_ERROR"),
                message=detail.get("message", "Error en API."),
                data=payload,
            )
        if isinstance(detail, list):
            return ApiResult(
                ok=False,
                status_code=status_code,
                error="VALIDATION_ERROR",
                message="Datos inválidos. Revisa el formato y vuelve a intentarlo.",
                data=payload,
            )

        return ApiResult(
            ok=False,
            status_code=status_code,
            error="API_ERROR",
            message=payload.get("message", "Error en API."),
            data=payload,
        )
