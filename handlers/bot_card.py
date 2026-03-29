from aiogram import Router, types
import db
import services.deploy as deploy
from keyboards import bot_card_keyboard, delete_confirm1_keyboard, delete_confirm2_keyboard

router = Router()


@router.callback_query(lambda c: c.data.startswith("bot_"))
async def cb_bot_card(callback: types.CallbackQuery):
    bot_id = callback.data.replace("bot_", "")
    bot = await db.get_bot(bot_id)
    if not bot:
        await callback.answer("❌ Бот не найден")
        return

    status = await deploy.get_service_status_by_name(bot["systemd_unit"])
    status_icon = "✅" if status == "active" else "❌"
    status_text = "Running" if status == "active" else "Stopped" if status == "inactive" else status

    text = (
        f"🤖 <b>@{bot['telegram_bot_username']}</b>\n\n"
        f"Статус: {status_icon} {status_text}\n"
        f"ID: {bot_id}\n"
        f"Пользователь: {bot['system_user']}\n"
        f"Папка: {bot['work_dir']}\n"
        f"Источник: {bot['source_type']}\n"
    )
    if bot["last_error"]:
        text += f"\n⚠️ Ошибка: {bot['last_error'][:100]}"

    await callback.message.edit_text(text, reply_markup=bot_card_keyboard(bot_id), parse_mode="HTML")


@router.callback_query(lambda c: c.data.startswith("start_"))
async def cb_start(callback: types.CallbackQuery):
    bot_id = callback.data.replace("start_", "")
    bot = await db.get_bot(bot_id)
    if not bot:
        await callback.answer("❌ Бот не найден")
        return
    await deploy.start_service_by_name(bot["systemd_unit"])
    status = await deploy.get_service_status_by_name(bot["systemd_unit"])
    db_status = "running" if status == "active" else "error"
    await db.update_bot_status(bot_id, db_status)
    await callback.answer(f"▶️ {'Запущен' if db_status == 'running' else 'Ошибка запуска'}")


@router.callback_query(lambda c: c.data.startswith("stop_"))
async def cb_stop(callback: types.CallbackQuery):
    bot_id = callback.data.replace("stop_", "")
    bot = await db.get_bot(bot_id)
    if not bot:
        await callback.answer("❌ Бот не найден")
        return
    await deploy.stop_service_by_name(bot["systemd_unit"])
    await db.update_bot_status(bot_id, "stopped")
    await callback.answer("⏹ Остановлен")


@router.callback_query(lambda c: c.data.startswith("restart_"))
async def cb_restart(callback: types.CallbackQuery):
    bot_id = callback.data.replace("restart_", "")
    bot = await db.get_bot(bot_id)
    if not bot:
        await callback.answer("❌ Бот не найден")
        return
    await deploy.restart_service_by_name(bot["systemd_unit"])
    status = await deploy.get_service_status_by_name(bot["systemd_unit"])
    db_status = "running" if status == "active" else "error"
    await db.update_bot_status(bot_id, db_status)
    await callback.answer(f"🔄 {'Перезапущен' if db_status == 'running' else 'Ошибка'}")


@router.callback_query(lambda c: c.data.startswith("logs_"))
async def cb_logs(callback: types.CallbackQuery):
    bot_id = callback.data.replace("logs_", "")
    bot = await db.get_bot(bot_id)
    if not bot:
        await callback.answer("❌ Бот не найден")
        return
    logs = await deploy.get_logs_by_name(bot["systemd_unit"], lines=50)
    if not logs.strip():
        logs = "📭 Логи пустые"
    if len(logs) > 4000:
        logs = logs[:4000] + "\n\n... (обрезано)"
    await callback.message.answer(
        f"📜 <b>Логи {bot['telegram_bot_username']}:</b>\n\n<code>{logs}</code>",
        parse_mode="HTML"
    )


@router.callback_query(lambda c: c.data.startswith("update_"))
async def cb_update(callback: types.CallbackQuery):
    bot_id = callback.data.replace("update_", "")
    bot = await db.get_bot(bot_id)
    if not bot or bot["source_type"] != "github":
        await callback.answer("⚠️ Обновление доступно только для GitHub ботов", show_alert=True)
        return

    msg = await callback.message.answer("⏳ Обновляю из GitHub...")

    # Если source_value пустой — пробуем получить URL из git remote
    github_url = bot["source_value"] or ""
    if not github_url:
        github_url = await deploy.get_git_remote_url(bot["work_dir"], bot["system_user"])
        if github_url:
            await db.update_source_value(bot_id, github_url)
        else:
            await msg.edit_text("❌ Не удалось определить URL репозитория. Проверь git remote origin вручную.")
            return

    branch = bot["branch"] or "main"
    success, err = await deploy.pull_and_update(bot["work_dir"], bot["system_user"], branch)
    if not success:
        await msg.edit_text(f"❌ Ошибка git pull:\n<code>{err[:500]}</code>", parse_mode="HTML")
        return

    await deploy.restart_service_by_name(bot["systemd_unit"])
    status = await deploy.get_service_status_by_name(bot["systemd_unit"])
    db_status = "running" if status == "active" else "error"
    await db.update_bot_status(bot_id, db_status)
    icon = "✅" if db_status == "running" else "⚠️"
    await msg.edit_text(f"{icon} Обновлено и {'перезапущено' if db_status == 'running' else 'сервис не поднялся — проверь логи'}")


@router.callback_query(lambda c: c.data.startswith("delete_"))
async def cb_delete(callback: types.CallbackQuery):
    bot_id = callback.data.replace("delete_", "")
    bot = await db.get_bot(bot_id)
    if not bot:
        await callback.answer("❌ Бот не найден")
        return
    if deploy.is_protected(bot["system_user"]):
        await callback.answer("🚫 Этот бот защищён от удаления", show_alert=True)
        return
    await callback.message.edit_text(
        f"⚠️ <b>Удалить @{bot['telegram_bot_username']}?</b>\n\n"
        "Бот будет остановлен и удалён с сервера вместе со всеми файлами.",
        reply_markup=delete_confirm1_keyboard(bot_id),
        parse_mode="HTML"
    )


@router.callback_query(lambda c: c.data.startswith("delconf1_"))
async def cb_delete_confirm1(callback: types.CallbackQuery):
    bot_id = callback.data.replace("delconf1_", "")
    bot = await db.get_bot(bot_id)
    if not bot:
        await callback.answer("❌ Бот не найден")
        return
    await callback.message.edit_text(
        f"🚨 <b>ПОСЛЕДНЕЕ ПРЕДУПРЕЖДЕНИЕ</b>\n\n"
        f"Бот @{bot['telegram_bot_username']} и все его файлы будут <b>безвозвратно удалены с сервера</b>.\n\n"
        "Это действие нельзя отменить.",
        reply_markup=delete_confirm2_keyboard(bot_id),
        parse_mode="HTML"
    )


@router.callback_query(lambda c: c.data.startswith("delconf2_"))
async def cb_delete_confirm2(callback: types.CallbackQuery):
    bot_id = callback.data.replace("delconf2_", "")
    bot = await db.get_bot(bot_id)
    if bot:
        if deploy.is_protected(bot["system_user"]):
            await callback.answer("🚫 Этот бот защищён от удаления", show_alert=True)
            return
        await deploy.delete_service_by_name(
            bot["systemd_unit"], bot["system_user"], bot["work_dir"],
            source_type=bot["source_type"]
        )
    await db.delete_bot(bot_id)
    await callback.message.edit_text("🗑 Бот удалён с сервера")
