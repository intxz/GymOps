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


def _format_date(value: str) -> str:
    return value[:10] if value else "fecha_desconocida"


def _fmt_set_line(set_row: dict[str, Any]) -> str:
    weight = set_row.get("weight", 0)
    reps = set_row.get("reps", 0)
    rpe = set_row.get("rpe", 0)
    suffix = " PR" if set_row.get("is_pr") else ""
    return f"{weight}x{reps} @RPE{rpe}{suffix}"


def _fmt_history_set(entry: dict[str, Any]) -> str:
    prefix = "cal" if entry.get("is_warmup") else "ef"
    weight = entry.get("weight", 0)
    reps = entry.get("reps", 0)
    rpe = entry.get("rpe", 0)
    return f"{weight}x{reps} @{rpe} ({prefix})"


def _clean_analysis_line(text: Any) -> str | None:
    if not isinstance(text, str):
        return None
    cleaned = text.strip()
    if not cleaned:
        return None
    return cleaned.removeprefix("Hermes IA:").strip()


def _effective_volume_by_exercise(exercises: list[dict[str, Any]]) -> str:
    volumes: list[str] = []
    for exercise in exercises:
        name = exercise.get("exercise_name", "Ejercicio")
        volume = exercise.get("volume_effective", 0)
        volumes.append(f"{name}: {volume} kg")
    return "; ".join(volumes) if volumes else "Sin volumen efectivo."


def _render_end_summary(payload: dict[str, Any]) -> str:
    session = payload.get("session", {})
    summary = payload.get("summary", {})
    duration = _format_duration(int(session.get("duration_seconds") or 0))
    exercises = summary.get("exercises", [])
    observations = [_clean_analysis_line(obs) for obs in summary.get("observations", [])]
    observations = [obs for obs in observations if obs]
    recommendations = [_clean_analysis_line(rec) for rec in summary.get("recommendations", [])]
    recommendations = [rec for rec in recommendations if rec]

    lines: list[str] = []
    lines.append("Entreno finalizado.")
    lines.append("")
    lines.append(f"Duración: {duration}")
    lines.append(f"Series efectivas: {summary.get('effective_sets', 0)}")
    lines.append(f"Calentamiento: {summary.get('warmup_sets', 0)}")
    lines.append(f"Volumen total: {summary.get('volume_total', 0)} kg")
    lines.append(f"Volumen efectivo: {_effective_volume_by_exercise(exercises)}")
    lines.append("")

    lines.append("Trabajo por ejercicio:")
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

    if observations:
        lines.append("Lectura general:")
        for obs in observations[:4]:
            lines.append(f"- {obs}")

    if recommendations:
        lines.append("")
        lines.append("Plan próxima sesión:")
        for rec in recommendations[:4]:
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
        "/coach - elige tu entrenador IA\n"
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


@router.message(Command("historial"))
async def history_command(message: Message, api_client: GymApiClient) -> None:
    if message.from_user is None:
        await message.answer("No pude identificar tu usuario de Telegram.")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Uso: /historial sentadilla")
        return

    exercise_name = parts[1].strip()
    result = await api_client.exercise_history(
        telegram_user_id=message.from_user.id,
        exercise_name=exercise_name,
        limit=20,
    )
    if not result.ok:
        await message.answer(result.message or "No se pudo obtener el historial.")
        return

    data = result.data or {}
    entries = data.get("entries", [])
    if not entries:
        await message.answer(f"No hay historial para {exercise_name}.")
        return

    lines = [f"Historial de {data.get('normalized_exercise_name', exercise_name)}:"]
    history_lines: list[str] = []
    current_day = ""
    current_sets: list[str] = []
    for entry in entries:
        day = _format_date(entry.get("performed_at", ""))
        if current_day and day != current_day:
            history_lines.append(f"- {current_day}: {', '.join(current_sets)}")
            current_sets = []
        current_day = day
        current_sets.append(_fmt_history_set(entry))

    if current_day:
        history_lines.append(f"- {current_day}: {', '.join(current_sets)}")

    lines.extend(history_lines[:6])

    observations = [_clean_analysis_line(obs) for obs in data.get("observations", [])]
    observations = [obs for obs in observations if obs]
    recommendations = [_clean_analysis_line(rec) for rec in data.get("recommendations", [])]
    recommendations = [rec for rec in recommendations if rec]

    if observations:
        lines.append("")
        lines.append("Conclusión:")
        for observation in observations[:3]:
            lines.append(f"- {observation}")

    if recommendations:
        lines.append("")
        lines.append("Próximas acciones:")
        for recommendation in recommendations[:3]:
            lines.append(f"- {recommendation}")

    await message.answer("\n".join(lines))


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


@router.message(Command("peso", "nota", "fatiga", "resumen"))
async def future_commands_placeholder(message: Message) -> None:
    await message.answer("Este comando estará disponible en una fase siguiente.")
