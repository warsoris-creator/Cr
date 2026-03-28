from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def status_keyboard(bots):
    buttons = []
    for bot in bots:
        status_icon = "✅" if bot["status"] == "running" else "❌" if bot["status"] in ["stopped", "error"] else "⚙️"
        username = bot["telegram_bot_username"] or "Unknown"
        buttons.append([InlineKeyboardButton(
            text=f"{status_icon} @{username}",
            callback_data=f"bot_{bot['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="➕ Добавить бота", callback_data="add_bot")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def bot_card_keyboard(bot_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Запустить", callback_data=f"start_{bot_id}"),
         InlineKeyboardButton(text="⏹ Остановить", callback_data=f"stop_{bot_id}"),
         InlineKeyboardButton(text="🔄 Перезапустить", callback_data=f"restart_{bot_id}")],
        [InlineKeyboardButton(text="📜 Логи", callback_data=f"logs_{bot_id}"),
         InlineKeyboardButton(text="♻️ Обновить", callback_data=f"update_{bot_id}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_{bot_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_status")]
    ])

def cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_add")]
    ])

def source_type_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 GitHub", callback_data="source_github")],
        [InlineKeyboardButton(text="📁 Python файл", callback_data="source_file")]
    ])
