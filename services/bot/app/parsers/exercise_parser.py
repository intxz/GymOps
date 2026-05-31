import re
from dataclasses import dataclass


RESERVED_COMMANDS = {
    "start",
    "end",
    "help",
    "status",
    "cancel",
    "peso",
    "nota",
    "fatiga",
    "resumen",
    "historial",
}

_SET_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)?)x(\d+)\s+(\d+(?:\.\d+)?)\s*$")


@dataclass(frozen=True)
class ParsedSetCommand:
    exercise_name: str
    weight: float
    reps: int
    rpe: float

    @property
    def is_warmup(self) -> bool:
        return self.rpe == 0


def split_command(text: str) -> tuple[str, str]:
    chunks = text.strip().split(maxsplit=1)
    command = chunks[0] if chunks else ""
    args = chunks[1] if len(chunks) > 1 else ""
    return command, args


def classify_command(text: str) -> str:
    if not text.startswith("/"):
        return "invalid"

    command, _ = split_command(text)
    name = command[1:].strip().lower()
    if not name:
        return "invalid"
    if name in RESERVED_COMMANDS:
        return "reserved"
    return "exercise_dynamic"


def parse_dynamic_exercise(command: str, args: str) -> ParsedSetCommand:
    exercise_name = command.removeprefix("/").strip().lower()
    if not exercise_name:
        raise ValueError("Nombre de ejercicio inválido.")

    match = _SET_PATTERN.match(args)
    if not match:
        raise ValueError("Formato inválido. Usa: /<ejercicio> PESOxREPES RPE")

    weight = float(match.group(1))
    reps = int(match.group(2))
    rpe = float(match.group(3))

    if weight < 0:
        raise ValueError("El peso no puede ser negativo.")
    if reps <= 0:
        raise ValueError("Las repeticiones deben ser enteras y > 0.")
    if rpe < 0 or rpe > 10:
        raise ValueError("El RPE debe estar entre 0 y 10.")

    return ParsedSetCommand(exercise_name=exercise_name, weight=weight, reps=reps, rpe=rpe)

