from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import db
import services.deploy as deploy
import services.telegram_api as tg_api

router = Router()


@router.message(Command("scan"))
async def cmd_scan(message: types.Message):
    msg = await message.answer("🔍 Читаю /home/ ...")

    found = deploy.scan_existing_bots()

    if not found:
        await msg.edit_text("📭 Ботов по паттерну /home/{name}/{name}/{name}.py не найдено.")
        return

    existing_bots = await db.get_all_bots()
    existing_users = {b["system_user"] for b in existing_bots}

    new_bots = [b for b in found if b["system_user"] not in existing_users]
    already = [b for b in found if b["system_user"] in existing_users]

    text = "🔍 <b>Результат сканирования:</b>\n\n"

    if already:
        text += f"✅ Уже в менеджере: {', '.join(b['name'] for b in already)}\n\n"

    if not new_bots:
        await msg.edit_text(text + "Новых ботов не найдено.", parse_mode="HTML")
        return

    text += f"📋 Найдено новых: <b>{len(new_bots)}</b>\n\n"
    for b in new_bots:
        token_status = "🔑 токен найден" if b["token"] else "⚠️ токен не найден"
        text += f"• <code>{b['name']}</code> — {token_status}\n"

    buttons = [
        [InlineKeyboardButton(text="✅ Импортировать всех", callback_data="scan_import_all")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="scan_cancel")]
    ]

    await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


@router.callback_query(lambda c: c.data == "scan_import_all")
async def cb_import_all(callback: types.CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    msg = await callback.message.answer("⏳ Импортирую...")

    found = deploy.scan_existing_bots()
    existing_bots = await db.get_all_bots()
    existing_users = {b["system_user"] for b in existing_bots}
    new_bots = [b for b in found if b["system_user"] not in existing_users]

    if not new_bots:
        await msg.edit_text("Нечего импортировать.")
        return

    results = []
    for b in new_bots:
        token = b["token"]
        bot_info = await tg_api.validate_token(token) if token else None

        bot_id = await db.add_existing_bot(
            name=b["name"],
            telegram_bot_id=bot_info["id"] if bot_info else None,
            telegram_bot_username=bot_info["username"] if bot_info else b["name"],
            token=token or "",
            system_user=b["system_user"],
            work_dir=b["work_dir"],
            entrypoint=b["entrypoint"],
            service_name=b["service_name"],
        )

        status = await deploy.get_service_status_by_name(b["service_name"])
        db_status = "running" if status == "active" else "stopped"
        await db.update_bot_status(bot_id, db_status)

        icon = "✅" if db_status == "running" else "❌"
        name_display = f"@{bot_info['username']}" if bot_info else b["name"]
        token_note = "" if token else " ⚠️ без токена"
        results.append(f"{icon} {name_display}{token_note}")

    await msg.edit_text(
        "✅ <b>Импорт завершён:</b>\n\n" + "\n".join(results),
        parse_mode="HTML"
    )


@router.callback_query(lambda c: c.data == "scan_cancel")
async def cb_scan_cancel(callback: types.CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("❌ Отменено")
