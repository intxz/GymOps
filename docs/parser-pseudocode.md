# Parser de Comandos (Pseudocódigo)

```text
RESERVED_COMMANDS = {"start", "end", "help", "status", "cancel", "peso", "nota", "fatiga", "resumen", "historial"}

function handle_message(text):
    if not text starts with "/":
        return error("Usa /help")

    command_token, args = split_first_token(text)
    command_name = command_token.remove_prefix("/").lower().trim()

    if command_name in RESERVED_COMMANDS:
        return route_reserved(command_name, args)

    return parse_dynamic_exercise(command_name, args)

function parse_dynamic_exercise(exercise_name, args):
    # args format: "<peso>x<reps> <rpe>"
    pattern = r"^\s*(\d+(?:\.\d+)?)x(\d+)\s+(\d+(?:\.\d+)?)\s*$"
    match = regex_match(pattern, args)
    if not match:
        return error("Formato inválido. Usa: /<ejercicio> PESOxREPES RPE")

    weight = to_float(match.group(1))
    reps = to_int(match.group(2))
    rpe = to_float(match.group(3))

    if weight < 0:
        return error("Peso inválido")
    if reps <= 0:
        return error("Repeticiones inválidas")
    if rpe < 0 or rpe > 10:
        return error("RPE inválido")

    is_warmup = (rpe == 0)

    # send to API
    response = POST /sets {
      user_id,
      exercise_name,
      weight,
      reps,
      rpe
    }

    if response.error == "NO_ACTIVE_SESSION":
        return error("Usa /start primero")

    return success({
      exercise_name,
      weight,
      reps,
      rpe,
      is_warmup
    })
```

