from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.clients.api_client import GymApiClient

router = Router(name="coaches")


@router.message(Command("coach"))
async def coach_command(message: Message, api_client: GymApiClient) -> None:
    if message.from_user is None:
        await message.answer("No pude identificar tu usuario de Telegram.")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        # Show current coach and list
        result_me = await api_client.my_coach(telegram_user_id=message.from_user.id)
        result_list = await api_client.list_coaches()

        if not result_list.ok:
            await message.answer("No pude cargar la lista de entrenadores.")
            return

        coaches = result_list.data or {}
        coach_list = coaches.get("coaches", [])

        lines: list[str] = []
        if result_me.ok and result_me.data:
            me_data = result_me.data
            selected = me_data.get("selected_coach")
            if selected:
                lines.append(
                    f"Tu entrenador actual: {selected.get('emoji', '🤖')} {selected.get('name', 'Desconocido')}"
                )
            else:
                lines.append("No tienes entrenador asignado. Usa /coach <nombre> para elegir uno.")
        lines.append("")
        lines.append("Entrenadores disponibles:")
        for coach in coach_list:
            lines.append(
                f"{coach.get('emoji', '🤖')} {coach.get('name', 'Coach')}\n"
                f"  /coach {coach.get('slug', '')} - {coach.get('description', '')}"
            )

        await message.answer("\n".join(lines))
        return

    slug = parts[1].strip().lower()

    # Special case: "none" or "ninguno" to deselect
    if slug in ("none", "ninguno", "quitar"):
        result = await api_client.select_coach(
            telegram_user_id=message.from_user.id,
            coach_slug=None,
        )
        if not result.ok:
            await message.answer(result.message or "No se pudo deseleccionar el entrenador.")
            return
        await message.answer("✅ Entrenador deseleccionado. Volverás a análisis local.")
        return

    result = await api_client.select_coach(
        telegram_user_id=message.from_user.id,
        coach_slug=slug,
    )
    if not result.ok:
        if result.status_code == 404:
            await message.answer(
                f"❌ Coach '{slug}' no encontrado.\n"
                "Usa /coach para ver la lista disponible."
            )
            return
        await message.answer(result.message or "No se pudo seleccionar el entrenador.")
        return

    data = result.data or {}
    selected = data.get("selected_coach")
    if selected:
        await message.answer(
            f"{selected.get('emoji', '🤖')} {data.get('message', 'Entrenador seleccionado.')}"
        )
    else:
        await message.answer(data.get("message", "Coach deseleccionado."))
