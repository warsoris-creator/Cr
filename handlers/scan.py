from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import db
import services.deploy as deploy
import services.telegram_api as tg_api

router = Router()


async def sudo_stat(path: str) -> bool:
    import asyncio
    proc = await asyncio.create_subprocess_exec(
        "sudo", "stat", path,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    await proc.wait()
    return proc.returncode == 0


@router.message(Command("scan"))
async def cmd_scan(message: types.Message):
    msg = await message.answer("🔍 Читаю /home/ ...")

    # Шаг 1 — список пользователей
    try:
        users = os.listdir("/home")
    except Exception as e:
        await msg.edit_text(f"❌ Не могу прочитать /home/: {e}")
        return

    await msg.edit_text(f"🔍 Пользователи в /home/: {', '.join(users)}\n\nПроверяю каждого...")

    log = []
    found = []

    for name in users:
        if deploy.is_protected(name):
            log.append(f"🔒 {name} — защищён, пропускаю")
            continue

        py_path = f"/home/{name}/{name}/{name}.py"
        svc_path = f"/etc/systemd/system/{name}.service"

        py_ok = await sudo_stat(py_path)
        svc_ok = await sudo_stat(svc_path)

        if py_ok and svc_ok:
            token = deploy.extract_token_from_file(py_path)
            token_status = "🔑 токен есть" if token else "⚠️ токен не найден"
            log.append(f"✅ {name} — py✓ svc✓ {token_status}")
            found.append({
                "name": name,
                "work_dir": f"/home/{name}/{name}",
                "entrypoint": f"{name}.py",
                "system_user": name,
                "service_name": f"{name}.service",
                "token": token,
            })
        else:
            log.append(f"❌ {name} — py={'✓' if py_ok else '✗'} svc={'✓' if svc_ok else '✗'}")

    await msg.edit_text("🔍 <b>Диагностика сканирования:</b>\n\n" + "\n".join(log), parse_mode="HTML")

    if not found:
        await message.answer("📭 Подходящих ботов не найдено.")
        return

    existing_bots = await db.get_all_bots()
    existing_users = {b["system_user"] for b in existing_bots}

    new_bots = [b for b in found if b["system_user"] not in existing_users]
    already = [b for b in found if b["system_user"] in existing_users]

    text = ""
    if already:
        text += f"✅ Уже в менеджере: {', '.join(b['name'] for b in already)}\n\n"

    if not new_bots:
        await message.answer(text + "Новых ботов не найдено.")
        return

    text += f"📋 Найдено новых: <b>{len(new_bots)}</b>\n\n"
    for b in new_bots:
        token_status = "🔑 токен найден" if b["token"] else "⚠️ токен не найден"
        text += f"• <code>{b['name']}</code> — {token_status}\n"

    buttons = [
        [InlineKeyboardButton(text="✅ Импортировать всех", callback_data="scan_import_all")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="scan_cancel")]
    ]

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


@router.callback_query(lambda c: c.data == "scan_import_all")
async def cb_import_all(callback: types.CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("⏳ Импортирую...")

    found = deploy.scan_existing_bots()
    existing_bots = await db.get_all_bots()
    existing_users = {b["system_user"] for b in existing_bots}
    new_bots = [b for b in found if b["system_user"] not in existing_users]

    results = []
    for b in new_bots:
        token = b["token"]
        bot_info = None

        if token:
            bot_info = await tg_api.validate_token(token)

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

        # Получаем реальный статус
        status = await deploy.get_service_status_by_name(b["service_name"])
        db_status = "running" if status == "active" else "stopped"
        await db.update_bot_status(bot_id, db_status)

        icon = "✅" if db_status == "running" else "❌"
        token_note = "" if token else " ⚠️ без токена"
        results.append(f"{icon} @{bot_info['username'] if bot_info else b['name']}{token_note}")

    if results:
        await callback.message.answer(
            "✅ <b>Импорт завершён:</b>\n\n" + "\n".join(results),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer("Нечего импортировать.")


@router.callback_query(lambda c: c.data == "scan_cancel")
async def cb_scan_cancel(callback: types.CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("❌ Отменено")
