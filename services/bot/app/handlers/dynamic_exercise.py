from aiogram import F, Router
from aiogram.types import Message

from app.clients.api_client import GymApiClient
from app.parsers.exercise_parser import classify_command, parse_dynamic_exercise, split_command

router = Router(name="dynamic_exercise")


@router.message(F.text.startswith("/"))
async def dynamic_exercise_command(message: Message, api_client: GymApiClient) -> None:
    text = (message.text or "").strip()
    command_type = classify_command(text)
    if command_type != "exercise_dynamic":
        return

    if message.from_user is None:
        await message.answer("No pude identificar tu usuario de Telegram.")
        return

    command, args = split_command(text)
    try:
        parsed = parse_dynamic_exercise(command, args)
    except ValueError as exc:
        await message.answer(str(exc))
        return

    result = await api_client.add_set(
        telegram_user_id=message.from_user.id,
        exercise_name=parsed.exercise_name,
        weight=parsed.weight,
        reps=parsed.reps,
        rpe=parsed.rpe,
    )
    if not result.ok:
        if result.status_code == 409:
            await message.answer(
                "❌ " + (result.message or "No hay entrenamiento activo. Usa /start primero.")
            )
            return
        if result.status_code == 422:
            await message.answer(
                "❌ Datos inválidos.\n"
                "Revisa: peso ≥ 0, reps > 0, RPE entre 0 y 10.\n"
                "Ejemplo: /sentadilla 100x5 8"
            )
            return
        await message.answer(result.message or "No se pudo registrar la serie.")
        return

    data = result.data or {}
    if parsed.is_warmup:
        await message.answer(f"🔥 Añadido calentamiento: {parsed.exercise_name} {parsed.weight}x{parsed.reps}.")
        return

    effective_count = data.get("effective_set_count_for_exercise", "?")
    await message.answer(
        f"✅ Añadido: {parsed.exercise_name} {parsed.weight}x{parsed.reps} @RPE{parsed.rpe}\n"
        f"Serie efectiva #{effective_count} de {parsed.exercise_name}."
    )
