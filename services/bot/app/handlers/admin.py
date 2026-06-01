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
    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "❌ Falta el ID de usuario.\n\n"
            "Uso: /autorizar <telegram_user_id>\n"
            "Ejemplo: /autorizar 123456789\n\n"
            "Nota: El ID se obtiene cuando un usuario envía /start por primera vez."
        )
        return

    if not parts[1].strip().lstrip('-').isdigit():
        await message.answer(
            "❌ El ID debe ser un número.\n"
            "Ejemplo: /autorizar 123456789"
        )
        return

    target_id = int(parts[1].strip())
    if target_id <= 0:
        await message.answer("❌ El ID debe ser un número positivo.")
        return

    result = await api_client.authorize_user(
        admin_telegram_user_id=message.from_user.id,
        target_telegram_user_id=target_id,
    )
    if not result.ok:
        if result.status_code == 403:
            await message.answer("⛔ No tienes permisos de administrador.")
            return
        if result.status_code == 404:
            await message.answer(
                f"❌ Usuario {target_id} no encontrado.\n"
                "El usuario debe haber enviado /start al menos una vez."
            )
            return
        await message.answer(result.message or "No se pudo autorizar al usuario.")
        return

    data = result.data or {}
    username = data.get("username", "")
    name_info = f" ({username})" if username else ""
    await message.answer(f"✅ {data.get('message', 'Usuario autorizado.')}{name_info}")
