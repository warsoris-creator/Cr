from aiogram import Router, types
from aiogram.filters import Command
import db
import services.deploy as deploy
from keyboards import status_keyboard

router = Router()

@router.message(Command("status"))
async def cmd_status(message: types.Message):
    bots = await db.get_all_bots()

    if not bots:
        await message.answer(
            "📭 Нет активных ботов.\n\n"
            "Нажмите ➕ Добавить бота, чтобы создать первого.",
            reply_markup=status_keyboard([])
        )
        return

    for bot in bots:
        status = await deploy.get_service_status_by_name(bot["systemd_unit"])
        db_status = "running" if status == "active" else "stopped" if status == "inactive" else "error"
        await db.update_bot_status(bot["id"], db_status)

    bots = await db.get_all_bots()

    text = "🤖 <b>Ваши боты:</b>\n\n"
    for bot in bots:
        icon = "✅" if bot["status"] == "running" else "❌" if bot["status"] in ["stopped", "error"] else "⚙️"
        username = bot["telegram_bot_username"] or "Unknown"
        text += f"{icon} @{username}\n"

    await message.answer(text, reply_markup=status_keyboard(bots), parse_mode="HTML")

@router.callback_query(lambda c: c.data == "back_to_status")
async def back_to_status(callback: types.CallbackQuery):
    bots = await db.get_all_bots()

    for bot in bots:
        status = await deploy.get_service_status_by_name(bot["systemd_unit"])
        db_status = "running" if status == "active" else "stopped" if status == "inactive" else "error"
        await db.update_bot_status(bot["id"], db_status)

    bots = await db.get_all_bots()

    text = "🤖 <b>Ваши боты:</b>\n\n"
    for bot in bots:
        icon = "✅" if bot["status"] == "running" else "❌" if bot["status"] in ["stopped", "error"] else "⚙️"
        username = bot["telegram_bot_username"] or "Unknown"
        text += f"{icon} @{username}\n"

    await callback.message.edit_text(text, reply_markup=status_keyboard(bots), parse_mode="HTML")
