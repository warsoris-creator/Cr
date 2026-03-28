from aiogram import Router, types
from aiogram.filters import Command
import services.deploy as deploy

router = Router()

@router.message(Command("logs"))
async def cmd_logs(message: types.Message):
    args = message.text.split()

    if len(args) < 2:
        await message.answer("❌ Использование: /logs <bot_id>\n\nПример: /logs abc12345")
        return

    bot_id = args[1]
    logs = await deploy.get_logs(bot_id, lines=50)

    if not logs:
        logs = "📭 Логи пустые"

    if len(logs) > 4000:
        logs = logs[:4000] + "\n\n... (обрезано)"

    await message.answer(f"📜 <b>Логи бота {bot_id}:</b>\n\n<code>{logs}</code>", parse_mode="HTML")
