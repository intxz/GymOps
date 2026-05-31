from aiogram import F, Router
from aiogram.types import Message

router = Router(name="fallback")


@router.message(F.text.startswith("/"))
async def unknown_command(message: Message) -> None:
    await message.answer("Comando no reconocido. Usa /help para ver los comandos disponibles.")


@router.message()
async def plain_text_hint(message: Message) -> None:
    await message.answer("Para registrar una serie usa: /<ejercicio> PESOxREPS RPE")

