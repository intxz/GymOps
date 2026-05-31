# Decisiones de Fase 1

## Framework Telegram elegido: aiogram

Motivos:

- Asíncrono y eficiente para I/O.
- Router/handlers claros para separar comandos reservados y dinámicos.
- Buen encaje con FastAPI y `httpx` en async.

## SQLite ahora, PostgreSQL después

SQLite:

- Muy simple para desarrollo local y Docker.
- Archivo único fácil de respaldar.
- Menor complejidad operativa.

Limitación asumida:

- Concurrencia de escrituras limitada.

Estrategia de migración:

- Modelos con SQLAlchemy + migraciones Alembic.
- Evitar SQL dependiente de engine específico.

## Lógica de resumen local (sin IA)

Al cerrar sesión:

- Duración total
- Agrupación por ejercicio
- Series efectivas (`rpe > 0`)
- Series de calentamiento (`rpe == 0`)
- Volumen total y volumen efectivo
- Top sets por ejercicio
- PRs básicos contra histórico
- Recomendaciones simples por reglas de RPE

