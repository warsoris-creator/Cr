from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from config import ADMIN_IDS

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer(
        "🤖 <b>Bot Manager запущен!</b>\n\n"
        "Команды:\n"
        "/status - Список всех ботов\n"
        "/scan - Найти существующие боты на сервере\n"
        "/add - Добавить бота\n"
        "/logs &lt;id&gt; - Посмотреть логи\n"
        "/help - Помощь"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer(
        "📖 <b>Помощь</b>\n\n"
        "<b>Управление ботами:</b>\n"
        "/status - Показать всех ботов с кнопками управления\n"
        "/scan - Найти и импортировать существующие боты\n"
        "/add - Мастер добавления нового бота\n"
        "/logs &lt;bot_id&gt; - Последние 50 строк логов\n\n"
        "<b>В карточке бота:</b>\n"
        "▶️ Запустить\n"
        "⏹ Остановить\n"
        "🔄 Перезапустить\n"
        "📜 Логи\n"
        "♻️ Обновить (только GitHub)\n"
        "🗑 Удалить\n\n"
        "<b>Требования к коду бота:</b>\n"
        "- Файл bot.py или requirements.txt\n"
        "- Бот должен запускаться через python bot.py"
    )


@router.message()
async def echo(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Используйте /status или /add")
