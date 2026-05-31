import json
import logging
import re
import shutil
import subprocess
from collections.abc import Iterable
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.stats import ExerciseHistoryResponse
from app.schemas.summary import WorkoutSummaryResponse

logger = logging.getLogger(__name__)


def _clean_lines(values: Iterable[Any], max_items: int = 6) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        text = value.strip()
        if not text:
            continue
        cleaned.append(text)
        if len(cleaned) >= max_items:
            break
    return cleaned


def _build_prompt_payload(summary: WorkoutSummaryResponse) -> dict[str, Any]:
    return {
        "session_id": summary.session_id,
        "duration_seconds": summary.duration_seconds,
        "effective_sets": summary.effective_sets,
        "warmup_sets": summary.warmup_sets,
        "volume_total": summary.volume_total,
        "volume_effective": summary.volume_effective,
        "observations": summary.observations,
        "recommendations": summary.recommendations,
        "recent_exercise_history": [
            {
                "performed_at": row.performed_at.isoformat(),
                "exercise_name": row.exercise_name,
                "weight": row.weight,
                "reps": row.reps,
                "rpe": row.rpe,
                "is_warmup": row.is_warmup,
                "volume": row.volume,
                "estimated_1rm": row.estimated_1rm,
            }
            for row in summary.exercise_history
        ],
        "exercises": [
            {
                "exercise_name": ex.exercise_name,
                "volume_effective": ex.volume_effective,
                "top_set": (
                    {
                        "weight": ex.top_set.weight,
                        "reps": ex.top_set.reps,
                        "rpe": ex.top_set.rpe,
                        "volume": ex.top_set.volume,
                    }
                    if ex.top_set
                    else None
                ),
                "effective_sets": [
                    {"weight": s.weight, "reps": s.reps, "rpe": s.rpe, "volume": s.volume, "is_pr": s.is_pr}
                    for s in ex.effective_sets
                ],
            }
            for ex in summary.exercises
        ],
    }


def _mark_local_fallback(summary: WorkoutSummaryResponse) -> WorkoutSummaryResponse:
    summary.analysis_source = "local_rules"
    summary.ai_enabled = False
    summary.ai_model = None
    summary.ai_observations = []
    summary.ai_recommendations = []
    return summary


def _extract_json_object(raw_text: str) -> dict[str, Any] | None:
    text = raw_text.strip()
    if not text:
        return None

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    first = text.find("{")
    last = text.rfind("}")
    if first == -1 or last == -1 or last <= first:
        return None
    candidate = text[first : last + 1]
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _merge_ai_lines_into_summary(
    summary: WorkoutSummaryResponse,
    ai_observations: list[str],
    ai_recommendations: list[str],
    analysis_source: str,
    ai_model: str | None,
) -> WorkoutSummaryResponse:
    summary.ai_enabled = True
    summary.ai_model = ai_model
    summary.ai_observations = ai_observations
    summary.ai_recommendations = ai_recommendations
    summary.analysis_source = analysis_source

    merged_observations = list(summary.observations)
    merged_recommendations = list(summary.recommendations)

    for line in ai_observations:
        merged = f"Hermes IA: {line}"
        if merged not in merged_observations:
            merged_observations.append(merged)

    for line in ai_recommendations:
        merged = f"Hermes IA: {line}"
        if merged not in merged_recommendations:
            merged_recommendations.append(merged)

    summary.observations = merged_observations
    summary.recommendations = merged_recommendations
    return summary


def _run_hermes_json_prompt(prompt: str) -> tuple[list[str], list[str], str | None] | None:
    if not settings.hermes_oauth_enabled:
        return None

    hermes_bin = shutil.which(settings.hermes_command)
    if hermes_bin is None:
        logger.warning("HERMES_OAUTH_ENABLED=true pero comando '%s' no existe en PATH.", settings.hermes_command)
        return None

    cmd = [hermes_bin, "-z", prompt]
    if settings.hermes_model:
        cmd.extend(["-m", settings.hermes_model])
        if settings.hermes_provider:
            cmd.extend(["--provider", settings.hermes_provider])
    elif settings.hermes_provider:
        logger.warning(
            "HERMES_PROVIDER configurado sin HERMES_MODEL. Se ignora provider para usar modelo/proveedor por defecto."
        )
    cmd.append("--ignore-rules")

    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=settings.hermes_timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        logger.warning("Hermes OAuth timeout (%ss). Se usa fallback.", settings.hermes_timeout_seconds)
        return None
    except OSError as exc:
        logger.warning("Error ejecutando Hermes OAuth: %s", exc)
        return None

    if proc.returncode != 0:
        stderr_preview = (proc.stderr or "").strip().splitlines()[-1:] or [""]
        logger.warning("Hermes OAuth devolvió código %s. stderr=%s", proc.returncode, stderr_preview[0])
        return None

    ai_json = _extract_json_object(proc.stdout or "")
    if ai_json is None:
        logger.warning("Hermes OAuth no devolvió JSON parseable. Se mantiene local.")
        return None

    observations = _clean_lines(ai_json.get("observations", []), max_items=6)
    recommendations = _clean_lines(ai_json.get("recommendations", []), max_items=6)
    if not observations and not recommendations:
        logger.warning("Hermes OAuth devolvió JSON sin observaciones/recomendaciones útiles.")
        return None

    return observations, recommendations, settings.hermes_model or settings.openai_model or "hermes-default"


def _build_hermes_prompt(summary: WorkoutSummaryResponse) -> str:
    payload = _build_prompt_payload(summary)
    return (
        "Eres Hermes, analista profesional de entrenamiento de fuerza. "
        "Responde SOLO JSON válido con estructura exacta: "
        '{"observations":["..."],"recommendations":["..."]}. '
        "Observations: 2-4 puntos de lectura global del entrenamiento, fatiga, densidad, volumen y rendimiento. "
        "Recommendations: 2-4 acciones concretas para la próxima sesión, priorizando decisiones generales y luego ejercicios clave. "
        "Evita repetir datos obvios que ya aparecen en el resumen. "
        "Usa tono profesional, directo y en español. "
        "No des consejos médicos. "
        f"Datos del entrenamiento:\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _try_enrich_with_hermes_oauth(summary: WorkoutSummaryResponse) -> WorkoutSummaryResponse | None:
    if not settings.hermes_oauth_enabled:
        return None

    prompt = _build_hermes_prompt(summary)
    result = _run_hermes_json_prompt(prompt)
    if result is None:
        return None

    ai_observations, ai_recommendations, ai_model = result
    return _merge_ai_lines_into_summary(
        summary=summary,
        ai_observations=ai_observations,
        ai_recommendations=ai_recommendations,
        analysis_source="hermes_oauth",
        ai_model=ai_model,
    )


def _try_enrich_with_openai_api(summary: WorkoutSummaryResponse) -> WorkoutSummaryResponse | None:
    if not settings.openai_enabled:
        return None

    if not settings.openai_api_key:
        logger.warning("OPENAI_ENABLED=true pero OPENAI_API_KEY está vacío. Se usa fallback local.")
        return None

    prompt_payload = _build_prompt_payload(summary)
    developer_prompt = (
        "Eres Hermes, un asistente profesional experto en entrenamiento de fuerza. "
        "Debes responder SOLO JSON válido con esta estructura: "
        '{"observations":["..."],"recommendations":["..."]}. '
        "Observations: 2-4 puntos de lectura global del entrenamiento, fatiga, densidad, volumen y rendimiento. "
        "Recommendations: 2-4 acciones concretas para la próxima sesión, priorizando decisiones generales y luego ejercicios clave. "
        "Evita repetir datos obvios que ya aparecen en el resumen. "
        "Usa tono profesional, directo y en español. "
        "Evita recomendaciones médicas."
    )

    request_payload = {
        "model": settings.openai_model,
        "messages": [
            {"role": "developer", "content": developer_prompt},
            {"role": "user", "content": json.dumps(prompt_payload, ensure_ascii=False)},
        ],
        "response_format": {"type": "json_object"},
    }

    try:
        with httpx.Client(timeout=settings.openai_timeout_seconds) as client:
            response = client.post(
                f"{settings.openai_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json=request_payload,
            )
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        logger.warning("Hermes IA fallback por error de OpenAI API: %s", exc)
        return None

    content = body.get("choices", [{}])[0].get("message", {}).get("content")
    if not isinstance(content, str):
        logger.warning("Respuesta OpenAI sin content de texto. Se mantiene resumen local.")
        return None

    ai_json = _extract_json_object(content)
    if ai_json is None:
        logger.warning("Respuesta OpenAI no JSON válido. Se mantiene resumen local.")
        return None

    ai_observations = _clean_lines(ai_json.get("observations", []), max_items=6)
    ai_recommendations = _clean_lines(ai_json.get("recommendations", []), max_items=6)
    if not ai_observations and not ai_recommendations:
        logger.warning("OpenAI devolvió JSON sin observaciones/recomendaciones útiles.")
        return None

    return _merge_ai_lines_into_summary(
        summary=summary,
        ai_observations=ai_observations,
        ai_recommendations=ai_recommendations,
        analysis_source="openai_api",
        ai_model=settings.openai_model,
    )


def enrich_summary_with_hermes_ai(summary: WorkoutSummaryResponse) -> WorkoutSummaryResponse:
    enriched = _try_enrich_with_hermes_oauth(summary)
    if enriched is not None:
        return enriched

    enriched = _try_enrich_with_openai_api(summary)
    if enriched is not None:
        return enriched

    return _mark_local_fallback(summary)


def enrich_exercise_history_with_hermes(history: ExerciseHistoryResponse) -> ExerciseHistoryResponse:
    if not history.entries:
        return history

    payload = {
        "exercise_name": history.exercise_name,
        "normalized_exercise_name": history.normalized_exercise_name,
        "entries": [
            {
                "performed_at": entry.performed_at.isoformat(),
                "weight": entry.weight,
                "reps": entry.reps,
                "rpe": entry.rpe,
                "is_warmup": entry.is_warmup,
                "volume": entry.volume,
                "estimated_1rm": entry.estimated_1rm,
            }
            for entry in history.entries
        ],
    }
    prompt = (
        "Eres Hermes, analista profesional de entrenamiento de fuerza. "
        "Analiza el historial de un ejercicio y responde SOLO JSON válido con estructura exacta: "
        '{"observations":["..."],"recommendations":["..."]}. '
        "Observations: 2-4 conclusiones sobre progresión, consistencia, fatiga y rendimiento. "
        "Recommendations: 2-4 acciones para las próximas sesiones de ese ejercicio. "
        "No des consejos médicos. Usa tono profesional, directo y en español. "
        f"Historial:\n{json.dumps(payload, ensure_ascii=False)}"
    )

    result = _run_hermes_json_prompt(prompt)
    if result is not None:
        observations, recommendations, model = result
        history.observations = observations
        history.recommendations = recommendations
        history.analysis_source = "hermes_oauth"
        history.ai_enabled = True
        history.ai_model = model
        return history

    effective_entries = [entry for entry in history.entries if not entry.is_warmup]
    if not effective_entries:
        history.observations = ["Solo hay series de calentamiento registradas para este ejercicio."]
        history.recommendations = ["Registra al menos una serie efectiva con RPE > 0 para analizar progresión."]
        return history

    latest = effective_entries[0]
    best = max(effective_entries, key=lambda entry: entry.estimated_1rm or 0)
    avg_rpe = sum(entry.rpe for entry in effective_entries) / len(effective_entries)
    history.observations = [
        f"Mejor e1RM estimado: {best.estimated_1rm} kg con {best.weight}x{best.reps}.",
        f"Ultima serie efectiva: {latest.weight}x{latest.reps} @RPE{latest.rpe}.",
        f"RPE medio efectivo del historial mostrado: {avg_rpe:.1f}.",
    ]
    if avg_rpe >= 9:
        history.recommendations = ["Fatiga alta: mantén o baja carga y busca series más consistentes."]
    else:
        history.recommendations = ["Progresión estable: intenta sumar 1 repetición total o mantener carga con menor RPE."]
    return history
