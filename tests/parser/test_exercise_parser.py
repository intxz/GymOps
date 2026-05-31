from services.bot.app.parsers.exercise_parser import (
    classify_command,
    parse_dynamic_exercise,
    split_command,
)


def test_classify_reserved_command() -> None:
    assert classify_command("/start") == "reserved"


def test_classify_dynamic_exercise_command() -> None:
    assert classify_command("/sentadilla 100x5 8") == "exercise_dynamic"


def test_parse_dynamic_exercise_valid() -> None:
    command, args = split_command("/sentadilla 100x5 8.5")
    parsed = parse_dynamic_exercise(command, args)

    assert parsed.exercise_name == "sentadilla"
    assert parsed.weight == 100.0
    assert parsed.reps == 5
    assert parsed.rpe == 8.5
    assert parsed.is_warmup is False


def test_parse_dynamic_exercise_warmup() -> None:
    command, args = split_command("/sentadilla 60x8 0")
    parsed = parse_dynamic_exercise(command, args)
    assert parsed.is_warmup is True

