# GymOps / Hermes Fitness Tracker

Base del proyecto para Fases 1 a 6:

- Arquitectura inicial (FastAPI + Telegram Bot + SQLite)
- Estructura de carpetas modular
- `docker-compose.local.yml`
- Esquema inicial SQLite
- Parser de comandos de ejercicio (esqueleto + pseudocódigo)
- API FastAPI funcional para sesiones, series, resumen y estadísticas
- Stack de observabilidad con Prometheus + Grafana + dashboard base GymOps

## Estado actual

- Fase 1 completada (arquitectura y scaffolding)
- Fase 2 completada (API FastAPI)
- Fase 3 completada (bot Telegram)
- Fase 4 completada (resumen local mejorado)
- Fase 5 completada (Hermes IA + fallback local)
- Fase 6 completada (Grafana y dashboards)
- Fase 7 preparada (compose + guía Raspberry + NPM + Cloudflare + SSL)

## Estructura

```text
services/
  api/
  bot/
infra/
  docker/
docs/
tests/
data/
```

## Arranque local (base)

1. Copiar variables:

```bash
cp infra/docker/.env.example infra/docker/.env
```

2. Construir y levantar:

```bash
docker compose -f infra/docker/docker-compose.local.yml up --build
```

> Nota: en esta fase la API y el bot de Telegram base ya están funcionales.

## Raspberry + Nginx Proxy Manager (Fase 7)

Stack para Raspberry:

```bash
docker compose -f infra/docker/docker-compose.rpi.yml up -d --build
```

Incluye:

- `nginx-proxy-manager` en puertos `80/443`
- panel NPM en `81` (por defecto limitado a `127.0.0.1`)
- `gym-api`, `grafana`, `prometheus` sin puertos públicos directos

Guía completa:

- `docs/phase-7-rpi-nginx-proxy-manager-cloudflare.md`

## Endpoints Fase 2 (API)

- `POST /sessions/start`
- `POST /sessions/end`
- `POST /sessions/cancel`
- `GET /sessions/active?telegram_user_id=...`
- `POST /sets`
- `GET /sessions/{id}?telegram_user_id=...`
- `GET /stats/exercise/{exercise}?telegram_user_id=...`
- `GET /summary/{session_id}?telegram_user_id=...`

## Bot Telegram (Fase 3)

Comandos implementados:

- `/start`
- `/status`
- `/end`
- `/cancel`
- `/historial <ejercicio>`
- `/help`

Comandos dinámicos de ejercicio:

- `/<ejercicio> PESOxREPS RPE`
- Ejemplo: `/sentadilla 100x5 8`

## Checklist Producción

- Regenerar `TELEGRAM_BOT_TOKEN` antes de exponer servicios en producción.
- No reutilizar tokens usados en pruebas/local.

## Hermes IA (Fase 5)

Variables para API (`infra/docker/.env`):

- `OPENAI_ENABLED=false` (recomendado por defecto)
- `OPENAI_API_KEY=...`
- `OPENAI_MODEL=gpt-4.1-mini` (o el modelo que prefieras)
- `OPENAI_BASE_URL=https://api.openai.com/v1`
- `OPENAI_TIMEOUT_SECONDS=15`
- `HERMES_OAUTH_ENABLED=false`
- `HERMES_COMMAND=hermes`
- `HERMES_PROVIDER=` (opcional; requiere también `HERMES_MODEL`)
- `HERMES_MODEL=` (opcional, para forzar modelo en Hermes)
- `HERMES_TIMEOUT_SECONDS=45`
- `HERMES_HOME_HOST=/home/raspi/.hermes` (ajusta según usuario host)

Comportamiento:

- Si `OPENAI_ENABLED=false`, resumen 100% local (sin coste API).
- Si `HERMES_OAUTH_ENABLED=true`, GymOps intenta usar Hermes CLI con tu OAuth local.
- Si Hermes/OpenAI fallan, se aplica fallback local automáticamente.
- Al cerrar entreno, Hermes recibe el resumen actual y el historial reciente de los ejercicios trabajados.

Requisito para Docker:

- El servicio `gym-api` monta `${HERMES_HOME_HOST}` en `/root/.hermes` para reutilizar tu sesión OAuth.
- Si la ruta cambia en otra máquina, exporta la variable al levantar:
  `HERMES_HOME_HOST=/ruta/a/.hermes docker compose -f infra/docker/docker-compose.local.yml up --build`

## Observabilidad (Fase 6)

Servicios incluidos en `docker-compose.local.yml`:

- `prometheus` en `http://localhost:9090`
- `grafana` en `http://localhost:3000`

Credenciales Grafana (local):

- usuario: `${GRAFANA_ADMIN_USER}`
- password: `${GRAFANA_ADMIN_PASSWORD}`

Dashboard provisionado:

- `GymOps Overview` (carpeta `GymOps`)
- `GymOps Training Progress` (progreso por ejercicio)
- archivo: `infra/observability/grafana/dashboards/gymops-overview.json`
- archivo: `infra/observability/grafana/dashboards/gymops-training-progress.json`

Métricas API:

- endpoint: `GET /metrics`
- HTTP (rate, errores, latencia, in-flight)
- dominio GymOps (sesiones, sets, volumen, fuente de análisis IA/local)
- entrenamiento por ejercicio (volumen efectivo, series efectivas, mejor peso, e1RM estimado, RPE)

Seguridad recomendada:

- Mantener Grafana/Prometheus solo LAN o VPN en local y Raspberry.
