from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.clients.api_client import GymApiClient

router = Router(name="mesocycles")


@router.message(Command("plan"))
async def plan_command(message: Message, api_client: GymApiClient) -> None:
    if message.from_user is None:
        await message.answer("No pude identificar tu usuario de Telegram.")
        return

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2 or not parts[1].strip():
        # No subcommand: show active mesocycle week
        result = await api_client.get_active_mesocycle_week(telegram_user_id=message.from_user.id)
        if not result.ok:
            if result.status_code == 404:
                await message.answer(
                    "No tienes un mesociclo activo.\n"
                    "Usa /plan nuevo <nombre> <semanas> para crear uno.\n"
                    "Ejemplo: /plan nuevo Fuerza 4"
                )
                return
            await message.answer(result.message or "No se pudo obtener el plan.")
            return

        data = result.data or {}
        mesocycle = data.get("mesocycle", {})
        current_week = data.get("current_week", {})
        progress = data.get("week_progress_text", "")

        lines = [
            f"📅 {mesocycle.get('name', 'Plan')}",
            f"Objetivo: {mesocycle.get('goal', 'mixto')}",
            "",
            f"🗓️ {progress}",
            f"📊 RPE objetivo: {current_week.get('target_rpe_range', '?')}",
        ]

        # Show completion suggestion for week 12
        week_num = current_week.get('week_number', 0)
        total = mesocycle.get('weeks_total', 0)
        if week_num == total and total == 12:
            lines.append("")
            lines.append("🏁 ¡Última semana del programa!")
            lines.append("Al finalizar, puedes repetir con /plan nuevo o descansar.")

        await message.answer("\n".join(lines))
        return

    subcommand = parts[1].strip().lower()

    if subcommand == "nuevo":
        if len(parts) < 3 or not parts[2].strip():
            await message.answer(
                "Uso: /plan nuevo <nombre> <semanas>\n"
                "Ejemplo: /plan nuevo Fuerza 12\n"
                "Recomendado: 12 semanas (Foundation + Ramping)\n"
                "Objetivos: fuerza, hipertrofia, mixto (default)."
            )
            return

        name_parts = parts[2].strip().rsplit(maxsplit=1)
        if len(name_parts) == 2 and name_parts[1].isdigit():
            name = name_parts[0]
            weeks = int(name_parts[1])
        else:
            name = parts[2].strip()
            weeks = 4

        # Detect goal from name or use default
        goal = "mixto"
        lower_name = name.lower()
        if any(w in lower_name for w in ("fuerza", "power", "potencia")):
            goal = "fuerza"
        elif any(w in lower_name for w in ("hipertrofia", "massa", "volumen", "size")):
            goal = "hipertrofia"

        result = await api_client.create_mesocycle(
            telegram_user_id=message.from_user.id,
            name=name,
            goal=goal,
            weeks_total=weeks,
        )
        if not result.ok:
            if result.status_code == 409:
                await message.answer(
                    result.message or "Ya tienes un mesociclo activo. Finalízalo primero con /plan fin."
                )
                return
            await message.answer(result.message or "No se pudo crear el mesociclo.")
            return

        data = result.data or {}
        mesocycle = data.get("mesocycle", {})
        weeks_list = mesocycle.get("weeks", [])

        lines = [
            f"✅ Mesociclo creado: {mesocycle.get('name', 'Plan')}",
            f"Objetivo: {mesocycle.get('goal', 'mixto')}",
            f"Duración: {mesocycle.get('weeks_total', 0)} semanas",
            "",
            "Fases:",
        ]
        for week in weeks_list[:6]:
            lines.append(
                f"  Semana {week.get('week_number')}: {week.get('phase')} "
                f"(RPE {week.get('target_rpe_range', '?')})"
            )

        await message.answer("\n".join(lines))
        return

    if subcommand == "fin":
        # Get active mesocycle first to find ID
        result_active = await api_client.list_mesocycles(telegram_user_id=message.from_user.id)
        if not result_active.ok:
            await message.answer("No se pudo obtener tu mesociclo activo.")
            return

        mesocycles = result_active.data or {}
        active = None
        for m in mesocycles.get("mesocycles", []):
            if m.get("status") == "active":
                active = m
                break

        if active is None:
            await message.answer("No tienes un mesociclo activo para finalizar.")
            return

        result = await api_client.complete_mesocycle(
            telegram_user_id=message.from_user.id,
            mesocycle_id=active.get("id"),
        )
        if not result.ok:
            await message.answer(result.message or "No se pudo finalizar el mesociclo.")
            return

        await message.answer("🏁 Mesociclo finalizado. ¡Buen trabajo!")
        return

    if subcommand == "cancelar":
        result_active = await api_client.list_mesocycles(telegram_user_id=message.from_user.id)
        if not result_active.ok:
            await message.answer("No se pudo obtener tu mesociclo activo.")
            return

        mesocycles = result_active.data or {}
        active = None
        for m in mesocycles.get("mesocycles", []):
            if m.get("status") == "active":
                active = m
                break

        if active is None:
            await message.answer("No tienes un mesociclo activo para cancelar.")
            return

        result = await api_client.cancel_mesocycle(
            telegram_user_id=message.from_user.id,
            mesocycle_id=active.get("id"),
        )
        if not result.ok:
            await message.answer(result.message or "No se pudo cancelar el mesociclo.")
            return

        await message.answer("🚫 Mesociclo cancelado.")
        return

    await message.answer(
        "Subcomando no reconocido. Usa:\n"
        "/plan - ver plan activo\n"
        "/plan nuevo <nombre> <semanas>\n"
        "/plan fin - finalizar plan\n"
        "/plan cancelar - cancelar plan"
    )
