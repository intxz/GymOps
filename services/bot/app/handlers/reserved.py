from __future__ import annotations

from typing import Any

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.clients.api_client import GymApiClient

router = Router(name="reserved_commands")


def _format_duration(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}h {minutes}min"
    if minutes > 0:
        return f"{minutes}min {secs}s"
    return f"{secs}s"


def _fmt_set_line(set_row: dict[str, Any]) -> str:
    weight = set_row.get("weight", 0)
    reps = set_row.get("reps", 0)
    rpe = set_row.get("rpe", 0)
    suffix = " PR" if set_row.get("is_pr") else ""
    return f"{weight}x{reps} @RPE{rpe}{suffix}"


def _render_end_summary(payload: dict[str, Any]) -> str:
    session = payload.get("session", {})
    summary = payload.get("summary", {})
    duration = _format_duration(int(session.get("duration_seconds") or 0))

    lines: list[str] = []
    lines.append("Entreno finalizado.")
    lines.append("")
    lines.append(f"Duración: {duration}")
    lines.append("")

    exercises = summary.get("exercises", [])
    for exercise in exercises:
        name = exercise.get("exercise_name", "Ejercicio")
        lines.append(f"{name}:")
        warmups = exercise.get("warmup_sets", [])
        effective = exercise.get("effective_sets", [])

        if warmups:
            warmup_line = ", ".join(f"{s.get('weight', 0)}x{s.get('reps', 0)}" for s in warmups)
            lines.append(f"- Calentamiento: {warmup_line}")
        if effective:
            effective_line = ", ".join(_fmt_set_line(s) for s in effective)
            lines.append(f"- Efectivas: {effective_line}")
        lines.append(f"- Volumen efectivo: {exercise.get('volume_effective', 0)} kg")
        lines.append("")

    lines.append("Resumen:")
    lines.append(f"- {summary.get('effective_sets', 0)} series efectivas")
    lines.append(f"- {summary.get('warmup_sets', 0)} series de calentamiento")
    lines.append(f"- Volumen total: {summary.get('volume_total', 0)} kg")

    recommendations = summary.get("recommendations", [])
    if recommendations:
        lines.append("")
        lines.append("Mejora para la próxima semana:")
        for rec in recommendations[:3]:
            lines.append(f"- {rec}")

    return "\n".join(lines)


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    help_text = (
        "Comandos:\n"
        "/start - inicia entrenamiento\n"
        "/status - estado actual\n"
        "/end - finaliza y genera resumen\n"
        "/cancel - cancela sesión activa\n"
        "/help - ayuda\n\n"
        "Formato de series:\n"
        "/<ejercicio> PESOxREPS RPE\n"
        "Ejemplo: /sentadilla 100x5 8\n"
        "RPE 0 = calentamiento"
    )
    await message.answer(help_text)


@router.message(Command("start"))
async def start_command(message: Message, api_client: GymApiClient) -> None:
    if message.from_user is None:
        await message.answer("No pude identificar tu usuario de Telegram.")
        return

    result = await api_client.start_session(
        telegram_user_id=message.from_user.id,
        username=message.from_user.username,
    )
    if not result.ok:
        await message.answer(result.message or "No se pudo iniciar el entrenamiento.")
        return

    await message.answer("Entrenamiento iniciado. Cronómetro en marcha.")


@router.message(Command("status"))
async def status_command(message: Message, api_client: GymApiClient) -> None:
    if message.from_user is None:
        await message.answer("No pude identificar tu usuario de Telegram.")
        return

    result = await api_client.active_session(telegram_user_id=message.from_user.id)
    if not result.ok:
        await message.answer(result.message or "No se pudo obtener el estado.")
        return

    data = result.data or {}
    if not data.get("has_active_session"):
        await message.answer("No hay entrenamiento activo. Usa /start para empezar.")
        return

    duration = _format_duration(int(data.get("duration_seconds") or 0))
    exercises_count = int(data.get("exercises_count") or 0)
    effective_sets = int(data.get("effective_sets") or 0)
    warmup_sets = int(data.get("warmup_sets") or 0)

    await message.answer(
        "Estado actual:\n"
        f"- Duración: {duration}\n"
        f"- Ejercicios: {exercises_count}\n"
        f"- Series efectivas: {effective_sets}\n"
        f"- Calentamiento: {warmup_sets}"
    )


@router.message(Command("cancel"))
async def cancel_command(message: Message, api_client: GymApiClient) -> None:
    if message.from_user is None:
        await message.answer("No pude identificar tu usuario de Telegram.")
        return

    result = await api_client.cancel_session(telegram_user_id=message.from_user.id)
    if not result.ok:
        await message.answer(result.message or "No se pudo cancelar la sesión.")
        return

    await message.answer("Entrenamiento cancelado.")


@router.message(Command("end"))
async def end_command(message: Message, api_client: GymApiClient) -> None:
    if message.from_user is None:
        await message.answer("No pude identificar tu usuario de Telegram.")
        return

    result = await api_client.end_session(telegram_user_id=message.from_user.id)
    if not result.ok:
        await message.answer(result.message or "No se pudo finalizar la sesión.")
        return

    await message.answer(_render_end_summary(result.data or {}))


@router.message(Command("peso", "nota", "fatiga", "resumen", "historial"))
async def future_commands_placeholder(message: Message) -> None:
    await message.answer("Este comando estará disponible en una fase siguiente.")
