# GymOps Fase 1 - Arquitectura

## Componentes

1. `telegram-bot` (aiogram): interfaz con usuario en Telegram.
2. `gym-api` (FastAPI): capa de negocio y persistencia.
3. `SQLite` (`/data/gymops.db`): almacenamiento inicial portable.

## Principios

- El bot no accede a la base de datos directamente.
- Toda operación de negocio pasa por `gym-api`.
- Diseño agnóstico para migrar a PostgreSQL más adelante.
- Comandos reservados separados de comandos dinámicos de ejercicio.

## Flujo de datos

1. Usuario envía comando Telegram.
2. Bot clasifica:
   - reservado (`/start`, `/end`, etc.)
   - dinámico (`/<ejercicio> peso x reps rpe`)
3. Bot parsea y valida sintaxis básica.
4. Bot llama endpoint correspondiente en API.
5. API valida reglas de sesión activa, crea ejercicio si no existe y registra serie.
6. API responde resultado y bot confirma al usuario.

## Reglas clave de entrenamiento

- Solo una sesión activa por usuario.
- RPE `0` se considera calentamiento (`is_warmup = true`).
- Series repetidas del mismo ejercicio se almacenan como entradas separadas.
- Ejercicio nuevo se crea automáticamente por `normalized_name`.

