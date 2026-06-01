from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.clients.api_client import GymApiClient

router = Router(name="admin")


@router.message(Command("autorizar"))
async def authorize_command(message: Message, api_client: GymApiClient) -> None:
    if message.from_user is None:
        await message.answer("No pude identificar tu usuario.")
        return

    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.answer(
            "Uso: /autorizar <telegram_user_id>\n"
            "Ejemplo: /autorizar 123456789"
        )
        return

    target_id = int(parts[1].strip())
    result = await api_client.authorize_user(
        admin_telegram_user_id=message.from_user.id,
        target_telegram_user_id=target_id,
    )
    if not result.ok:
        if result.status_code == 403:
            await message.answer("⛔ No tienes permisos de administrador.")
            return
        if result.status_code == 404:
            await message.answer(f"Usuario {target_id} no encontrado en el sistema.")
            return
        await message.answer(result.message or "No se pudo autorizar al usuario.")
        return

    data = result.data or {}
    await message.answer(f"✅ {data.get('message', 'Usuario autorizado.')}")
