from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.clients.api_client import GymApiClient

router = Router(name="readiness")


@router.message(Command("readiness"))
async def readiness_command(message: Message, api_client: GymApiClient) -> None:
    if message.from_user is None:
        await message.answer("No pude identificar tu usuario de Telegram.")
        return

    parts = (message.text or "").split(maxsplit=4)
    if len(parts) > 1 and parts[1].strip().lower() == "log":
        # /readiness log <sleep> <stress> <soreness> [peso]
        if len(parts) < 5:
            await message.answer(
                "❌ Faltan argumentos.\n\n"
                "Uso: /readiness log <horas_sueño> <stress_1-10> <dolor_1-10> [peso]\n"
                "Ejemplo: /readiness log 7.5 4 3 82.5\n\n"
                "Reglas:\n"
                "  • Sueño: 0-24 horas\n"
                "  • Stress: 1-10\n"
                "  • Dolor muscular: 1-10\n"
                "  • Peso corporal: opcional, en kg"
            )
            return

        try:
            sleep_hours = float(parts[2])
            stress_level = int(parts[3])
            soreness = int(parts[4])
            body_weight = float(parts[5]) if len(parts) > 5 else None
        except (ValueError, IndexError):
            await message.answer(
                "❌ Formato inválido.\n"
                "Revisa que todos los valores sean números.\n"
                "Ejemplo: /readiness log 7.5 4 3 82.5"
            )
            return

        # Validate ranges
        errors: list[str] = []
        if sleep_hours < 0 or sleep_hours > 24:
            errors.append("Sueño debe estar entre 0 y 24 horas.")
        if stress_level < 1 or stress_level > 10:
            errors.append("Stress debe estar entre 1 y 10.")
        if soreness < 1 or soreness > 10:
            errors.append("Dolor muscular debe estar entre 1 y 10.")
        if body_weight is not None and body_weight <= 0:
            errors.append("Peso corporal debe ser mayor que 0.")

        if errors:
            await message.answer("❌ " + "\n".join(errors))
            return

        result = await api_client.log_readiness(
            telegram_user_id=message.from_user.id,
            sleep_hours=sleep_hours,
            stress_level=stress_level,
            soreness=soreness,
            body_weight=body_weight,
        )
        if not result.ok:
            if result.status_code == 422:
                await message.answer(
                    "❌ Datos inválidos enviados a la API.\n"
                    "Revisa los rangos: sueño 0-24, stress 1-10, dolor 1-10."
                )
                return
            await message.answer(result.message or "No se pudo guardar el registro.")
            return

        data = result.data or {}
        score = data.get("readiness_score", "?")
        await message.answer(
            f"📊 Readiness registrado: {score}/100\n"
            f"Sueño: {sleep_hours}h | Stress: {stress_level}/10 | Dolor: {soreness}/10"
        )
        return

    # /readiness without subcommand: show current score
    result = await api_client.get_readiness(telegram_user_id=message.from_user.id)
    if not result.ok:
        if result.status_code == 404:
            await message.answer(
                "No tienes registros de readiness.\n"
                "Usa: /readiness log <sueño> <stress> <dolor> [peso]"
            )
            return
        await message.answer(result.message or "No se pudo obtener el readiness.")
        return

    data = result.data or {}
    score = data.get("score", "?")
    interpretation = data.get("interpretation", "")
    recent = data.get("recent_entries", [])

    lines = [f"📊 Readiness: {score}/100"]
    if interpretation:
        lines.append(f"💡 {interpretation}")

    if recent:
        lines.append("")
        lines.append("Últimos registros:")
        for entry in recent[:3]:
            date = entry.get("date", "?")
            s = entry.get("readiness_score", "?")
            lines.append(f"  {date}: {s}/100")

    lines.append("")
    lines.append("Para registrar: /readiness log <sueño> <stress> <dolor> [peso]")

    await message.answer("\n".join(lines))
