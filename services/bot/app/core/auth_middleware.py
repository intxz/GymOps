from typing import Any, Callable, Coroutine

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from app.clients.api_client import GymApiClient


class AuthMiddleware(BaseMiddleware):
    """Middleware to check if users are authorized before processing commands."""

    ALLOWED_COMMANDS = {"/start", "/help", "/autorizar"}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Coroutine[Any, Any, Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        text = (event.text or "").strip().split()[0] if event.text else ""
        if text in self.ALLOWED_COMMANDS:
            return await handler(event, data)

        if event.from_user is None:
            await event.answer("No pude identificar tu usuario.")
            return None

        api_client: GymApiClient = data.get("api_client")
        if api_client is None:
            return await handler(event, data)

        result = await api_client.check_user(telegram_user_id=event.from_user.id)
        if not result.ok:
            await event.answer("Error verificando autorización. Intenta más tarde.")
            return None

        user_data = result.data or {}
        if not user_data.get("authorized", False):
            await event.answer(
                "⛔ No estás autorizado para usar este bot.\n"
                "Contacta al administrador para obtener acceso."
            )
            return None

        return await handler(event, data)
