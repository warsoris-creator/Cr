from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from states import AddBot
from keyboards import cancel_keyboard, source_type_keyboard
import services.telegram_api as tg_api
import services.deploy as deploy_service
import db

router = Router()

@router.message(Command("add"))
async def cmd_add(message: types.Message, state: FSMContext):
    await state.set_state(AddBot.waiting_for_token)
    await message.answer(
        "🔑 <b>Шаг 1/3: Отправьте токен бота</b>\n\n"
        "Получите токен у @BotFather (команда /newbot)\n"
        "Токен выглядит так: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(lambda c: c.data == "add_bot")
async def cb_add_bot(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddBot.waiting_for_token)
    await callback.message.answer(
        "🔑 <b>Шаг 1/3: Отправьте токен бота</b>\n\n"
        "Получите токен у @BotFather (команда /newbot)",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(lambda c: c.data == "cancel_add")
async def cb_cancel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("❌ Отменено")

@router.message(AddBot.waiting_for_token)
async def process_token(message: types.Message, state: FSMContext):
    token = message.text.strip()

    bot_info = await tg_api.validate_token(token)
    if not bot_info:
        await message.answer(
            "❌ Неверный токен. Попробуйте ещё раз.\n"
            "Токен должен быть в формате: 123456789:ABCdef...",
            reply_markup=cancel_keyboard()
        )
        return

    await state.update_data(token=token, bot_info=bot_info)
    await state.set_state(AddBot.waiting_for_source_type)

    await message.answer(
        f"✅ Токен принят!\nБот: @{bot_info['username']}\n\n"
        "📂 <b>Шаг 2/3: Выберите источник кода</b>",
        reply_markup=source_type_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(lambda c: c.data == "source_github")
async def cb_source_github(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(source_type="github")
    await state.set_state(AddBot.waiting_for_github_url)
    await callback.message.answer(
        "🌐 <b>Отправьте ссылку на GitHub репозиторий</b>\n\n"
        "Пример: https://github.com/username/repo",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(lambda c: c.data == "source_file")
async def cb_source_file(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(source_type="file")
    await state.set_state(AddBot.waiting_for_file)
    await callback.message.answer(
        "📁 <b>Отправьте Python файл (.py) или архив (.zip)</b>\n\n"
        "Файл должен содержать код бота",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )

@router.message(AddBot.waiting_for_github_url)
async def process_github_url(message: types.Message, state: FSMContext):
    github_url = message.text.strip()

    if not github_url.startswith("https://github.com/"):
        await message.answer(
            "❌ Неверная ссылка. Должна начинаться с https://github.com/\n"
            "Отправьте корректную ссылку:",
            reply_markup=cancel_keyboard()
        )
        return

    await state.update_data(github_url=github_url)
    data = await state.get_data()
    await deploy_and_save_bot(message, state, data)

@router.message(AddBot.waiting_for_file, F.document)
async def process_file(message: types.Message, state: FSMContext):
    doc = message.document

    if not (doc.file_name.endswith(".py") or doc.file_name.endswith(".zip")):
        await message.answer(
            "❌ Нужно отправить .py или .zip файл\n"
            "Попробуйте ещё раз:",
            reply_markup=cancel_keyboard()
        )
        return

    file = await message.bot.get_file(doc.file_id)
    file_bytes = await message.bot.download_file(file.file_path)

    data = await state.get_data()
    await state.update_data(file_bytes=file_bytes.read(), filename=doc.file_name)
    data = await state.get_data()
    await deploy_and_save_bot(message, state, data)

async def deploy_and_save_bot(message: types.Message, state: FSMContext, data: dict):
    bot_info = data["bot_info"]
    token = data["token"]
    source_type = data["source_type"]

    await message.answer("⏳ <b>Начинаю развёртывание...</b>", parse_mode="HTML")

    bot_id = await db.add_bot(
        telegram_bot_id=bot_info["id"],
        telegram_bot_username=bot_info["username"],
        token=token,
        source_type=source_type,
        source_value=data.get("github_url", ""),
        entrypoint=data.get("filename", "bot.py") if source_type == "file" else "bot.py"
    )

    work_dir = f"/srv/telegram-bots/{bot_id}"
    username = f"tgbot_{bot_id}"

    await message.answer("📁 Создаю пользователя и папку...")
    await deploy_service.create_system_user(username)

    if source_type == "github":
        await message.answer("🌐 Клонирую репозиторий...")
        success = await deploy_service.clone_github(data["github_url"], work_dir)
    else:
        await message.answer("📁 Сохраняю файл...")
        success = await deploy_service.save_python_file(data["file_bytes"], work_dir, data.get("filename", "bot.py"))

    if not success:
        await db.update_bot_status(bot_id, "error", last_error="Failed to get code")
        await message.answer("❌ Ошибка при получении кода")
        await state.clear()
        return

    await message.answer("🔧 Настраиваю окружение...")
    await deploy_service.setup_venv(work_dir)

    await message.answer("⚙️ Создаю systemd сервис...")
    entrypoint = data.get("filename", "bot.py") if source_type == "file" else "bot.py"
    await deploy_service.create_systemd_service(bot_id, username, work_dir, entrypoint)

    await message.answer("▶️ Запускаю бота...")
    await deploy_service.start_service(bot_id)

    status = await deploy_service.get_service_status(bot_id)
    db_status = "running" if status == "active" else "error"
    await db.update_bot_status(bot_id, db_status)

    await state.clear()
    await message.answer(
        f"✅ <b>Бот @{bot_info['username']} успешно создан!</b>\n\n"
        f"ID: {bot_id}\n"
        f"Статус: {'✅ Работает' if db_status == 'running' else '❌ Ошибка'}\n\n"
        "Используйте /status для управления",
        parse_mode="HTML"
    )
